"""Exclusive USB/IP import over the existing pinned/authenticated TLS transport.

USB payloads are opaque, bounded and never logged, stored or retried.
"""
import asyncio
import contextlib
import json
import os
from pathlib import Path
import re
import secrets
import struct
import time
from aiohttp import web, WSMsgType
from .storage import atomic_json, load_json

IMPORT = struct.pack('!HHI', 0x111, 0x8003, 0)
IMPORTED = struct.pack('!HHI', 0x111, 3, 0)


class USBError(RuntimeError):
    pass


async def run(exe, *args):
    try:
        proc = await asyncio.create_subprocess_exec(str(exe), *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            creationflags=getattr(__import__('subprocess'), 'CREATE_NO_WINDOW', 0))
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), 15)
        except BaseException:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
            raise
        if proc.returncode:
            raise USBError('Componente USB retornou falha; confira instalação e permissões')
        return out.decode('utf-8-sig')
    except (OSError, asyncio.TimeoutError) as exc:
        raise USBError('Componente USB ausente ou sem resposta') from exc


class WindowsHost:
    def __init__(self):
        self.exe = Path(os.environ.get('ProgramFiles', r'C:\Program Files'))/'usbipd-win'/'usbipd.exe'

    async def devices(self):
        if os.name != 'nt':
            raise USBError('Servidor USB requer Central Windows 10/11 com usbipd-win instalado')
        state = json.loads(await run(self.exe, 'state'))
        return [dict(instance=d['InstanceId'], description=d.get('Description',''),
                     busid=d['BusId'], shared=bool(d.get('PersistedGuid')),
                     attached=bool(d.get('ClientIPAddress')),
                     candidate=bool(re.fullmatch(r'USB\\VID_05E0&PID_[0-9A-F]{4}\\[^\\]+',d['InstanceId'],re.I)))
                for d in state['Devices'] if d.get('BusId')]

    async def secure(self):
        # Raw USB/IP must never be reachable through the LAN. Loopback stays local.
        script = """$ErrorActionPreference='Stop';
$r=Get-NetFirewallRule -PolicyStore ActiveStore -Name SmartPDV-USB-Raw-Block;
$p=$r | Get-NetFirewallPortFilter; $a=$r | Get-NetFirewallAddressFilter;
if ($r.Enabled -ne 'True' -or $r.Action -ne 'Block' -or $r.Direction -ne 'Inbound' -or
[string]$r.Profile -ne 'Any' -or $p.Protocol -ne 'TCP' -or $p.LocalPort -ne '3240' -or
$a.RemoteAddress -ne 'Any' -or $a.LocalAddress -ne 'Any') {exit 1};
if ((Get-NetFirewallProfile -PolicyStore ActiveStore | Where-Object { -not $_.Enabled }).Count) {exit 1};
Write-Output OK"""
        if (await run('powershell.exe','-NoProfile','-NonInteractive','-Command',script)).strip() != 'OK':
            raise USBError('Proteção da porta USB/IP não confirmada')


async def pump(ws, reader, writer):
    async def to_client():
        while chunk := await reader.read(65536):
            await ws.send_bytes(chunk)
    async def to_host():
        async for msg in ws:
            if msg.type != WSMsgType.BINARY:
                break
            writer.write(msg.data)
            await writer.drain()
    tasks = [asyncio.create_task(to_client()), asyncio.create_task(to_host())]
    try:
        await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        await ws.close()


class Bridge:
    def __init__(self, central, host=None):
        self.central, self.host = central, host or WindowsHost()
        self.path = central.directory/'usb-reader.json'
        self.selection = load_json(self.path) if self.path.exists() else None
        self.lock = asyncio.Lock()
        self.lease = None
        self.devices = []
        self.status, self.error = 'desconectado', None
        self.last_bus = None

    def public(self):
        return dict(status=self.status,error=self.error,devices=self.devices,selection=self.selection,
                    number=self.lease['number'] if self.lease else None)

    def authorized(self, lease):
        state = self.central.state.get(lease['number'],{})
        if not state.get('active') or state.get('owner') != lease['owner']:
            return False
        return any(id(ws)==lease['owner'] and not ws.closed and session['control']
                   and session['token'] in self.central.sessions and session['expires']>time.monotonic()
                   for ws,session in self.central.viewers.items())

    async def refresh(self):
        self.devices = await self.host.devices()
        self.error = None
        if not self.lease:
            self.status = 'disponível' if any(self.selected(d) and d['shared'] and not d['attached']
                                             for d in self.devices) else 'desconectado'

    def selected(self, device):
        return bool(self.selection and device['candidate'] and device['instance'] == self.selection['instance'])

    async def stop(self):
        old, self.lease = self.lease, None  # revoke before await: one-shot tokens
        if old:
            self.last_bus = old['busid']
            if old.get('writer'):
                old['writer'].close()
            if old.get('ws'):
                await old['ws'].close()
            agent = self.central.agents.get(old['number'])
            if agent and not agent.closed:
                with contextlib.suppress(ConnectionError,RuntimeError):
                    await agent.send_json({'type':'usb_disconnect','lease':old['id']})
        self.status, self.error = 'desconectado', None

    async def previous_detached(self):
        # No new destination until the real USB host releases the previous one.
        if self.last_bus:
            for _ in range(10):
                if not any(d['busid'] == self.last_bus and d['attached'] for d in await self.host.devices()):
                    self.last_bus = None
                    return
                await asyncio.sleep(.2)
            raise USBError('Conexão USB anterior ainda não foi liberada; tente novamente após corrigir')

    async def action(self, data, owner):
        async with self.lock:
            action = data.get('action')
            if self.lease and self.lease['owner'] != owner and action != 'refresh':
                raise USBError('Leitor pertence a outro atendimento')
            try:
                if action == 'refresh':
                    await self.refresh()
                elif action == 'select':
                    await self.stop()
                    await self.previous_detached()
                    await self.refresh()
                    device = next((d for d in self.devices if d['instance'] == data.get('instance')),None)
                    if not device or not device['candidate'] or data.get('confirm_ls2208') is not True:
                        raise USBError('Confirme o LS2208 físico; fabricante sozinho não identifica o modelo')
                    selection = {'instance':device['instance'],'description':device['description']}
                    await asyncio.to_thread(atomic_json,self.path,selection)
                    self.selection = selection
                    await self.refresh()
                elif action == 'disconnect':
                    await self.stop()
                    await self.previous_detached()
                elif action == 'connect':
                    number = data.get('number')
                    state = self.central.state.get(number) if type(number) is int else None
                    if not state or not state['active'] or state['owner'] != owner or not state.get('usb_capable'):
                        raise USBError('Abra atendimento no PDV com componente USB Windows 7 habilitado')
                    await self.stop()
                    await self.previous_detached()
                    await self.host.secure()
                    await self.refresh()
                    device = next((d for d in self.devices if self.selected(d)),None)
                    if not device or not device['shared'] or device['attached']:
                        raise USBError('Leitor ausente, não preparado pelo administrador ou já em uso')
                    busid = device['busid']
                    if not re.fullmatch(r'\d+-\d+',busid):
                        raise USBError('BUSID inválido')
                    lease = dict(id=secrets.token_urlsafe(32),number=number,owner=owner,busid=busid,
                                 claimed=False,imported=False,deadline=time.monotonic()+30,ws=None,writer=None)
                    self.lease = lease
                    self.status = 'conectando'
                    await self.central.agents[number].send_json({'type':'usb_connect','lease':lease['id'],
                        'busid':busid,'instance':device['instance']})
                else:
                    raise USBError('Comando USB inválido')
            except (USBError,OSError,ValueError,KeyError) as exc:
                # Static diagnostics only: no CLI output, card contents or USB bytes.
                error = str(exc) if isinstance(exc,USBError) else 'Falha ao preparar leitor USB'
                if data.get('action') == 'connect':
                    await self.stop()
                self.status,self.error = 'erro',error
        await self.central.publish()

    async def release(self, *, number=None, owner=None):
        async with self.lock:
            if self.lease and (self.lease['number'] == number or self.lease['owner'] == owner):
                await self.stop()

    async def report(self, number, data):
        async with self.lock:
            lease = self.lease
            if not lease or lease['number'] != number or data.get('lease') != lease['id']:
                return
            if data.get('ok') is True and lease['imported']:
                self.status = 'conectado'
            else:
                await self.stop()
                self.status,self.error = 'erro','Cliente não reconheceu o USB ou perdeu a conexão; reconecte explicitamente'
        await self.central.publish()

    async def watch(self):
        while True:
            await asyncio.sleep(2)
            lease = self.lease
            if not lease:
                continue
            try:
                if not self.authorized(lease):
                    raise USBError('Atendimento expirou')
                if self.status != 'conectado' and time.monotonic() > lease['deadline']:
                    raise USBError('Tempo de anexação USB esgotado')
                await self.host.secure()
                devices = await self.host.devices()
                if not any(self.selected(d) and d['busid']==lease['busid'] for d in devices):
                    raise USBError('Leitor removido ou mudou de identidade')
            except (USBError,OSError,ValueError,KeyError):
                async with self.lock:
                    if self.lease is lease:
                        await self.stop()
                        self.status,self.error = 'erro','Leitor ou transporte indisponível; reconecte explicitamente'
                await self.central.publish()

    async def stream(self, request, number):
        async with self.lock:
            lease = self.lease
            if (not lease or not self.authorized(lease) or lease['number'] != number or lease['claimed'] or
                    not secrets.compare_digest(request.headers.get('X-USB-Lease',''),lease['id'])):
                raise web.HTTPForbidden()
            lease['claimed'] = True
        ws = web.WebSocketResponse(heartbeat=3,receive_timeout=12,max_msg_size=65537,compress=False)
        await ws.prepare(request)
        lease['ws'] = ws
        writer = None
        try:
            msg = await asyncio.wait_for(ws.receive(),8)
            expected = IMPORT + lease['busid'].encode().ljust(32,b'\0')
            if msg.type != WSMsgType.BINARY or msg.data != expected:
                raise USBError('Somente importação do leitor selecionado é permitida')
            await self.host.secure()
            devices = await self.host.devices()
            if not any(self.selected(d) and d['busid']==lease['busid'] and not d['attached'] for d in devices):
                raise USBError('Identidade USB mudou')
            # Destination is fixed, never a client-provided TCP forwarding address.
            reader,writer = await asyncio.wait_for(self.open_host(),5)
            lease['writer'] = writer
            if self.lease is not lease or not self.authorized(lease):
                raise USBError('Concessão revogada')
            writer.write(expected)
            await writer.drain()
            header = await asyncio.wait_for(reader.readexactly(8),8)
            if header != IMPORTED:
                raise USBError('Servidor USB recusou importação')
            descriptor = await asyncio.wait_for(reader.readexactly(312),8)
            identity = re.search(r'VID_([0-9A-F]{4})&PID_([0-9A-F]{4})',self.selection['instance'],re.I)
            if (struct.unpack('!HH',descriptor[300:304]) != tuple(int(x,16) for x in identity.groups())
                    or descriptor[256:288].rstrip(b'\0') != lease['busid'].encode()):
                raise USBError('Servidor retornou outro dispositivo USB')
            if not any(self.selected(d) and d['busid']==lease['busid'] and d['attached']
                       for d in await self.host.devices()):
                raise USBError('Identidade do leitor anexado não confirmada')
            lease['imported'] = True
            await ws.send_bytes(header)
            await ws.send_bytes(descriptor)
            await pump(ws,reader,writer)
        except (USBError,OSError,asyncio.TimeoutError,asyncio.IncompleteReadError):
            pass
        finally:
            if writer:
                writer.close()
            await ws.close()
            async with self.lock:
                if self.lease is lease:
                    await self.stop()
                    self.status,self.error = 'erro','Transporte USB encerrado; reconecte explicitamente'
            await self.central.publish()
        return ws

    async def open_host(self):
        return await asyncio.open_connection('127.0.0.1',3240)
