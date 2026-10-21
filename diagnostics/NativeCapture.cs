using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO.Ports;
using System.Runtime.InteropServices;

namespace SmartPDV.Diagnostics
{
    // Passive, manually armed, bounded observer. Always passes keyboard events on.
    sealed class NativeCapture : IDisposable
    {
        delegate IntPtr Hook(int code, IntPtr message, IntPtr data);
        [StructLayout(LayoutKind.Sequential)] struct KeyboardData { public uint Key, Scan, Flags, Time; public UIntPtr Extra; }
        [StructLayout(LayoutKind.Sequential)] struct RawDevice { public ushort Page, Usage; public uint Flags; public IntPtr Target; }
        [StructLayout(LayoutKind.Sequential)] struct RawHeader { public uint Type, Size; public IntPtr Device, Param; }
        [StructLayout(LayoutKind.Sequential)] struct RawKeyboard { public ushort Scan, Flags, Reserved, Key; public uint Message, Extra; }
        [StructLayout(LayoutKind.Sequential)] struct DeviceList { public IntPtr Device; public uint Type; }
        [DllImport("user32.dll", SetLastError = true)] static extern IntPtr SetWindowsHookEx(int id, Hook callback, IntPtr module, uint thread);
        [DllImport("user32.dll")] static extern bool UnhookWindowsHookEx(IntPtr hook);
        [DllImport("user32.dll")] static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr message, IntPtr data);
        [DllImport("kernel32.dll", CharSet = CharSet.Auto)] static extern IntPtr GetModuleHandle(string name);
        [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll", SetLastError = true)] static extern bool RegisterRawInputDevices(RawDevice[] devices, uint count, uint size);
        [DllImport("user32.dll", SetLastError = true)] static extern uint GetRawInputData(IntPtr handle, uint command, IntPtr data, ref uint size, uint headerSize);
        [DllImport("user32.dll", SetLastError = true)] static extern uint GetRawInputDeviceList(IntPtr devices, ref uint count, uint size);
        readonly Summary summary;
        readonly Stopwatch clock = new Stopwatch();
        readonly Dictionary<IntPtr, int> devices = new Dictionary<IntPtr, int>();
        readonly Hook callback;
        IntPtr hook;
        bool registered;
        public bool Active { get; private set; }
        public bool ObservationFailed { get; private set; }
        public string StopReason { get; private set; }
        public int Elapsed { get { return (int)Math.Min(30000, clock.ElapsedMilliseconds); } }
        public int Keyboards = -1, Hids = -1, SerialPorts = -1;
        public NativeCapture(Summary summary) { this.summary = summary; callback = Observe; }
        public void Start(IntPtr window)
        {
            if (Active || hook != IntPtr.Zero || registered) throw new InvalidOperationException("Capture already active");
            Inventory();
            try
            {
                hook = SetWindowsHookEx(13, callback, GetModuleHandle(null), 0);
                if (hook == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
                // RIDEV_INPUTSINK only: NOLEGACY / suppression / exclusivity are never used.
                registered = RegisterRawInputDevices(new[] { new RawDevice { Page = 1, Usage = 6, Flags = 0x100, Target = window } }, 1, (uint)Marshal.SizeOf(typeof(RawDevice)));
                if (!registered) throw new Win32Exception(Marshal.GetLastWin32Error());
                StopReason = "manual"; clock.Restart(); Active = true;
            }
            catch { Dispose(); throw; }
        }
        bool Collecting()
        {
            if (!Active) return false;
            if (clock.ElapsedMilliseconds >= 30000) { Stop("timeout"); return false; }
            if (summary.Events >= Summary.EventLimit) { Stop("event_limit"); return false; }
            return true;
        }
        IntPtr Observe(int code, IntPtr message, IntPtr pointer)
        {
            try
            {
                if (code >= 0 && Collecting())
                {
                    var data = (KeyboardData)Marshal.PtrToStructure(pointer, typeof(KeyboardData));
                    summary.Add((data.Flags & 0x10) != 0 ? "ll_injected" : "ll_not_injected", data.Key,
                        (data.Flags & 0x80) == 0, (data.Flags & 1) != 0, data.Scan != 0, (data.Flags & 2) != 0,
                        clock.Elapsed.TotalMilliseconds, GetForegroundWindow());
                }
            }
            catch { ObservationFailed = true; Stop("manual"); }
            return CallNextHookEx(hook, code, message, pointer);
        }
        public void RawInput(IntPtr handle)
        {
            if (!Collecting()) return;
            uint size = 0, headerSize = (uint)Marshal.SizeOf(typeof(RawHeader));
            if (GetRawInputData(handle, 0x10000003, IntPtr.Zero, ref size, headerSize) != 0 || size < headerSize || size > 65536) return;
            IntPtr buffer = Marshal.AllocHGlobal((int)size);
            try
            {
                uint copied = GetRawInputData(handle, 0x10000003, buffer, ref size, headerSize);
                if (copied == uint.MaxValue || copied != size || copied < headerSize + Marshal.SizeOf(typeof(RawKeyboard))) return;
                var header = (RawHeader)Marshal.PtrToStructure(buffer, typeof(RawHeader));
                if (header.Type != 1) return; // Never decode HID reports or translate to text.
                var key = (RawKeyboard)Marshal.PtrToStructure(IntPtr.Add(buffer, (int)headerSize), typeof(RawKeyboard));
                if (key.Key == 255) return; // Fake key / keyboard overrun, not a valid key event.
                string source = "raw_keyboard_no_device";
                if (header.Device != IntPtr.Zero)
                {
                    int device;
                    if (!devices.TryGetValue(header.Device, out device))
                    {
                        if (devices.Count >= 16) return;
                        devices[header.Device] = device = devices.Count + 1;
                    }
                    source = "raw_keyboard_" + device;
                }
                summary.Add(source, key.Key, (key.Flags & 1) == 0, (key.Flags & 6) != 0, key.Scan != 0, false,
                    clock.Elapsed.TotalMilliseconds, GetForegroundWindow());
            }
            finally { Marshal.FreeHGlobal(buffer); }
        }
        void Inventory()
        {
            try { SerialPorts = SerialPort.GetPortNames().Length; } catch { SerialPorts = -1; }
            uint count = 0, stride = (uint)Marshal.SizeOf(typeof(DeviceList));
            if (GetRawInputDeviceList(IntPtr.Zero, ref count, stride) == uint.MaxValue || count > 4096) return;
            if (count == 0) { Keyboards = Hids = 0; return; }
            IntPtr list = Marshal.AllocHGlobal(checked((int)(count * stride)));
            try
            {
                uint received = GetRawInputDeviceList(list, ref count, stride);
                if (received == uint.MaxValue) return;
                Keyboards = Hids = 0;
                for (int i = 0; i < received; i++)
                {
                    var item = (DeviceList)Marshal.PtrToStructure(IntPtr.Add(list, i * (int)stride), typeof(DeviceList));
                    if (item.Type == 1) Keyboards++;
                    if (item.Type == 2) Hids++;
                }
            }
            finally { Marshal.FreeHGlobal(list); }
        }
        public void Tick() { Collecting(); }
        public void Stop(string reason)
        {
            if (Active) { Active = false; clock.Stop(); StopReason = reason; }
        }
        public Dictionary<string, object> Report() { return summary.Export(Elapsed, StopReason ?? "manual", Keyboards, Hids, SerialPorts); }
        public void Dispose()
        {
            Stop("manual");
            if (hook != IntPtr.Zero) { UnhookWindowsHookEx(hook); hook = IntPtr.Zero; }
            if (registered)
            {
                RegisterRawInputDevices(new[] { new RawDevice { Page = 1, Usage = 6, Flags = 1, Target = IntPtr.Zero } }, 1, (uint)Marshal.SizeOf(typeof(RawDevice)));
                registered = false;
            }
            devices.Clear();
        }
    }
}
