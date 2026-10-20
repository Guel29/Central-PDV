"""Diagnóstico de imports do executável sem console, antes de carregar a aplicação."""
import argparse
import importlib
import os
from pathlib import Path
import sys
import traceback


def run(role):
    try:
        entry = importlib.import_module('smartpdv.desktop_entry')
        return entry.launch(role) or 0
    except Exception as exc:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--data',type=Path)
        options,_ = parser.parse_known_args(sys.argv[1:])
        base = Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local'/'share')))
        directory = options.data or base/'SmartPDV'/role
        try:
            directory.mkdir(parents=True,exist_ok=True)
            (directory/'startup-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except OSError:
            pass
        if '--background' not in sys.argv and '--no-browser' not in sys.argv:
            try:
                import tkinter as tk
                from tkinter import messagebox
                root=tk.Tk();root.withdraw()
                messagebox.showerror('Smart PDV',str(exc),parent=root)
                root.destroy()
            except Exception:
                pass
        return 1
