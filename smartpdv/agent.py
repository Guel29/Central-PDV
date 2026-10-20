import asyncio
import base64
import ipaddress
import json
import socket
import time
from aiohttp import ClientSession, ClientWSTimeout, Fingerprint, WSMsgType
from .storage import load_json, unprotect


def lan_address(host):
    addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    ips = [ipaddress.ip_address(row[4][0]) for row in addresses]
    if not ips or any(not (ip.is_private or ip.is_loopback or ip.is_link_local) for ip in ips):
        raise ValueError('A Central deve ter endereço de rede local')
    return str(ips[0])


class Agent:
    def __init__(self, path, desktop):
        self.config = load_json(path)
        self.desktop = desktop
        self.pending = False
        self.active = False
        self.running = True

    async def run(self):
        delay = 1
        try:
            async with ClientSession() as client:
                while self.running:
                    try:
                        ip = await asyncio.to_thread(lan_address, self.config['central'])
                        address = f'[{ip}]' if ':' in ip else ip
                        async with client.ws_connect(f"https://{address}:{self.config['port']}/agent",
                            ssl=Fingerprint(bytes.fromhex(self.config['fingerprint'])), heartbeat=5,
                            timeout=ClientWSTimeout(ws_receive=20, ws_close=5), max_msg_size=8192,
                            headers={'Authorization':'Bearer ' + unprotect(self.config['token']),
                                     'X-Computer-ID':self.config['computer_id']}) as ws:
                            delay = 1
                            if self.pending:
                                await ws.send_json({'type':'request'})
                            sender = asyncio.create_task(self.send(ws))
                            try:
                                async for message in ws:
                                    if message.type != WSMsgType.TEXT:
                                        continue
                                    data = json.loads(message.data)
                                    if data['type'] == 'session':
                                        self.active = bool(data['active'])
                                        self.desktop.release()
                                        if self.active:
                                            self.pending = False
                                    elif data['type'] == 'input' and self.active:
                                        self.desktop.input(data['event'])
                            finally:
                                sender.cancel()
                                await asyncio.gather(sender, return_exceptions=True)
                    except Exception as exc:
                        # Não registrar payloads, tokens, capturas ou teclas.
                        print('Conexão indisponível:', type(exc).__name__, flush=True)
                    finally:
                        self.active = False
                        self.desktop.release()
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 15)
        finally:
            self.desktop.close()

    async def send(self, ws):
        last_frame = 0
        try:
            while True:
                if self.config['f11'] and self.desktop.requested() and not self.active:
                    self.pending = True
                    await ws.send_json({'type':'request'})
                interval = 0.25 if self.active else 2
                if time.monotonic() - last_frame >= interval:
                    jpeg = await asyncio.to_thread(self.desktop.capture, self.active)
                    await ws.send_json({'type':'frame', 'jpeg':base64.b64encode(jpeg).decode()})
                    last_frame = time.monotonic()
                await asyncio.sleep(0.03)
        except Exception:
            await ws.close()
            raise
