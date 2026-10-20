"""Entradas dos executáveis Windows; configuração explícita, execução sem console."""
import argparse
import os
from pathlib import Path
import ssl
import sys
import threading
import traceback
import time
import urllib.request
import webbrowser

from . import __main__ as cli
from .agent import lan_address
from .storage import load_json


def open_dashboard(directory):
    config = load_json(directory/'central.json')
    host = config['hostname']
    lan_address(host)  # Apenas nomes/IPs locais, inclusive na abertura do navegador.
    address = f'[{host}]' if ':' in host else host
    url = f"https://{address}:{config['port']}"
    context = ssl.create_default_context(cafile=str(directory/'central.crt'))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
    for _ in range(60):
        try:
            with opener.open(url+'/health',timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except (OSError, ValueError):
            time.sleep(1)


def launch(role):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--background',action='store_true')
    parser.add_argument('--data',type=Path)
    parser.add_argument('--no-browser',action='store_true')
    options, remaining = parser.parse_known_args(sys.argv[1:])
    background = options.background
    directory = None
    try:
        if background and (role != 'agent' or remaining not in ([], ['run'])):
            raise ValueError('--background é exclusivo da execução do Agent já configurado')
        base = Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local'/'share')))
        directory = options.data or base/'SmartPDV'/role
        arguments = [a for a in sys.argv[1:] if a not in ('--background','--no-browser')]
        running = remaining in ([],['run'])
        if running and not (directory/f'{role}.json').exists():
            if background:
                return  # Nunca abrir wizard na frente do operador durante o login.
            sys.argv = [sys.argv[0],role,'setup','--data',str(directory)]
            cli.main()
        if role == 'central' and running and not options.no_browser:
            threading.Thread(target=open_dashboard,args=(directory,),daemon=True).start()
        sys.argv = [sys.argv[0],role,*arguments]
        cli.main()
    except (Exception, SystemExit) as exc:
        if isinstance(exc,SystemExit) and exc.code in (None,0):
            return 0
        if directory and directory.is_dir():
            try:
                # Diagnóstico local de inicialização: sem telas, teclas ou tokens.
                (directory/'startup-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
            except OSError:
                pass
        if background or options.no_browser:
            return 1
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror('Smart PDV '+role, str(exc), parent=root)
        finally:
            root.destroy()
        return 1
