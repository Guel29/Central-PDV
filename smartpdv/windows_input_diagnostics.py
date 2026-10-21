"""Read-only Windows input context: no keys, EAN values, images or credentials."""
import ctypes as c
from pathlib import Path

VERSION = '1.0.4'


class InputContext:
    def __init__(self):
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        self.advapi = c.WinDLL('advapi32', use_last_error=True)
        self.user = c.WinDLL('user32', use_last_error=True)
        self.kernel.GetCurrentProcess.restype = c.c_void_p
        self.kernel.OpenProcess.argtypes = (c.c_uint32, c.c_int, c.c_uint32)
        self.kernel.OpenProcess.restype = c.c_void_p
        self.kernel.CloseHandle.argtypes = (c.c_void_p,)
        self.kernel.QueryFullProcessImageNameW.argtypes = (c.c_void_p,c.c_uint32,c.c_wchar_p,c.POINTER(c.c_uint32))
        self.advapi.OpenProcessToken.argtypes = (c.c_void_p,c.c_uint32,c.POINTER(c.c_void_p))
        self.advapi.GetTokenInformation.argtypes = (c.c_void_p,c.c_int,c.c_void_p,c.c_uint32,c.POINTER(c.c_uint32))
        self.advapi.GetSidSubAuthorityCount.argtypes = (c.c_void_p,)
        self.advapi.GetSidSubAuthorityCount.restype = c.POINTER(c.c_ubyte)
        self.advapi.GetSidSubAuthority.argtypes = (c.c_void_p,c.c_uint32)
        self.advapi.GetSidSubAuthority.restype = c.POINTER(c.c_uint32)
        self.user.GetForegroundWindow.restype = c.c_void_p
        self.user.GetWindowThreadProcessId.argtypes = (c.c_void_p,c.POINTER(c.c_uint32))

    def integrity(self, process):
        token = c.c_void_p()
        if not self.advapi.OpenProcessToken(process, 8, c.byref(token)):
            return None
        try:
            size = c.c_uint32()
            self.advapi.GetTokenInformation(token,25,None,0,c.byref(size))
            if not 0 < size.value <= 65536:
                return None
            buffer = c.create_string_buffer(size.value)
            if not self.advapi.GetTokenInformation(token,25,buffer,size,c.byref(size)):
                return None
            sid = c.cast(buffer,c.POINTER(c.c_void_p))[0]
            count = self.advapi.GetSidSubAuthorityCount(sid)[0]
            return self.advapi.GetSidSubAuthority(sid,count-1)[0] if count else None
        finally:
            self.kernel.CloseHandle(token)

    @staticmethod
    def label(rid):
        if rid is None: return 'unknown'
        if rid >= 0x4000: return 'system'
        if rid >= 0x3000: return 'high'
        if rid >= 0x2000: return 'medium'
        return 'low'

    def process(self, pid):
        handle = self.kernel.OpenProcess(0x1000,False,pid)
        if not handle:
            return '',None,c.get_last_error()
        try:
            name = c.create_unicode_buffer(4096)
            size = c.c_uint32(len(name))
            found = self.kernel.QueryFullProcessImageNameW(handle,0,name,c.byref(size))
            return Path(name.value).name[:120] if found else '',self.integrity(handle),0
        finally:
            self.kernel.CloseHandle(handle)

    def capture(self):
        agent = self.integrity(self.kernel.GetCurrentProcess())
        pid = c.c_uint32()
        self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(),c.byref(pid))
        name,target,error = self.process(pid.value) if pid.value else ('',None,0)
        return {'type':'input_diagnostics','agent_version':VERSION,
                'agent_integrity':self.label(agent),'target_integrity':self.label(target),
                'target_name':name,'target_pid':pid.value,'query_error':max(0,min(65535,error)),
                'comparison':'unknown' if agent is None or target is None else 'agent_lower' if agent < target else 'not_lower'}
