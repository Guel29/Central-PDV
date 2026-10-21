import argparse
import asyncio
import getpass
import json
import subprocess
import os
from pathlib import Path
import secrets
import sys
import uuid
import socket
from aiohttp import web
from .storage import atomic_json, load_json, protect, secure_directory
from .security import create_certificate, tls_context, token_hash


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
    fingerprint = create_certificate(directory, host)
    atomic_json(directory / 'central.json', {'host':'0.0.0.0', 'port':8443, 'hostname':host,
        'fingerprint':fingerprint, 'pdvs':[],
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


def reissue_pairing(directory):
    config = load_json(directory / 'central.json')
    number = int(ask('Número do PDV para gerar novo pareamento (substitui sua credencial; será necessário configurar novamente esse PDV)'))
    pdv = next((p for p in config['pdvs'] if p['number'] == number), None)
    if number <= 0 or pdv is None:
        raise SystemExit('PDV não cadastrado. Use Cadastrar PDV para um novo caixa.')
    # Hold the listening port until the two writes finish. Never rotate a key
    # while a running Central still accepts the previous in-memory credential.
    family = socket.AF_INET6 if ':' in config['host'] else socket.AF_INET
    address = (config['host'], config['port'])
    with socket.socket(family, socket.SOCK_STREAM) as guard:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            guard.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            guard.bind(address)
        except OSError:
            raise SystemExit('Feche a Central antes de gerar novo pareamento. Se já fechou, verifique se a porta configurada está ocupada.') from None
        # Re-read after acquiring the port, preserving current registrations.
        config = load_json(directory / 'central.json')
        if (config['host'], config['port']) != address:
            raise SystemExit('A configuração de rede mudou. Tente gerar o pareamento novamente.')
        pdv = next((p for p in config['pdvs'] if p['number'] == number), None)
        if pdv is None:
            raise SystemExit('PDV não cadastrado.')
        token = secrets.token_urlsafe(32)
        pairing = {'number':number, 'computer_id':pdv['computer_id'], 'central':config['hostname'],
                   'port':config['port'], 'fingerprint':config['fingerprint'], 'token':token, 'f11':True}
        export = directory / 'pairing' / f'pdv-{number}.json'
        # Export first: a failed config write must not invalidate the old Agent.
        atomic_json(export, pairing)
        pdv['token_hash'] = token_hash(token)
        try:
            atomic_json(directory / 'central.json', config)
        except Exception:
            export.unlink(missing_ok=True)  # Do not leave an unactivated pairing.
            raise
    message = (f'Novo pareamento do PDV {number} salvo em:\n{export}\n\n'
               'A credencial anterior desse PDV foi substituída. Preserve uma cópia do agent.json antigo, '
               'remova-o da pasta ativa com o Agent fechado e use Configurar PDV para importar este arquivo. '
               'Depois inicie a Central e o Agent. Os outros PDVs mantêm seus cadastros.')
    if getattr(sys, 'frozen', False):
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showinfo('Novo pareamento de PDV', message, parent=root)
        finally:
            root.destroy()
    else:
        print(message)
    return export


def trust_certificate(directory):
    if os.name != 'nt':
        raise SystemExit('A instalação de confiança deste comando exige Windows')
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    config = load_json(directory / 'central.json')
    certificate = directory / 'central.crt'
    actual = x509.load_pem_x509_certificate(certificate.read_bytes()).fingerprint(hashes.SHA256()).hex()
    if not secrets.compare_digest(actual, config['fingerprint']):
        raise SystemExit('Certificado diferente do cadastro. Confiança não alterada.')
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        if not messagebox.askyesno('Certificado da Central local',
            'Adicionar à confiança deste usuário Windows o certificado local da Central?\n'
            'Isso permite abrir o dashboard HTTPS neste computador.\nSHA-256: ' + actual, parent=root):
            return
        subprocess.run(['certutil', '-user', '-addstore', 'Root', str(certificate)], check=True, capture_output=True)
        messagebox.showinfo('Smart PDV', 'Certificado local instalado para este usuário.', parent=root)
    finally:
        root.destroy()


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
    parser.add_argument('action', nargs='?', default='run', choices=['run','setup','add-pdv','reissue-pairing','trust-certificate','check-config'])
    parser.add_argument('--data', type=Path)
    args = parser.parse_args()
    base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local' / 'share')))
    directory = secure_directory(args.data or base / 'SmartPDV' / args.role)
    if args.action == 'setup':
        return setup_central(directory) if args.role == 'central' else setup_agent(directory)
    if args.action == 'check-config':
        if args.role != 'agent':
            parser.error('check-config é exclusivo do Agent')
        from .storage import unprotect
        config = load_json(directory / 'agent.json')
        unprotect(config['token'])
        print('Cadastro do PDV e credencial Windows disponíveis.')
        return
    if args.action == 'trust-certificate':
        if args.role != 'central':
            parser.error('trust-certificate é exclusivo da Central')
        return trust_certificate(directory)
    if args.action == 'add-pdv':
        if args.role != 'central':
            parser.error('add-pdv é exclusivo da Central')
        return add_pdv(directory)
    if args.action == 'reissue-pairing':
        if args.role != 'central':
            parser.error('reissue-pairing é exclusivo da Central')
        reissue_pairing(directory)
        return
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
        asyncio.run(Agent(directory / 'agent.json', Desktop(config['f11'], config.get('keyboard_min_press_ms', 20))).run())


if __name__ == '__main__':
    main()
