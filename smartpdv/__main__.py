import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import secrets
import sys
import uuid
from aiohttp import web
from .storage import atomic_json, load_json, protect, secure_directory
from .security import create_certificate, password_hash, tls_context, token_hash


def ask(label, secret=False):
    if getattr(sys, 'frozen', False):
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        result = simpledialog.askstring('Smart PDV Control', label, show='*' if secret else None, parent=root)
        root.destroy()
        if result is None:
            raise SystemExit('Configuração cancelada')
        return result.strip()
    return (getpass.getpass(label + ': ') if secret else input(label + ': ')).strip()


def setup_central(directory):
    if (directory / 'central.json').exists():
        raise SystemExit('Central já configurada; use add-pdv para cadastrar novos caixas')
    host = ask('IP ou nome LAN da Central (usado no certificado)')
    name = ask('Nome do supervisor administrador')
    password = ask('Senha do supervisor (mínimo 12 caracteres)', True)
    if len(password) < 12 or not name:
        raise SystemExit('Nome e senha forte obrigatórios')
    fingerprint = create_certificate(directory, host)
    atomic_json(directory / 'central.json', {'host':'0.0.0.0', 'port':8443, 'hostname':host,
        'fingerprint':fingerprint, 'pdvs':[],
        'supervisors':[{'name':name, 'password_hash':password_hash(password), 'control':True}],
        'alarm':{'enabled':True,'repeat_seconds':10}, 'dashboard':{'columns':4},
        'logs':{'retention_days':30,'max_bytes':5000000}})


def add_pdv(directory):
    config = load_json(directory / 'central.json')
    number = int(ask('Número do PDV'))
    if number <= 0 or any(p['number'] == number for p in config['pdvs']):
        raise SystemExit('Número inválido ou já cadastrado')
    identifier = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    config['pdvs'].append({'number':number, 'computer_id':identifier, 'token_hash':token_hash(token)})
    pairing = {'number':number, 'computer_id':identifier, 'central':config['hostname'],
               'port':config['port'], 'fingerprint':config['fingerprint'], 'token':token, 'f11':True}
    # Exportação explícita de pareamento; transferir diretamente por mídia segura.
    export = directory / 'pairing' / f'pdv-{number}.json'
    atomic_json(export, pairing)
    atomic_json(directory / 'central.json', config)
    print('Pareamento criado em', export, '— reinicie a Central após cadastrar.')


def add_supervisor(directory):
    config = load_json(directory / 'central.json')
    name = ask('Nome do supervisor')
    if not name or any(u['name'] == name for u in config['supervisors']):
        raise SystemExit('Nome inválido ou já cadastrado')
    password = ask('Senha (mínimo 12 caracteres)', True)
    if len(password) < 12:
        raise SystemExit('Senha curta demais')
    control = ask('Permitir controle remoto? (s/n)').lower() == 's'
    config['supervisors'].append({'name':name, 'password_hash':password_hash(password), 'control':control})
    atomic_json(directory / 'central.json', config)
    print('Supervisor cadastrado; reinicie a Central.')


def setup_agent(directory):
    if (directory / 'agent.json').exists():
        raise SystemExit('Agent já configurado; preserve ou remova a configuração antes de refazer')
    pairing_path = ask('Caminho do arquivo de pareamento exportado pela Central')
    pairing = load_json(pairing_path)
    host = ask(f"Endereço LAN da Central [{pairing['central']}]") or pairing['central']
    number = int(ask(f"Número do PDV [{pairing['number']}]") or pairing['number'])
    if number != pairing['number']:
        raise SystemExit('Número diferente do cadastro na Central')
    pairing.update(central=host, token=protect(pairing['token']))
    atomic_json(directory / 'agent.json', pairing)
    print('Agent configurado. Exclua o arquivo de pareamento das mídias de transferência.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('role', choices=['central','agent'])
    parser.add_argument('action', nargs='?', default='run', choices=['run','setup','add-pdv','add-supervisor'])
    parser.add_argument('--data', type=Path)
    args = parser.parse_args()
    base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local' / 'share')))
    directory = secure_directory(args.data or base / 'SmartPDV' / args.role)
    if args.action == 'setup':
        return setup_central(directory) if args.role == 'central' else setup_agent(directory)
    if args.action in ('add-pdv', 'add-supervisor'):
        if args.role != 'central':
            parser.error('add-pdv é exclusivo da Central')
        return add_pdv(directory) if args.action == 'add-pdv' else add_supervisor(directory)
    if args.role == 'central':
        from .central import Central
        central = Central(directory)
        web.run_app(central.app, host=central.config['host'], port=central.config['port'], ssl_context=tls_context(directory), print=None)
    else:
        if os.name != 'nt':
            raise SystemExit('Captura, F11 e controle remoto exigem Windows interativo')
        from .agent import Agent
        from .windows import Desktop
        config = load_json(directory / 'agent.json')
        asyncio.run(Agent(directory / 'agent.json', Desktop(config['f11'])).run())


if __name__ == '__main__':
    main()
