"""Actual global F11 delivery and restoration of a minimized Windows window."""
import ctypes as c
import os
import time
import pytest

@pytest.mark.skipif(os.name != 'nt', reason='Exige janela e hotkey Windows reais')
def test_global_f11_restores_central_window():
    import tkinter as tk
    from smartpdv.central_shortcut import GlobalF11, TITLE, restore_dashboard
    from smartpdv.windows_keyboard import ScanKeyboard
    root = tk.Tk()
    root.title(TITLE+' - teste')
    root.geometry('320x100')
    root.update()
    root.iconify()
    root.update()
    called = []
    def activate():
        called.append(restore_dashboard())
    shortcut = GlobalF11(activate).start()
    try:
        keyboard = ScanKeyboard()
        scan = keyboard.resolve(0x7a)
        keyboard.send(scan, True)
        keyboard.send(scan, False)
        deadline = time.monotonic()+5
        while time.monotonic() < deadline and (not called or root.state() == 'iconic'):
            root.update()
            time.sleep(.01)
        assert called == [True]
        assert root.state() != 'iconic'
        user = c.WinDLL('user32')
        user.GetForegroundWindow.restype = c.c_void_p
        user.GetWindowTextW.argtypes = (c.c_void_p,c.c_wchar_p,c.c_int)
        title = c.create_unicode_buffer(256)
        user.GetWindowTextW(user.GetForegroundWindow(),title,len(title))
        assert title.value.startswith(TITLE)
    finally:
        shortcut.close()
        root.destroy()
    # Unregister on exit: another instance can claim F11 again.
    again = GlobalF11(lambda: None).start()
    again.close()
