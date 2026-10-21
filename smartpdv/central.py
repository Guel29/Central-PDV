import asyncio
import base64
import binascii
import datetime as dt
import json
import ipaddress
from pathlib import Path
import secrets
import time
import os
import re
import threading
from contextlib import AsyncExitStack
from aiohttp import web, WSMsgType
from .security import token_hash
from .storage import load_json, atomic_json
from .timed_keys import valid_sequence


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Central:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.config = load_json(self.directory / 'central.json')
        saved = self.config.get('peripherals', {})
        if not isinstance(saved,dict):
            saved = {}
        self.config['peripherals'] = {key:saved.get(key, True) if type(saved.get(key, True)) is bool else True for key in ('keyboard','mouse')}
        self.agents = {}
        self.log_lock = threading.Lock()
        self.viewers = {}
        self.sessions = {}
        self.locks = {p['number']: asyncio.Lock() for p in self.config['pdvs']}
        self.state = {p['number']: dict(number=p['number'], online=False, pending=False,
                      active=False, thumbnail=None, connected_at=None, requested_at=None,
                      supervisor=None, attended_at=None, owner=None, agent_version=None, keyboard_protocol=None, timed_keys=False) for p in self.config['pdvs']}
        self.app = web.Application(client_max_size=2 * 1024 * 1024, middlewares=[self.errors])
        self.app.add_routes([web.get('/', self.index), web.get('/app.js', self.asset),
                            web.get('/timed-keys.js', self.asset),
                            web.get('/style.css', self.asset), web.get('/session', self.session_info), web.get('/dashboard', self.dashboard),
                            web.get('/agent', self.agent), web.get('/health', self.health)])
        self.app.on_startup.append(self.start)
        self.app.on_shutdown.append(self.shutdown)
        self.app.on_cleanup.append(self.cleanup)

    @web.middleware
    async def errors(self, request, handler):
        if not request.remote or not ipaddress.ip_address(request.remote).is_private:
            raise web.HTTPForbidden(text='Acesso permitido somente pela rede local')
        try:
            response = await handler(request)
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            raise web.HTTPBadRequest(text='Mensagem inválida')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    async def index(self, request):
        self.require_console(request)
        return web.FileResponse(Path(__file__).parent / 'web' / 'index.html')

    async def asset(self, request):
        return web.FileResponse(Path(__file__).parent / 'web' / request.path[1:])

    async def health(self, request):
        from .version import VERSION
        return web.json_response({'status': 'ok', 'storage': 'json', 'transport': 'tls','version':VERSION})

    def same_origin(self, request):
        return request.headers.get('Origin') == f'https://{request.host}'

    @staticmethod
    def is_console(request):
        if not request.remote:
            return False
        remote = ipaddress.ip_address(request.remote)
        if remote.is_loopback:
            return True
        local = request.transport.get_extra_info('sockname') if request.transport else None
        return bool(local and remote == ipaddress.ip_address(local[0]))

    def require_console(self, request):
        if not self.is_console(request):
            raise web.HTTPForbidden(text='Abra o dashboard no próprio computador Central')

    def supervisor(self, request):
        self.require_console(request)
        session = self.sessions.get(request.cookies.get('session'))
        if not session or session['expires'] < time.monotonic():
            raise web.HTTPUnauthorized()
        return session

    async def session_info(self, request):
        self.require_console(request)
        if request.headers.get('Origin') and not self.same_origin(request):
            raise web.HTTPForbidden()
        if request.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise web.HTTPForbidden()
        token = request.cookies.get('session')
        session = self.sessions.get(token)
        if not session or session['expires'] < time.monotonic():
            token = secrets.token_urlsafe(32)
            session = {'name':'Central', 'control':True,
                       'expires':time.monotonic()+8*3600, 'token':token}
            self.sessions[token] = session
        result = web.json_response({'name':'Central','control':True,'direct_access':True})
        result.set_cookie('session',token,secure=True,httponly=True,samesite='Strict',max_age=28800)
        return result

    async def publish(self):
        public = [{k: v for k, v in s.items() if k != 'owner'} for s in self.state.values()]
        data = {'type': 'state', 'pdvs': public, 'alarm': self.config['alarm'], 'dashboard': self.config['dashboard'], 'peripherals':self.config['peripherals']}
        await self.broadcast(data)

    async def broadcast(self, data):
        async def deliver(ws):
            session = self.viewers.get(ws)
            if not session or session['token'] not in self.sessions or session['expires'] < time.monotonic():
                self.viewers.pop(ws, None)
                await ws.close()
                return
            try:
                await asyncio.wait_for(ws.send_json(data), 2)
            except (ConnectionError, asyncio.TimeoutError, RuntimeError):
                self.viewers.pop(ws, None)
                await ws.close()
        await asyncio.gather(*(deliver(ws) for ws in tuple(self.viewers)))

    async def dashboard(self, request):
        session = self.supervisor(request)
        if not self.same_origin(request):
            raise web.HTTPForbidden()
        ws = web.WebSocketResponse(heartbeat=10, max_msg_size=8192)
        await ws.prepare(request)
        self.viewers[ws] = session
        await self.publish()
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                if session['token'] not in self.sessions or session['expires'] < time.monotonic():
                    break
                try:
                    data = json.loads(msg.data)
                    if not isinstance(data,dict):
                        raise ValueError('Comando inválido')
                    if data.get('type') == 'peripherals':
                        settings = self.valid_peripherals(data.get('settings'))
                        if not session['control'] or settings is None:
                            raise ValueError('Autorizações inválidas')
                        async with AsyncExitStack() as locks:
                            for number in sorted(self.locks):
                                await locks.enter_async_context(self.locks[number])
                            # Merge just this setting into the current JSON, preserving PDV registrations.
                            try:
                                current = load_json(self.directory/'central.json')
                                current['peripherals'] = settings
                                await asyncio.to_thread(atomic_json,self.directory/'central.json',current)
                            except (OSError,ValueError,RuntimeError):
                                await ws.send_json({'type':'error','message':'Não foi possível salvar as autorizações. As opções anteriores continuam aplicadas.'})
                                continue
                            previous = self.config['peripherals']
                            self.config['peripherals'] = settings
                            if (previous['keyboard'] and not settings['keyboard']) or (previous['mouse'] and not settings['mouse']):
                                for number, agent in list(self.agents.items()):
                                    if self.state[number]['active'] and not agent.closed:
                                        await agent.send_json({'type':'input','event':{'kind':'release'}})
                        await self.publish()
                        await ws.send_json({'type':'peripherals_saved'})
                        continue
                    if data.get('type') not in {'start','end','input'}:
                        raise ValueError('Comando inválido')
                    s = self.state[int(data['number'])]
                    async with self.locks[s['number']]:
                        agent = self.agents.get(s['number'])
                        if not session['control'] or not agent:
                            await ws.send_json({'type': 'error', 'message': 'PDV indisponível ou sem permissão de controle'})
                            continue
                        if data['type'] == 'start' and not s['active']:
                            await agent.send_json({'type': 'session', 'active': True})
                            s.update(active=True, pending=False, supervisor=session['name'], attended_at=now(), owner=id(ws))
                            await ws.send_json({'type':'opened', 'number':s['number']})
                        elif data['type'] == 'start':
                            await ws.send_json({'type':'error','message':'PDV já está em atendimento'})
                        elif data['type'] == 'end' and s['owner'] == id(ws):
                            await self.end(s, data.get('result', 'Concluído'))
                        elif data['type'] == 'input' and s['owner'] == id(ws):
                            event = data['event']
                            if (self.valid_input(event) and self.input_allowed(event)
                                    and (event['kind'] != 'key_sequence' or s['timed_keys'])):
                                await agent.send_json({'type': 'input', 'event': event})
                            continue
                    await self.publish()
                except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                    await ws.send_json({'type': 'error', 'message': 'Comando inválido'})
        finally:
            self.viewers.pop(ws, None)
            for s in self.state.values():
                async with self.locks[s['number']]:
                    if s['owner'] == id(ws):
                        await self.end(s, 'Supervisor desconectado')
            await self.publish()
        return ws

    @staticmethod
    def valid_peripherals(settings):
        if not isinstance(settings,dict) or set(settings) != {'keyboard','mouse'}:
            return None
        return dict(settings) if all(type(value) is bool for value in settings.values()) else None

    def input_allowed(self,event):
        if event.get('kind') == 'release': return True
        key = 'keyboard' if event.get('kind') in ('key','key_sequence') else 'mouse'
        return self.config['peripherals'][key]

    @staticmethod
    def valid_input(event):
        if not isinstance(event, dict):
            return False
        if event.get('kind') == 'key_sequence':
            return valid_sequence(event)
        if event.get('kind') == 'release':
            return True
        if event.get('kind') == 'wheel':
            return type(event.get('delta')) is int and event['delta'] in (-120, 120)
        if event.get('kind') == 'mouse':
            return (event.get('action') in ('move', 'down', 'up') and event.get('button', 0) in (0, 2)
                    and all(type(event.get(k)) in (int, float) and 0 <= event[k] <= 1 for k in ('x', 'y')))
        code = event.get('code','')
        return (event.get('kind') == 'key' and event.get('action') in ('down', 'up')
                and isinstance(event.get('key'), str) and len(event['key']) <= 24
                and isinstance(code,str) and len(code) <= 32 and (not code or code.isascii() and code.isalnum()))

    async def end(self, s, result):
        if not s['active']:
            return
        if s['requested_at']:
            await asyncio.to_thread(self.log, {'pdv': s['number'], 'requested_at': s['requested_at'],
                       'supervisor': s['supervisor'], 'attended_at': s['attended_at'],
                       'result': result if result in {'Concluído','Liberado','Cancelado','Alternância de PDV','Supervisor desconectado','PDV desconectado'} else 'Concluído'})
        agent = self.agents.get(s['number'])
        if agent and not agent.closed:
            await agent.send_json({'type': 'session', 'active': False})
        s.update(active=False, owner=None, supervisor=None, attended_at=None)
        if not s['pending']:
            s['requested_at'] = None

    def log(self, entry):
        with self.log_lock:
            self._log(entry)

    def _log(self, entry):
        folder = self.directory / 'logs'
        folder.mkdir(exist_ok=True)
        today = dt.datetime.now(dt.timezone.utc).date()
        prefix = today.isoformat()
        index = 0
        maximum = self.config['logs']['max_bytes']
        while True:
            path = folder / f'{prefix}-{index:03}.jsonl'
            if not path.exists() or path.stat().st_size < maximum:
                break
            index += 1
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            f.flush()
            os.fsync(f.fileno())
        for old in folder.glob('*.jsonl'):
            try:
                day = dt.date.fromisoformat(old.name[:10])
                if (today - day).days >= self.config['logs']['retention_days']:
                    old.unlink()
            except ValueError:
                continue

    async def agent(self, request):
        identifier = request.headers.get('X-Computer-ID')
        digest = token_hash(request.headers.get('Authorization', '').removeprefix('Bearer '))
        pdv = next((p for p in self.config['pdvs'] if p['computer_id'] == identifier
                    and secrets.compare_digest(p['token_hash'], digest)), None)
        if not pdv:
            raise web.HTTPUnauthorized()
        number = pdv['number']
        if number in self.agents:
            raise web.HTTPConflict(text='PDV já conectado')
        ws = web.WebSocketResponse(heartbeat=5, receive_timeout=20, max_msg_size=1500000)
        await ws.prepare(request)
        self.agents[number] = ws
        s = self.state[number]
        version = request.headers.get('X-SmartPDV-Version','')
        version = version if re.fullmatch(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',version) else None
        protocol = request.headers.get('X-SmartPDV-Keyboard')
        s.update(online=True, connected_at=now(), agent_version=version,
                 timed_keys=request.headers.get('X-SmartPDV-Timed-Keys') == 'numeric-v1',
                 keyboard_protocol=protocol if protocol=='scan-code-v1' else None)
        await self.publish()
        last_frame = 0
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                data = json.loads(msg.data)
                if data['type'] == 'request' and not s['pending']:
                    s.update(pending=True, requested_at=now())
                    await self.publish()
                elif data['type'] == 'input_status' and s['active']:
                    accepted, code = data.get('accepted'), data.get('error_code')
                    if type(accepted) is bool and type(code) is int and 0 <= code <= 65535:
                        # Live result only, sent solely to the owner. Never log keys or input text.
                        for viewer in list(self.viewers):
                            if id(viewer) == s['owner'] and not viewer.closed:
                                await viewer.send_json({'type':'input_status','number':number,'accepted':accepted,'error_code':code})
                elif data['type'] == 'frame' and time.monotonic() - last_frame >= (0.15 if s['active'] else 1):
                    frame = data['jpeg']
                    if isinstance(frame, str) and len(frame) < 1400000:
                        try:
                            raw = base64.b64decode(frame, validate=True)
                        except (ValueError, binascii.Error):
                            continue
                        if not raw.startswith(b'\xff\xd8'):
                            continue
                        s['thumbnail'] = frame
                        last_frame = time.monotonic()
                        await self.broadcast({'type':'frame','number':number,'jpeg':frame})
        except (asyncio.TimeoutError, ConnectionError, ValueError, KeyError, TypeError):
            pass
        finally:
            self.agents.pop(number, None)
            async with self.locks[number]:
                await self.end(s, 'PDV desconectado')
                s.update(online=False, active=False, thumbnail=None, connected_at=None, agent_version=None, keyboard_protocol=None, timed_keys=False)
            await self.publish()
        return ws

    async def start(self, app):
        self.reaper = asyncio.create_task(self.expire())

    async def expire(self):
        while True:
            await asyncio.sleep(30)
            self.sessions = {k:v for k,v in self.sessions.items() if v['expires'] > time.monotonic()}

    async def shutdown(self, app):
        await asyncio.gather(*(ws.close() for ws in (*self.viewers, *self.agents.values())), return_exceptions=True)

    async def cleanup(self, app):
        self.reaper.cancel()
        await asyncio.gather(self.reaper, return_exceptions=True)
