"""Entrada nativa por scan codes; sem redirecionamento de dispositivos."""
import ctypes as c
import time


class MouseInput(c.Structure):
    _fields_ = [('x', c.c_int32), ('y', c.c_int32), ('data', c.c_uint32),
                ('flags', c.c_uint32), ('time', c.c_uint32), ('extra', c.c_size_t)]


class KeyboardInput(c.Structure):
    _fields_ = [('vk', c.c_uint16), ('scan', c.c_uint16), ('flags', c.c_uint32),
                ('time', c.c_uint32), ('extra', c.c_size_t)]


class InputUnion(c.Union):
    _fields_ = [('mouse', MouseInput), ('keyboard', KeyboardInput)]


class Input(c.Structure):
    _fields_ = [('type', c.c_uint32), ('data', InputUnion)]


class ScanKeyboard:
    def __init__(self, minimum_press_ms=20):
        if type(minimum_press_ms) is not int or not 0 <= minimum_press_ms <= 100:
            raise ValueError('keyboard_min_press_ms deve estar entre 0 e 100')
        self.minimum_press = minimum_press_ms / 1000
        self.pressed = {}
        self.user = c.WinDLL('user32', use_last_error=True)
        self.user.SendInput.argtypes = (c.c_uint32, c.POINTER(Input), c.c_int)
        self.user.SendInput.restype = c.c_uint32
        self.user.GetForegroundWindow.restype = c.c_void_p
        self.user.GetWindowThreadProcessId.argtypes = (c.c_void_p, c.POINTER(c.c_uint32))
        self.user.GetWindowThreadProcessId.restype = c.c_uint32
        self.user.GetKeyboardLayout.argtypes = (c.c_uint32,)
        self.user.GetKeyboardLayout.restype = c.c_void_p
        self.user.MapVirtualKeyExW.argtypes = (c.c_uint32, c.c_uint32, c.c_void_p)
        self.user.MapVirtualKeyExW.restype = c.c_uint32
        self.user.VkKeyScanExW.argtypes = (c.c_wchar, c.c_void_p)
        self.user.VkKeyScanExW.restype = c.c_short

    def layout(self):
        thread = self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(), None)
        return self.user.GetKeyboardLayout(thread)

    def character(self, key):
        code = self.user.VkKeyScanExW(key, self.layout())
        return code & 255 if code != -1 else None

    def resolve(self, vk):
        scan = self.user.MapVirtualKeyExW(vk, 4, self.layout())
        if not scan or scan & 0xff00 == 0xe100:
            raise ValueError('Tecla sem scan code suportado')
        # Navigation must remain separate from keypad digits across layouts.
        if 0x21 <= vk <= 0x28 or vk in (0x2d, 0x2e, 0x5b, 0x5c, 0x5d, 0x6f, 0xa3, 0xa5):
            scan = scan & 0xff | 0xe000
        return scan

    def send(self, scan, down):
        if not down and scan in self.pressed:
            remaining = self.minimum_press - (time.monotonic() - self.pressed[scan])
            if remaining > 0:
                time.sleep(remaining)
        flags = 0x0008 | (1 if scan & 0xff00 == 0xe000 else 0) | (0 if down else 2)
        packet = Input(type=1, data=InputUnion(keyboard=KeyboardInput(scan=scan & 255, flags=flags)))
        if self.user.SendInput(1, c.byref(packet), c.sizeof(Input)) != 1:
            raise OSError(c.get_last_error(), 'Windows recusou a entrada remota; verifique as permissoes do Agent e do aplicativo')
        if down:
            self.pressed.setdefault(scan, time.monotonic())
        else:
            self.pressed.pop(scan, None)
