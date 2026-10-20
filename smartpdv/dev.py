"""Laboratório local: Central e Agents reais, com desktops explicitamente simulados."""
import argparse
import asyncio
import getpass
import io
import os
from pathlib import Path
import secrets
import threading
import uuid
import webbrowser

from aiohttp import web
from PIL import Image, ImageDraw
from .agent import Agent
from .central import Central
from .security import create_certificate, password_hash, tls_context, token_hash
from .storage import atomic_json, load_json, protect, secure_directory

WEB = Path(__file__).parent / 'web'


def initialize(directory, password, port=8443):
    directory = secure_directory(directory)
    if (directory / 'central.json').exists():
        config = load_json(directory / 'central.json')
        if not config.get('development_only'):
            raise ValueError('Recusado: este diretório não é exclusivo de desenvolvimento')
        return config
    if len(password) < 8:
        raise ValueError('Escolha uma senha de desenvolvimento com pelo menos 8 caracteres')
    fingerprint = create_certificate(directory, '127.0.0.1')
    config = {'development_only': True, 'host':'127.0.0.1', 'hostname':'127.0.0.1',
              'port':port, 'fingerprint':fingerprint, 'pdvs':[],
              'supervisors':[{'name':'desenvolvimento', 'password_hash':password_hash(password), 'control':True}],
              'alarm':{'enabled':True,'repeat_seconds':10}, 'dashboard':{'columns':3},
              'logs':{'retention_days':7,'max_bytes':1000000}}
    for number in (1, 2):
        identifier, token = str(uuid.uuid4()), secrets.token_urlsafe(32)
        config['pdvs'].append({'number':number, 'computer_id':identifier, 'token_hash':token_hash(token)})
        atomic_json(directory / f'agent-{number}' / 'agent.json', {'number':number, 'computer_id':identifier,
            'central':'127.0.0.1', 'port':port, 'fingerprint':fingerprint, 'token':protect(token), 'f11':True})
    atomic_json(directory / 'central.json', config)
    return config


class SimulatedDesktop:
    def __init__(self, number):
        self.number = number
        self.lock = threading.Lock()
        self.call = False
        self.text = ''
        self.approved = False
        self.cursor = (.5, .5)

    def request(self):
        with self.lock:
            self.call = True

    def requested(self):
        with self.lock:
            result, self.call = self.call, False
            return result

    def input(self, event):
        with self.lock:
            if event['kind'] == 'mouse':
                self.cursor = (event['x'], event['y'])
                if event['action'] == 'down' and .68 <= event['x'] <= .95 and .73 <= event['y'] <= .9:
                    self.approved = True
            elif event['kind'] == 'key' and event['action'] == 'down':
                key = event['key']
                if key == 'Backspace':
                    self.text = self.text[:-1]
                elif len(key) == 1:
                    self.text = (self.text + key)[-60:]
                elif key == 'Enter':
                    self.approved = True

    def release(self):
        pass

    def close(self):
        pass

    def snapshot(self):
        with self.lock:
            return {'number':self.number,'text':self.text,'approved':self.approved,'cursor':self.cursor}

    def capture(self, active):
        state = self.snapshot()
        image = Image.new('RGB', (960, 540), '#0b1524')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((20,20,940,520),radius=20,outline='#eaff38',width=3)
        draw.text((45,45),f'PDV {self.number:02} / DESKTOP SIMULADO',fill='#eaff38',font_size=28)
        draw.text((45,105),'Nao captura nem controla o Windows neste modo.',fill='#a9bed5',font_size=21)
        draw.text((45,165),'VENDA DE TESTE / Caixa aberto',fill='white',font_size=26)
        draw.text((45,225),'TOTAL: R$ 125,90',fill='#68dfff',font_size=32)
        draw.text((45,295),'Teclado recebido: '+state['text'],fill='white',font_size=22)
        draw.rounded_rectangle((653,394,912,486),radius=12,fill='#1d6c36' if state['approved'] else '#39472b')
        draw.text((670,425),'LIBERADO' if state['approved'] else 'LIBERAR TESTE',fill='#deff69',font_size=23)
        x,y=state['cursor']
        draw.ellipse((x*960-5,y*540-5,x*960+5,y*540+5),fill='#4cddff')
        if not active:
            image.thumbnail((320,180))
        output = io.BytesIO()
        image.save(output,'JPEG',quality=65)
        return output.getvalue()


class DevelopmentCentral(Central):
    def __init__(self, directory):
        super().__init__(directory)
        if not self.config.get('development_only') or self.config['host'] != '127.0.0.1':
            raise ValueError('O laboratório só aceita configuração própria e escuta loopback')
        self.desktops = {n:SimulatedDesktop(n) for n in (1,2)}
        self.agent_tasks = {}
        self.app.add_routes([web.get('/dev/operator', self.operator),
                            web.get('/dev/panel.js', self.dev_asset),
                            web.get('/dev/reload.js', self.dev_asset),
                            web.get('/dev/state', self.dev_state),
                            web.get('/dev/version', self.version),
                            web.post('/dev/action', self.action)])
        self.app.on_startup.append(self.start_agents)
        self.app.on_shutdown.insert(0, self.stop_agents)

    async def index(self, request):
        html = (WEB/'index.html').read_text(encoding='utf-8')
        banner = ('<aside class="dev-banner"><strong>LABORATÓRIO · SIMULAÇÃO</strong> '
                  'Central e WebSocket reais; tela, F11 e entrada Windows simulados. '
                  '<a href="/dev/operator" target="_blank" rel="noopener">Abrir Agent simulado ↗</a></aside>')
        html = html.replace('<main>', '<main>'+banner)
        html = html.replace('</head>', '<script src="/dev/reload.js" defer></script></head>')
        return web.Response(text=html,content_type='text/html')

    async def operator(self, request):
        try:
            self.supervisor(request)
        except web.HTTPUnauthorized:
            raise web.HTTPFound('/')
        return web.FileResponse(WEB/'operator.html')

    async def dev_asset(self, request):
        return web.FileResponse(WEB/request.path.rsplit('/',1)[1])

    async def version(self, request):
        self.supervisor(request)
        return web.json_response({'version':sum(p.stat().st_mtime_ns for p in WEB.iterdir() if p.is_file())})

    async def dev_state(self, request):
        self.supervisor(request)
        return web.json_response({'pdvs':[{**desktop.snapshot(),
            'online':self.state[n]['online'], 'active':self.state[n]['active'],
            'pending':self.state[n]['pending']} for n,desktop in self.desktops.items()]})

    async def action(self, request):
        if not self.supervisor(request)['control'] or not self.same_origin(request):
            raise web.HTTPForbidden()
        data = await request.json()
        number = int(data['number'])
        desktop = self.desktops[number]
        action = data['action']
        if action == 'request':
            desktop.request()
        elif action == 'disconnect':
            task = self.agent_tasks.pop(number,None)
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        elif action == 'connect':
            if number not in self.agent_tasks or self.agent_tasks[number].done():
                self.launch_agent(number)
        elif action == 'reset':
            with desktop.lock:
                desktop.text, desktop.approved = '', False
        else:
            raise web.HTTPBadRequest()
        return web.json_response({'ok':True})

    def launch_agent(self, number):
        agent = Agent(self.directory/f'agent-{number}'/'agent.json',self.desktops[number])
        self.agent_tasks[number] = asyncio.create_task(agent.run())

    async def start_agents(self, app):
        # Binding da porta acontece após on_startup; Agents usam reconexão normal.
        for number in self.desktops:
            self.launch_agent(number)

    async def stop_agents(self, app):
        tasks = list(self.agent_tasks.values())
        self.agent_tasks.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--print-data-directory', action='store_true', help='Informar o caminho físico dos dados já preparados')
    parser.add_argument('--prepare', action='store_true', help='Preparar dados e certificado sem iniciar processos')
    parser.add_argument('--open', action='store_true', help='Abrir o navegador deste computador')
    args = parser.parse_args()
    base = Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local'/'share')))
    directory = args.data or base/'SmartPDV'/'development'
    if args.print_data_directory:
        print(directory.resolve(strict=True))
        return
    if (directory/'central.json').exists():
        initialize(directory,'')
    else:
        initialize(directory,getpass.getpass('Crie a senha do laboratório (mínimo 8 caracteres): '))
    directory = directory.resolve(strict=True)
    if args.prepare:
        print('Laboratório preparado em:',directory)
        return
    central = DevelopmentCentral(directory)
    print('LABORATÓRIO: desktops e F11 simulados. Comunicação TLS/WebSocket real.')
    print('Usuário: desenvolvimento. Senha: a escolhida na primeira execução.')
    print('Central: https://127.0.0.1:8443 | Operador: /dev/operator')
    print('Certificado local:',directory/'central.crt')
    print('SHA-256 esperado:',central.config['fingerprint'])
    print('Confie somente neste certificado local verificado. Não desative TLS.')
    if args.open:
        threading.Timer(2,lambda:webbrowser.open('https://127.0.0.1:8443')).start()
    web.run_app(central.app,host='127.0.0.1',port=central.config['port'],ssl_context=tls_context(directory),print=None)


if __name__ == '__main__':
    main()
