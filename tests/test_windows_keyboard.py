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
        events.clear()
        physical=[('1','Digit1',0x02),('1','Numpad1',0x4f),('Enter','Enter',0x1c),
                  ('Enter','NumpadEnter',0xe01c),('Control','ControlRight',0xe01d),
                  ('Meta','MetaLeft',0xe05b),('Shift','ShiftRight',0x36)]
        for key,code,scan in physical:
            desktop.input(dict(kind='key',action='down',key=key,code=code))
            desktop.input(dict(kind='key',action='up',key=key,code=code))
        deadline=time.monotonic()+3
        while len(events)<2*len(physical) and time.monotonic()<deadline:
            while user.PeekMessageW(c.byref(message),None,0,0,1):
                user.TranslateMessage(c.byref(message));user.DispatchMessageW(c.byref(message))
            time.sleep(.001)
        assert len(events)==2*len(physical),events
        for index,(_,code,scan) in enumerate(physical):
            down,up=events[index*2:index*2+2]
            assert down[1]==up[1]==scan&255, (code,scan,down,up)
            # Windows normalizes injected right Shift to LLKHF_EXTENDED even
            # though its set-1 scan (0x36) has no E0 prefix. Preserve that scan.
            extended=bool(scan&0xff00) or code=='ShiftRight'
            assert bool(down[2]&1)==bool(up[2]&1)==extended, (code,scan,down,up)
            if code=='ShiftRight':
                assert down[0]==up[0]==0xa1  # Actual VK_RSHIFT, not left Shift.
            assert not down[2]&128 and up[2]&128
        assert not desktop.held_keys
        events.clear()
        # Observed one-ms press times must not acquire the ordinary 20-ms hold.
        from test_timed_keys import sequence
        burst=sequence('001234567890')
        assert desktop.input(burst)
        deadline=time.monotonic()+3
        while len(events)<len(burst['events']) and time.monotonic()<deadline:
            while user.PeekMessageW(c.byref(message),None,0,0,1):
                user.TranslateMessage(c.byref(message));user.DispatchMessageW(c.byref(message))
        assert len(events)==len(burst['events'])
        assert [vk for vk,scan,flags,stamp in events[::2]]==[ord(k) for k in '001234567890']+[13]
        assert all(flags&16 for vk,scan,flags,stamp in events)  # Remains injected, never fake hardware.
        assert events[-1][3]-events[0][3]<.2  # Old path requires >=260 ms.
        assert not desktop.held_keys
    finally:
        user.UnhookWindowsHookEx(hook)
        desktop.close()
