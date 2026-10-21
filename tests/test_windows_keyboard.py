"""Observe actual Windows keyboard events. Hook is test-only, never shipped."""
import ctypes as c
import os
import time
import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Exige entrada nativa Windows')


def test_native_desktop_scan_codes_and_release():
    from ctypes.wintypes import MSG
    from smartpdv.windows import Desktop
    from smartpdv.windows_keyboard import Input
    assert c.sizeof(Input) == (40 if c.sizeof(c.c_void_p) == 8 else 28)
    class KeyboardData(c.Structure):
        _fields_ = [('vk', c.c_uint32), ('scan', c.c_uint32), ('flags', c.c_uint32),
                    ('time', c.c_uint32), ('extra', c.c_size_t)]
    user = c.WinDLL('user32', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    callback_type = c.WINFUNCTYPE(c.c_ssize_t, c.c_int, c.c_size_t, c.c_ssize_t)
    user.SetWindowsHookExW.argtypes = (c.c_int, callback_type, c.c_void_p, c.c_uint32)
    user.SetWindowsHookExW.restype = c.c_void_p
    user.CallNextHookEx.argtypes = (c.c_void_p, c.c_int, c.c_size_t, c.c_ssize_t)
    user.CallNextHookEx.restype = c.c_ssize_t
    user.UnhookWindowsHookEx.argtypes = (c.c_void_p,)
    kernel.GetModuleHandleW.argtypes = (c.c_wchar_p,)
    kernel.GetModuleHandleW.restype = c.c_void_p
    events = []
    @callback_type
    def callback(code, message, pointer):
        if code >= 0:
            data = c.cast(pointer, c.POINTER(KeyboardData)).contents
            if data.flags & 16:
                events.append((data.vk, data.scan, data.flags, time.perf_counter()))
                return 1  # Swallow synthetic CI input instead of typing into other apps.
        return user.CallNextHookEx(None, code, message, pointer)
    hook = user.SetWindowsHookExW(13, callback, kernel.GetModuleHandleW(None), 0)
    assert hook, c.get_last_error()
    desktop = Desktop(hotkey=False)
    try:
        keys = list('7890123456789') + ['Enter', 'ArrowLeft', 'Control']
        for key in keys:
            desktop.input(dict(kind='key', action='down', key=key))
            if key != 'Control':
                desktop.input(dict(kind='key', action='up', key=key))
        desktop.release()  # End/disconnect must release the held modifier.
        message = MSG()
        deadline = time.monotonic() + 3
        while len(events) < 2*len(keys) and time.monotonic() < deadline:
            while user.PeekMessageW(c.byref(message), None, 0, 0, 1):
                user.TranslateMessage(c.byref(message))
                user.DispatchMessageW(c.byref(message))
            time.sleep(.001)
        # Low-level hooks report VK_LCONTROL for the generic Control scan.
        expected = [ord(k) for k in keys[:13]] + [13,37,0xa2]
        assert len(events) == 2*len(keys), events
        for index, vk in enumerate(expected):
            down, up = events[index*2:index*2+2]
            assert down[0] == up[0] == vk
            assert down[1] == up[1] != 0
            assert not down[2] & 128 and up[2] & 128
            assert up[3]-down[3] >= .019
        assert events[-4][2] & 1 and events[-3][2] & 1  # Extended left arrow.
        assert not desktop.held_keys
    finally:
        user.UnhookWindowsHookEx(hook)
        desktop.close()


def test_native_input_context_reads_actual_process_token():
    from smartpdv.windows_input_diagnostics import InputContext, VERSION
    context=InputContext()
    agent=context.integrity(context.kernel.GetCurrentProcess())
    assert agent is not None
    name,level,error=context.process(os.getpid())
    assert level==agent and error==0
    assert name.lower().endswith('.exe') and '/' not in name and '\\' not in name
    result=context.capture()
    assert result['agent_version']==VERSION
    assert result['agent_integrity']!='unknown'
    assert set(result)=={'type','agent_version','agent_integrity','target_integrity','target_name','target_pid','query_error','comparison'}
