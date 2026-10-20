import base64
import ctypes
import csv
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def _windows_user_sid():
    result = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                            check=True, capture_output=True, text=True,
                            encoding='utf-8', errors='replace',
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                            stdin=subprocess.DEVNULL)
    rows = list(csv.reader(result.stdout.splitlines()))
    if len(rows) != 1 or len(rows[0]) != 2:
        raise RuntimeError('Não foi possível identificar o SID do usuário Windows')
    sid = rows[0][1].strip()
    if not re.fullmatch(r'S-1-\d+(?:-\d+)+', sid):
        raise RuntimeError('O Windows não retornou um SID de usuário válido')
    return sid


def _secure_windows_directory(path):
    sid = _windows_user_sid()
    # Conceder acesso explícito antes de remover herança evita bloquear o dono
    # se o grant falhar. Usar SIDs funciona com contas locais, domínio e nomes
    # traduzidos, sem depender de USERNAME ou getpass.getuser().
    commands = [
        ['icacls', str(path), '/grant:r', f'*{sid}:(OI)(CI)F'],
        ['icacls', str(path), '/grant:r', '*S-1-5-18:(OI)(CI)F'],
        ['icacls', str(path), '/inheritance:r'],
    ]
    for command in commands:
        try:
            subprocess.run(command, check=True, capture_output=True, text=True,
                           encoding='utf-8', errors='replace',
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                            stdin=subprocess.DEVNULL)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or '').strip()
            raise RuntimeError(
                f'Não foi possível proteger a pasta {path}. '
                f'icacls retornou {exc.returncode}: {detail}. '
                'As permissões de segurança não foram ignoradas.'
            ) from exc


def secure_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    # Python da Microsoft Store virtualiza AppData. resolve()/realpath usa o
    # caminho físico que executáveis Windows externos, como icacls, enxergam.
    path = path.resolve(strict=True)
    if os.name == 'nt':
        _secure_windows_directory(path)
    else:
        path.chmod(0o700)
    return path


def atomic_json(path, value):
    path = Path(path)
    path = secure_directory(path.parent) / path.name
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _dpapi(data, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    target = Blob()
    if decrypt:
        ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


def protect(value):
    data = value.encode()
    return {'format': 'dpapi' if os.name == 'nt' else 'private-file',
            'data': base64.b64encode(_dpapi(data) if os.name == 'nt' else data).decode()}


def unprotect(value):
    data = base64.b64decode(value['data'])
    if value['format'] == 'dpapi':
        if os.name != 'nt':
            raise RuntimeError('Credencial DPAPI exige o usuário Windows original')
        data = _dpapi(data, True)
    return data.decode()
