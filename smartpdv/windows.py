"""Operações na sessão interativa Windows, sem serviços externos."""
import ctypes
import io
from PIL import ImageGrab
from .windows_keyboard import ScanKeyboard


class Desktop:
    def __init__(self, hotkey=True):
        self.user = ctypes.windll.user32
        self.user.SetProcessDPIAware()
        self.keyboard = ScanKeyboard()
        self.held_keys = {}
        self.held_buttons = set()
        self.hotkey = hotkey
        if hotkey and not self.user.RegisterHotKey(None, 1, 0x4000, 0x7A):
            raise RuntimeError('F11 já está registrado por outro programa')

    def requested(self):
        from ctypes.wintypes import MSG
        message = MSG()
        return bool(self.user.PeekMessageW(ctypes.byref(message), None, 0x0312, 0x0312, 1))

    def capture(self, active):
        image = ImageGrab.grab()
        image.thumbnail((1280, 720) if active else (320, 180))
        out = io.BytesIO()
        image.convert('RGB').save(out, 'JPEG', quality=60 if active else 40)
        return out.getvalue()

    def input(self, event):
        if event['kind'] == 'release':
            return self.release()
        if event['kind'] == 'wheel':
            self.user.mouse_event(0x0800, 0, 0, event['delta'], 0)
            return
        if event['kind'] == 'mouse':
            x = round(event['x'] * (self.user.GetSystemMetrics(0) - 1))
            y = round(event['y'] * (self.user.GetSystemMetrics(1) - 1))
            self.user.SetCursorPos(x, y)
            button = event.get('button', 0)
            if event['action'] in ('down', 'up'):
                down = event['action'] == 'down'
                flags = (2 if down else 4) if button == 0 else (8 if down else 16)
                self.user.mouse_event(flags, 0, 0, 0, 0)
                (self.held_buttons.add if down else self.held_buttons.discard)(button)
        else:
            key = event['key']
            special = {'Enter':13,'Escape':27,'Tab':9,'Backspace':8,'Delete':46,'ArrowLeft':37,
                       'ArrowUp':38,'ArrowRight':39,'ArrowDown':40,'Shift':16,'Control':17,
                       'Alt':18,' ':32,'Home':36,'End':35,'PageUp':33,'PageDown':34}
            vk = special.get(key)
            if key.startswith('F') and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
                vk = 111 + int(key[1:])
            if vk is None and len(key) == 1:
                vk = self.keyboard.character(key)
            if vk is not None:
                down = event['action'] == 'down'
                scan = self.held_keys.get(vk)
                if scan is None:
                    scan = self.keyboard.resolve(vk)
                self.keyboard.send(scan, down)
                if down:
                    self.held_keys[vk] = scan
                else:
                    self.held_keys.pop(vk, None)

    def release(self):
        for scan in self.held_keys.values():
            try:
                self.keyboard.send(scan, False)
            except OSError:
                # A blocked/elevated desktop must not terminate reconnection cleanup.
                pass
        for button in self.held_buttons:
            self.user.mouse_event(4 if button == 0 else 16, 0, 0, 0, 0)
        self.held_keys.clear()
        self.held_buttons.clear()

    def close(self):
        self.release()
        if self.hotkey:
            self.user.UnregisterHotKey(None, 1)
