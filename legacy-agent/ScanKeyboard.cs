using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

namespace SmartPDV.Legacy
{
    // INPUT must contain the full native union on both x86 (28) and x64 (40).
    static class ScanKeyboard
    {
        [StructLayout(LayoutKind.Sequential)] struct MouseInput
        {
            public int X, Y; public uint Data, Flags, Time; public UIntPtr Extra;
        }
        [StructLayout(LayoutKind.Sequential)] struct KeyboardInput
        {
            public ushort VirtualKey, Scan; public uint Flags, Time; public UIntPtr Extra;
        }
        [StructLayout(LayoutKind.Explicit)] struct InputUnion
        {
            [FieldOffset(0)] public MouseInput Mouse;
            [FieldOffset(0)] public KeyboardInput Keyboard;
        }
        [StructLayout(LayoutKind.Sequential)] struct Input
        {
            public uint Type; public InputUnion Data;
        }
        [DllImport("user32.dll", SetLastError = true)]
        static extern uint SendInput(uint count, Input[] inputs, int size);
        [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, IntPtr process);
        [DllImport("user32.dll")] static extern IntPtr GetKeyboardLayout(uint thread);
        [DllImport("user32.dll")] static extern uint MapVirtualKeyEx(uint key, uint mode, IntPtr layout);
        public static ushort Resolve(byte virtualKey)
        {
            IntPtr layout = GetKeyboardLayout(GetWindowThreadProcessId(GetForegroundWindow(), IntPtr.Zero));
            // MAPVK_VK_TO_VSC_EX includes E0 for navigation and right modifiers.
            uint scan = MapVirtualKeyEx(virtualKey, 4, layout);
            if (scan == 0 || (scan & 0xff00) == 0xe100)
                throw new NotSupportedException("Tecla sem scan code suportado.");
            // Some layouts return the unprefixed keypad scan for navigation VKs.
            // Keep navigation distinct from keypad digits regardless of Num Lock.
            bool extended = (virtualKey >= 0x21 && virtualKey <= 0x28) ||
                virtualKey == 0x2d || virtualKey == 0x2e || virtualKey == 0x5b ||
                virtualKey == 0x5c || virtualKey == 0x5d || virtualKey == 0x6f ||
                virtualKey == 0xa3 || virtualKey == 0xa5;
            if (extended) scan = (scan & 0xff) | 0xe000;
            return (ushort)scan;
        }
        public static void Send(ushort scan, bool down)
        {
            uint flags = 0x0008u; // KEYEVENTF_SCANCODE, wVk must be zero.
            if ((scan & 0xff00) == 0xe000) flags |= 0x0001u;
            if (!down) flags |= 0x0002u;
            var input = new Input { Type = 1, Data = new InputUnion {
                Keyboard = new KeyboardInput { Scan = (ushort)(scan & 0xff), Flags = flags } } };
            if (SendInput(1, new Input[] { input }, Marshal.SizeOf(typeof(Input))) != 1)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows nao aceitou a entrada remota. Verifique as permissoes do Agent e do aplicativo.");
        }
    }
}
