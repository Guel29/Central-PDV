import base64
import ctypes
import json
import os
from pathlib import Path
import subprocess
import tempfile


def secure_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        import getpass
        subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                        f'{getpass.getuser()}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'],
                       check=True, capture_output=True)
    else:
        path.chmod(0o700)
    return path


def atomic_json(path, value):
    path = Path(path)
    secure_directory(path.parent)
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
