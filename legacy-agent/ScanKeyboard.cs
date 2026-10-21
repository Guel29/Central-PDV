using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using System.ComponentModel;
using System.Runtime.InteropServices;

namespace SmartPDV.Legacy
{
    // INPUT must contain the full native union on both x86 (28) and x64 (40).
    static class ScanKeyboard
    {
        public static int MinimumPressMilliseconds = 20;
        static readonly object Sync = new object();
        static readonly Dictionary<ushort,long> Pressed = new Dictionary<ushort,long>();
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
        [DllImport("kernel32.dll")] static extern void SetLastError(uint code);
        [DllImport("user32.dll", SetLastError = true)]
        static extern uint SendInput(uint count, Input[] inputs, int size);
        [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, IntPtr process);
        [DllImport("user32.dll")] static extern IntPtr GetKeyboardLayout(uint thread);
        [DllImport("user32.dll")] static extern uint MapVirtualKeyEx(uint key, uint mode, IntPtr layout);
        static readonly Dictionary<string,ushort> Physical = BuildPhysical();
        static Dictionary<string,ushort> BuildPhysical()
        {
            var result = new Dictionary<string,ushort> {
                {"Escape",0x01},{"Backspace",0x0e},{"Tab",0x0f},{"Enter",0x1c},
                {"ControlLeft",0x1d},{"ControlRight",0xe01d},{"ShiftLeft",0x2a},{"ShiftRight",0x36},
                {"AltLeft",0x38},{"AltRight",0xe038},{"MetaLeft",0xe05b},{"MetaRight",0xe05c},
                {"ContextMenu",0xe05d},{"Space",0x39},{"CapsLock",0x3a},
                {"Minus",0x0c},{"Equal",0x0d},{"BracketLeft",0x1a},{"BracketRight",0x1b},
                {"Backslash",0x2b},{"Semicolon",0x27},{"Quote",0x28},{"Backquote",0x29},
                {"Comma",0x33},{"Period",0x34},{"Slash",0x35},{"IntlBackslash",0x56},
                {"Home",0xe047},{"ArrowUp",0xe048},{"PageUp",0xe049},{"ArrowLeft",0xe04b},
                {"ArrowRight",0xe04d},{"End",0xe04f},{"ArrowDown",0xe050},{"PageDown",0xe051},
                {"Insert",0xe052},{"Delete",0xe053},{"NumLock",0x45},{"ScrollLock",0x46},
                {"NumpadMultiply",0x37},{"NumpadSubtract",0x4a},{"NumpadAdd",0x4e},
                {"NumpadDecimal",0x53},{"NumpadDivide",0xe035},{"NumpadEnter",0xe01c},
                {"F11",0x57},{"F12",0x58}
            };
            ushort[] digits = {0x0b,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0a};
            ushort[] numpad = {0x52,0x4f,0x50,0x51,0x4b,0x4c,0x4d,0x47,0x48,0x49};
            ushort[] letters = {0x1e,0x30,0x2e,0x20,0x12,0x21,0x22,0x23,0x17,0x24,0x25,0x26,0x32,
                0x31,0x18,0x19,0x10,0x13,0x1f,0x14,0x16,0x2f,0x11,0x2d,0x15,0x2c};
            for(int i=0;i<10;i++) {result.Add("Digit"+i,digits[i]);result.Add("Numpad"+i,numpad[i]);}
            for(int i=0;i<26;i++) result.Add("Key"+(char)('A'+i),letters[i]);
            for(int i=1;i<=10;i++) result.Add("F"+i,(ushort)(0x3a+i));
            return result;
        }
        public static bool TryPhysical(string code, out ushort scan)
        {
            scan=0;
            return code!=null && Physical.TryGetValue(code,out scan);
        }
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
        public static void Send(ushort scan, bool down, bool preserveTiming = false)
        {
            lock (Sync)
            {
            long started;
            if (!preserveTiming && !down && Pressed.TryGetValue(scan, out started))
            {
                while (true)
                {
                    double remaining = MinimumPressMilliseconds - (Stopwatch.GetTimestamp()-started)*1000.0/Stopwatch.Frequency;
                    if (remaining <= 0) break;
                    Thread.Sleep((int)Math.Ceiling(remaining));
                }
            }
            uint flags = 0x0008u; // KEYEVENTF_SCANCODE, wVk must be zero.
            if ((scan & 0xff00) == 0xe000) flags |= 0x0001u;
            if (!down) flags |= 0x0002u;
            var input = new Input { Type = 1, Data = new InputUnion {
                Keyboard = new KeyboardInput { Scan = (ushort)(scan & 0xff), Flags = flags } } };
            SetLastError(0);
            if (SendInput(1, new Input[] { input }, Marshal.SizeOf(typeof(Input))) != 1)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows nao aceitou a entrada remota. Verifique as permissoes do Agent e do aplicativo.");
            if (down) { if (!Pressed.ContainsKey(scan)) Pressed[scan] = Stopwatch.GetTimestamp(); }
            else Pressed.Remove(scan);
            }
        }
    }
}
