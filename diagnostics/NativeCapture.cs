using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO.Ports;
using System.Runtime.InteropServices;
using System.Threading;

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
        [StructLayout(LayoutKind.Sequential)] struct NativeMessage { public IntPtr Window; public uint Message; public UIntPtr Param; public IntPtr Data; public uint Time; public int X, Y; }
        [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
        [DllImport("user32.dll")] static extern bool PeekMessage(out NativeMessage message, IntPtr window, uint minimum, uint maximum, uint remove);
        [DllImport("user32.dll")] static extern int GetMessage(out NativeMessage message, IntPtr window, uint minimum, uint maximum);
        [DllImport("user32.dll")] static extern bool TranslateMessage(ref NativeMessage message);
        [DllImport("user32.dll")] static extern IntPtr DispatchMessage(ref NativeMessage message);
        [DllImport("user32.dll")] static extern bool PostThreadMessage(uint thread, uint message, UIntPtr param, IntPtr data);
        readonly object sync = new object();
        readonly ManualResetEvent ready = new ManualResetEvent(false);
        Thread worker;
        uint workerId;
        volatile bool stopping;
        int hookError, hookCallbacks, rawMessages, rawReadErrors;
        uint initialActivity;
        bool activityAvailable, activitySeen;
        string inputDesktop="unavailable", tokenLevel="unavailable";
        public int EventCount { get { lock(sync)return summary.Events; } }
        readonly Summary summary;
        readonly bool rawMode;
        readonly Stopwatch clock = new Stopwatch();
        readonly Dictionary<IntPtr, int> devices = new Dictionary<IntPtr, int>();
        readonly Hook callback;
        IntPtr hook;
        bool registered;
        public bool Active { get; private set; }
        public bool ObservationFailed { get; private set; }
        public string StopReason { get; private set; }
        public int Elapsed { get { lock (sync) return (int)Math.Min(30000, clock.ElapsedMilliseconds); } }
        public int Keyboards = -1, Hids = -1, SerialPorts = -1;
        public NativeCapture(Summary summary, bool rawMode = false) { this.summary = summary; this.rawMode = rawMode; callback = Observe; }
        public void Start(IntPtr window)
        {
            if (Active || hook != IntPtr.Zero || registered) throw new InvalidOperationException("Capture already active");
            Inventory();
            inputDesktop=CaptureEnvironment.InputDesktop(); tokenLevel=CaptureEnvironment.TokenLevel();
            activityAvailable=CaptureEnvironment.LastActivity(out initialActivity);
            try
            {
                if (rawMode)
                {
                    // Separate collection modes keep both channels independently verifiable.
                    registered = RegisterRawInputDevices(new[] { new RawDevice { Page = 1, Usage = 6, Flags = 0x100, Target = window } }, 1, (uint)Marshal.SizeOf(typeof(RawDevice)));
                    if (!registered) throw new Win32Exception(Marshal.GetLastWin32Error());
                }
                else
                {
                    worker = new Thread(ObserveLoop) { IsBackground = true };
                    worker.SetApartmentState(ApartmentState.STA); worker.Start();
                    if (!ready.WaitOne(5000) || hook == IntPtr.Zero) throw new Win32Exception(hookError);
                }
                lock (sync) { StopReason = "manual"; clock.Restart(); Active = true; }
            }
            catch { Dispose(); throw; }
        }
        void ObserveLoop()
        {
            try
            {
                NativeMessage message;
                workerId = GetCurrentThreadId(); PeekMessage(out message, IntPtr.Zero, 0, 0, 0);
                if (!stopping) hook = SetWindowsHookEx(13, callback, GetModuleHandle(null), 0);
                if (hook == IntPtr.Zero) hookError = Marshal.GetLastWin32Error();
                ready.Set();
                while (!stopping && hook != IntPtr.Zero && GetMessage(out message, IntPtr.Zero, 0, 0) > 0)
                { TranslateMessage(ref message); DispatchMessage(ref message); }
            }
            catch { lock (sync) { ObservationFailed = true; Stop("manual"); } ready.Set(); }
            finally { if (hook != IntPtr.Zero) { UnhookWindowsHookEx(hook); hook = IntPtr.Zero; } }
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
                lock (sync) if (code >= 0 && Collecting())
                {
                    hookCallbacks=Math.Min(1000000,hookCallbacks+1);
                    var data = (KeyboardData)Marshal.PtrToStructure(pointer, typeof(KeyboardData));
                    summary.Add((data.Flags & 0x10) != 0 ? "ll_injected" : "ll_not_injected", data.Key,
                        (data.Flags & 0x80) == 0, (data.Flags & 1) != 0, data.Scan != 0, (data.Flags & 2) != 0,
                        clock.Elapsed.TotalMilliseconds, GetForegroundWindow());
                }
            }
            catch { lock (sync) { ObservationFailed = true; Stop("manual"); } }
            return CallNextHookEx(hook, code, message, pointer);
        }
        public void RawInput(IntPtr handle)
        {
            lock (sync) { if (!rawMode || !Collecting()) return; rawMessages=Math.Min(1000000,rawMessages+1); }
            uint size = 0, headerSize = (uint)Marshal.SizeOf(typeof(RawHeader));
            if (GetRawInputData(handle, 0x10000003, IntPtr.Zero, ref size, headerSize) != 0 || size < headerSize || size > 65536) { RawReadError(); return; }
            IntPtr buffer = Marshal.AllocHGlobal((int)size);
            try
            {
                uint copied = GetRawInputData(handle, 0x10000003, buffer, ref size, headerSize);
                if (copied == uint.MaxValue || copied != size || copied < headerSize + Marshal.SizeOf(typeof(RawKeyboard))) { RawReadError(); return; }
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
                lock (sync) if (Collecting()) summary.Add(source, key.Key, (key.Flags & 1) == 0, (key.Flags & 6) != 0, key.Scan != 0, false,
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
        void RawReadError() { lock(sync)rawReadErrors=Math.Min(1000000,rawReadErrors+1); }
        void Activity()
        {
            uint current;
            if(activityAvailable && CaptureEnvironment.LastActivity(out current) && current!=initialActivity)activitySeen=true;
        }
        public void Tick() { lock (sync) { if(Active)Activity(); Collecting(); } }
        public void Stop(string reason)
        {
            lock (sync) if (Active) { Activity(); Active = false; clock.Stop(); StopReason = reason; }
        }
        public Dictionary<string, object> Report()
        {
            lock(sync) {
                var report=summary.Export(Elapsed,StopReason??"manual",Keyboards,Hids,SerialPorts);
                var health=(Dictionary<string,object>)report["capture_health"];
                if(ObservationFailed)health["status"]="observer_error";
                health["hook_callbacks"]=hookCallbacks; health["raw_messages"]=rawMessages; health["raw_read_errors"]=rawReadErrors;
                health["input_activity"]=!activityAvailable?"unknown":activitySeen?"yes":"no";
                health["input_desktop"]=inputDesktop; health["process_token_level"]=tokenLevel;
                health["hook_thread_alive"]=worker!=null&&worker.IsAlive; health["raw_registration_succeeded"]=registered;
                return report;
            }
        }
        public void Dispose()
        {
            Stop("manual");
            stopping = true;
            if (workerId != 0) PostThreadMessage(workerId, 0x12, UIntPtr.Zero, IntPtr.Zero);
            if (worker != null && worker != Thread.CurrentThread) worker.Join(1000);
            if (registered)
            {
                RegisterRawInputDevices(new[] { new RawDevice { Page = 1, Usage = 6, Flags = 1, Target = IntPtr.Zero } }, 1, (uint)Marshal.SizeOf(typeof(RawDevice)));
                registered = false;
            }
            devices.Clear();
        }
    }
}
