"""F11 global da Central na sessao Windows interativa."""
import ctypes as c
from ctypes.wintypes import MSG
import os
from pathlib import Path
import subprocess
import threading
import time
import webbrowser

TITLE = 'SmartCentral — Smart PDV Control'


class GlobalF11:
    def __init__(self, callback):
        self.callback = callback
        self.ready = threading.Event()
        self.error = None
        self.thread_id = 0
        self.thread = threading.Thread(target=self._run, name='SmartCentral-F11', daemon=True)

    def start(self):
        self.thread.start()
        if not self.ready.wait(5):
            raise RuntimeError('Inicializacao do atalho F11 expirou')
        if self.error:
            raise self.error
        return self

    def _run(self):
        user = c.WinDLL('user32', use_last_error=True)
        kernel = c.WinDLL('kernel32', use_last_error=True)
        self.thread_id = kernel.GetCurrentThreadId()
        message = MSG()
        user.PeekMessageW(c.byref(message), None, 0, 0, 0)
        if not user.RegisterHotKey(None, 1, 0x4000, 0x7a):
            self.error = RuntimeError('F11 ja esta em uso por outro programa nesta sessao Windows')
            self.ready.set()
            return
        self.ready.set()
        try:
            while user.GetMessageW(c.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312 and message.wParam == 1:
                    try:
                        self.callback()
                    except OSError:
                        pass
        finally:
            user.UnregisterHotKey(None, 1)

    def close(self):
        if self.thread.is_alive():
            c.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
            self.thread.join(3)


def restore_dashboard():
    user = c.WinDLL('user32', use_last_error=True)
    user.GetWindowTextLengthW.argtypes = (c.c_void_p,)
    user.GetWindowTextW.argtypes = (c.c_void_p, c.c_wchar_p, c.c_int)
    user.IsWindowVisible.argtypes = (c.c_void_p,)
    user.IsIconic.argtypes = (c.c_void_p,)
    user.ShowWindow.argtypes = (c.c_void_p, c.c_int)
    user.SetForegroundWindow.argtypes = (c.c_void_p,)
    user.FlashWindow.argtypes = (c.c_void_p, c.c_int)
    callback_type = c.WINFUNCTYPE(c.c_int, c.c_void_p, c.c_ssize_t)
    user.EnumWindows.argtypes = (callback_type, c.c_ssize_t)
    found = []
    @callback_type
    def visit(window, parameter):
        if user.IsWindowVisible(window):
            title = c.create_unicode_buffer(user.GetWindowTextLengthW(window)+1)
            user.GetWindowTextW(window, title, len(title))
            if title.value.startswith(TITLE):
                found.append(window)
                return 0
        return 1
    user.EnumWindows(visit, 0)
    if not found:
        return False
    window = found[0]
    user.ShowWindow(window, 9 if user.IsIconic(window) else 5)
    if not user.SetForegroundWindow(window):
        user.FlashWindow(window, True)
    return True


def app_browser():
    import winreg
    for name in ('msedge.exe', 'chrome.exe'):
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\'+name,
                                        0, winreg.KEY_READ | view) as key:
                        path = Path(winreg.QueryValue(key, None).strip('"'))
                        if path.is_file():
                            return path
                except OSError:
                    pass
    for variable in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
        for relative in ('Microsoft/Edge/Application/msedge.exe', 'Google/Chrome/Application/chrome.exe'):
            path = Path(os.environ.get(variable, ''))/relative
            if path.is_file():
                return path
    return None


class DashboardWindow:
    def __init__(self, url):
        self.url = url
        self.lock = threading.Lock()
        self.last_open = 0

    def activate(self):
        with self.lock:
            if restore_dashboard():
                return
            if time.monotonic()-self.last_open < 3:
                return
            browser = app_browser()
            if browser:
                # An app window keeps the dashboard identifiable even with other tabs open.
                subprocess.Popen([str(browser), '--app='+self.url], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                webbrowser.open(self.url)
            self.last_open = time.monotonic()
