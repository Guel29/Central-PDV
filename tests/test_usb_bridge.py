"""Real TLS/WebSocket and USB/IP framing against a controlled TCP USB endpoint.

The endpoint does not emulate an LS2208 or validate any Windows driver or VR.
"""
import asyncio
import contextlib
from pathlib import Path
import time
import struct
from aiohttp import ClientSession, Fingerprint, ClientResponseError
import pytest
from smartpdv.usb import IMPORT, IMPORTED, USBError
from test_system import prepare, start, local_session, message_type, TOKEN

INSTANCE = r'USB\VID_05E0&PID_1200\TEST_DEVICE'


class Host:
    def __init__(self):
        self.attached = False
        self.authorized = True
        self.present = True
        self.candidate = True
    async def secure(self):
        if not self.authorized:
            raise USBError('Proteção da porta USB/IP não confirmada')
    async def devices(self):
        return [dict(instance=INSTANCE,description='LS2208 test fixture',busid='1-2',
                     candidate=self.candidate,shared=True,attached=self.attached)] if self.present else []


async def scenario(path, check, two=False):
    pin = Fingerprint(bytes.fromhex(prepare(path)))
    if two:
        from smartpdv.storage import load_json, atomic_json
        from smartpdv.security import token_hash
        config=load_json(path/'central.json')
        config['pdvs'].append(dict(number=2,computer_id='device-2',token_hash=token_hash('token-2')))
        atomic_json(path/'central.json',config)
    central, runner, port = await start(path)
    host = central.usb.host = Host()
    counters = {'connections':0}
    async def usb(reader,writer):
        counters['connections'] += 1
        try:
            assert await reader.readexactly(40) == IMPORT+b'1-2'.ljust(32,b'\0')
            host.attached = True
            descriptor=bytearray(312)
            descriptor[256:288]=b'1-2'.ljust(32,b'\0')
            descriptor[300:304]=struct.pack('!HH',0x05e0,0x1200)
            writer.write(IMPORTED+descriptor)
            await writer.drain()
            while chunk := await reader.read(65536):
                writer.write(chunk)
                await writer.drain()
        except (OSError,asyncio.IncompleteReadError):
            pass
        finally:
            host.attached = False
            writer.close()
    server = await asyncio.start_server(usb,'127.0.0.1',0)
    tcp_port = server.sockets[0].getsockname()[1]
    async def connect():
        return await asyncio.open_connection('127.0.0.1',tcp_port)
    central.usb.open_host = connect
    url = f'https://127.0.0.1:{port}'
    auth = {'Authorization':'Bearer '+TOKEN,'X-Computer-ID':'test-device','X-SmartPDV-USB':'usbip-win7-v1'}
    try:
        async with ClientSession() as client:
            agent = await client.ws_connect(url+'/agent',ssl=pin,headers=auth)
            dashboard = await client.ws_connect(url+'/dashboard',ssl=pin,headers=await local_session(client,url,pin))
            await dashboard.send_json({'type':'start','number':1})
            assert (await agent.receive_json())['active']
            await message_type(dashboard,'opened')
            await dashboard.send_json({'type':'usb','action':'select','instance':INSTANCE,'confirm_ls2208':True})
            await wait_until(lambda:central.usb.selection is not None)
            await check(central,host,client,url,pin,auth,agent,dashboard,counters)
            await dashboard.close()
            await agent.close()
    finally:
        await runner.cleanup()
        server.close()
        await server.wait_closed()


async def wait_until(predicate):
    async def wait():
        while not predicate():
            await asyncio.sleep(.01)
    await asyncio.wait_for(wait(),5)


async def grant(dashboard, agent):
    await dashboard.send_json({'type':'usb','action':'connect','number':1})
    return await message_type(agent,'usb_connect')


def test_real_tls_usb_stream_exclusive_one_shot_and_end(tmp_path):
    async def check(c,h,client,url,pin,auth,agent,dashboard,counters):
        lease = await grant(dashboard,agent)
        assert c.usb.status == 'conectando'
        with pytest.raises(ClientResponseError) as exc:
            await client.ws_connect(url+'/usb-stream',ssl=pin,headers={**auth,'X-USB-Lease':'wrong'})
        assert exc.value.status == 403
        headers = {**auth,'X-USB-Lease':lease['lease']}
        ws = await client.ws_connect(url+'/usb-stream',ssl=pin,headers=headers)
        await ws.send_bytes(IMPORT+b'1-2'.ljust(32,b'\0'))
        assert (await ws.receive()).data == IMPORTED
        assert len((await ws.receive()).data)==312
        await agent.send_json({'type':'usb_status','lease':lease['lease'],'ok':True})
        await wait_until(lambda:c.usb.status=='conectado')
        payload = bytes(range(256))*300
        # Binary relay must survive chunk boundaries without storing/replaying data.
        for offset in range(0,len(payload),16000):
            await ws.send_bytes(payload[offset:offset+16000])
        received = b''
        while len(received)<len(payload):
            received += (await asyncio.wait_for(ws.receive(),3)).data
        assert received == payload
        with pytest.raises(ClientResponseError) as exc:
            await client.ws_connect(url+'/usb-stream',ssl=pin,headers=headers)
        assert exc.value.status==403
        assert counters['connections']==1
        await dashboard.send_json({'type':'end','number':1,'result':'Concluído'})
        await wait_until(lambda:c.usb.lease is None)
        assert (await ws.receive()).type.name in ('CLOSE','CLOSED')
        with pytest.raises(ClientResponseError):
            await client.ws_connect(url+'/usb-stream',ssl=pin,headers=headers)
        assert not any(payload[:32] in p.read_bytes() for p in Path(tmp_path).rglob('*.jsonl'))
    asyncio.run(scenario(tmp_path,check))


def test_import_cannot_export_another_usb_or_list_devices(tmp_path):
    async def check(c,h,client,url,pin,auth,agent,dashboard,counters):
        for preamble in (IMPORT+b'1-9'.ljust(32,b'\0'),b'list devices',IMPORT):
            lease = await grant(dashboard,agent)
            ws = await client.ws_connect(url+'/usb-stream',ssl=pin,headers={**auth,'X-USB-Lease':lease['lease']})
            await ws.send_bytes(preamble)
            await ws.receive()
            await wait_until(lambda:c.usb.lease is None)
            assert counters['connections']==0
    asyncio.run(scenario(tmp_path,check))


def test_raw_firewall_and_removed_identity_block_import(tmp_path):
    async def check(c,h,client,url,pin,auth,agent,dashboard,counters):
        h.authorized=False
        await dashboard.send_json({'type':'usb','action':'connect','number':1})
        await wait_until(lambda:c.usb.status=='erro')
        assert c.usb.lease is None
        h.authorized=True
        lease=await grant(dashboard,agent)
        h.present=False
        ws=await client.ws_connect(url+'/usb-stream',ssl=pin,headers={**auth,'X-USB-Lease':lease['lease']})
        await ws.send_bytes(IMPORT+b'1-2'.ljust(32,b'\0'))
        await ws.receive()
        await wait_until(lambda:c.usb.lease is None)
        assert counters['connections']==0
    asyncio.run(scenario(tmp_path,check))


def test_claim_requires_auth_and_cannot_mark_connected_without_import(tmp_path):
    async def check(c,h,client,url,pin,auth,agent,dashboard,counters):
        lease=await grant(dashboard,agent)
        for credentials in ({},{**auth,'Authorization':'Bearer incorrect'}):
            with pytest.raises(ClientResponseError) as exc:
                await client.ws_connect(url+'/usb-stream',ssl=pin,headers={**credentials,'X-USB-Lease':lease['lease']})
            assert exc.value.status==401
        await agent.send_json({'type':'usb_status','lease':lease['lease'],'ok':True})
        await wait_until(lambda:c.usb.lease is None)
        assert c.usb.status=='erro'
        assert counters['connections']==0
    asyncio.run(scenario(tmp_path,check))


def test_select_rejects_generic_keyboard_without_model_confirmation(tmp_path):
    async def check(c,h,client,url,pin,auth,agent,dashboard,counters):
        c.usb.selection=None
        await dashboard.send_json({'type':'usb','action':'select','instance':INSTANCE})
        await wait_until(lambda:c.usb.status=='erro')
        assert c.usb.selection is None
        h.candidate=False
        await dashboard.send_json({'type':'usb','action':'select','instance':INSTANCE,'confirm_ls2208':True})
        await asyncio.sleep(.1)
        assert c.usb.selection is None
    asyncio.run(scenario(tmp_path,check))


def test_switch_closes_previous_before_granting_another_pdv(tmp_path):
    async def check(c,h,client,url,pin,auth,agent,dashboard,counters):
        other=await client.ws_connect(url+'/agent',ssl=pin,headers={
            'Authorization':'Bearer token-2','X-Computer-ID':'device-2','X-SmartPDV-USB':'usbip-win7-v1'})
        await dashboard.send_json({'type':'start','number':2})
        assert (await other.receive_json())['active']
        await message_type(dashboard,'opened')
        first=await grant(dashboard,agent)
        ws=await client.ws_connect(url+'/usb-stream',ssl=pin,headers={**auth,'X-USB-Lease':first['lease']})
        await ws.send_bytes(IMPORT+b'1-2'.ljust(32,b'\0'))
        assert (await ws.receive()).data==IMPORTED
        await ws.receive()  # device descriptor
        await dashboard.send_json({'type':'usb','action':'connect','number':2})
        second=await message_type(other,'usb_connect')
        assert first['lease']!=second['lease']
        assert c.usb.lease['number']==2
        assert not h.attached
        assert (await ws.receive()).type.name in ('CLOSE','CLOSED')
        # First PDV's valid credential cannot use the second PDV's fresh grant.
        with pytest.raises(ClientResponseError) as exc:
            await client.ws_connect(url+'/usb-stream',ssl=pin,headers={**auth,'X-USB-Lease':second['lease']})
        assert exc.value.status==403
        await other.close()
        await wait_until(lambda:c.usb.lease is None)
    asyncio.run(scenario(tmp_path,check,two=True))


def test_expired_owner_revokes_an_unused_grant_without_reconnect(tmp_path):
    async def check(c,h,client,url,pin,auth,agent,dashboard,counters):
        lease=await grant(dashboard,agent)
        for session in c.sessions.values():
            session['expires']=time.monotonic()-1
        await wait_until(lambda:c.usb.lease is None)
        with pytest.raises(ClientResponseError):
            await client.ws_connect(url+'/usb-stream',ssl=pin,headers={**auth,'X-USB-Lease':lease['lease']})
        assert counters['connections']==0
    asyncio.run(scenario(tmp_path,check))


def test_other_dashboard_cannot_disconnect_or_replace_an_owned_grant(tmp_path):
    async def check(c,h,client,url,pin,auth,agent,dashboard,counters):
        lease=await grant(dashboard,agent)
        other=await client.ws_connect(url+'/dashboard',ssl=pin,headers=await local_session(client,url,pin))
        for action in ('connect','disconnect','select'):
            await other.send_json({'type':'usb','action':action,'number':1,'instance':INSTANCE,'confirm_ls2208':True})
            error=await message_type(other,'error')
            assert 'outro atendimento' in error['message']
            assert c.usb.lease['id']==lease['lease']
            assert c.usb.status=='conectando'
        await other.close()
        assert c.usb.lease['id']==lease['lease']
    asyncio.run(scenario(tmp_path,check))
