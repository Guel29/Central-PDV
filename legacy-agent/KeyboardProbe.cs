// CI only: observe actual Windows keyboard injection with a low-level hook.
// Never included in the installed Agent; never records operator input.
using System;
using System.Diagnostics;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Windows.Forms;
namespace SmartPDV.Legacy
{
    static class KeyboardProbe
    {
        delegate IntPtr Hook(int code, IntPtr message, IntPtr data);
        [StructLayout(LayoutKind.Sequential)] struct KeyboardData
        { public uint Key, Scan, Flags, Time; public UIntPtr Extra; }
        [DllImport("user32.dll", SetLastError=true)] static extern IntPtr SetWindowsHookEx(int id, Hook callback, IntPtr module, uint thread);
        [DllImport("user32.dll")] static extern bool UnhookWindowsHookEx(IntPtr hook);
        [DllImport("user32.dll")] static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr message, IntPtr data);
        [DllImport("kernel32.dll", CharSet=CharSet.Auto)] static extern IntPtr GetModuleHandle(string name);
        [STAThread] static int Main()
        {
            var events = new List<KeyboardData>();
            var times = new List<long>();
            Hook callback = delegate(int code, IntPtr message, IntPtr data) {
                if (code >= 0) {
                    var item = (KeyboardData)Marshal.PtrToStructure(data, typeof(KeyboardData));
                    if ((item.Flags & 16) != 0) { events.Add(item); times.Add(Stopwatch.GetTimestamp()); return new IntPtr(1); }
                }
                return CallNextHookEx(IntPtr.Zero, code, message, data);
            };
            IntPtr handle = SetWindowsHookEx(13, callback, GetModuleHandle(null), 0);
            if (handle == IntPtr.Zero) throw new Exception("Cannot install CI keyboard hook");
            try
            {
                // EAN-13 digits, Enter and an extended navigation key. Swallowed by hook.
                byte[] keys = { 0x37,0x38,0x39,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,0x39,0x35,0x0d,0x25 };
                foreach (byte key in keys)
                {
                    ushort scan = ScanKeyboard.Resolve(key);
                    ScanKeyboard.Send(scan,true); ScanKeyboard.Send(scan,false);
                    Application.DoEvents();
                }
                DateTime deadline=DateTime.UtcNow.AddSeconds(3);
                while(events.Count < keys.Length*2 && DateTime.UtcNow < deadline) Application.DoEvents();
                if(events.Count != keys.Length*2) throw new Exception("Missing scan code events: "+events.Count);
                for(int i=0;i<keys.Length;i++)
                {
                    var down=events[i*2]; var up=events[i*2+1];
                    if ((times[i*2+1]-times[i*2])*1000.0/Stopwatch.Frequency < 19)
                        throw new Exception("Keyboard press too short at "+i);
                    if(down.Key!=keys[i] || up.Key!=keys[i] || down.Scan==0 || down.Scan!=up.Scan ||
                       (down.Flags&128)!=0 || (up.Flags&128)==0)
                        throw new Exception("Invalid keyboard down/up at "+i);
                }
                if((events[events.Count-1].Flags&1)==0) throw new Exception("Missing extended flag");
                events.Clear(); times.Clear();
                string[] codes={"Digit1","Numpad1","Enter","NumpadEnter","ControlRight","MetaLeft","ShiftRight"};
                string[] names={"1","1","Enter","Enter","Control","Meta","Shift"};
                ushort[] scans={0x02,0x4f,0x1c,0xe01c,0xe01d,0xe05b,0x36};
                var desktop=new Desktop();
                for(int i=0;i<codes.Length;i++)
                {
                    desktop.Input(new Dictionary<string,object>{{"kind","key"},{"action","down"},{"key",names[i]},{"code",codes[i]}});
                    desktop.Release();
                    Application.DoEvents();
                }
                deadline=DateTime.UtcNow.AddSeconds(3);
                while(events.Count<codes.Length*2 && DateTime.UtcNow<deadline) Application.DoEvents();
                if(events.Count!=codes.Length*2) throw new Exception("Missing physical keyboard events");
                for(int i=0;i<scans.Length;i++)
                {
                    var down=events[i*2];var up=events[i*2+1];
                    if(down.Scan!=(uint)(scans[i]&255) || up.Scan!=down.Scan ||
                       ((down.Flags&1)!=0)!=((scans[i]&0xff00)!=0) || ((up.Flags&1)!=0)!=((scans[i]&0xff00)!=0) ||
                       (down.Flags&128)!=0 || (up.Flags&128)==0)
                        throw new Exception("Physical scan code mismatch: "+codes[i]+" expected="+scans[i].ToString("x")+" down="+down.Key.ToString("x")+"/"+down.Scan.ToString("x")+"/"+down.Flags.ToString("x")+" up="+up.Key.ToString("x")+"/"+up.Scan.ToString("x")+"/"+up.Flags.ToString("x"));
                }
                Console.WriteLine("PASS Windows SendInput: EAN, physical keypad vs top-row, Enter vs keypad Enter, sided modifiers, Windows key and release");
                return 0;
            }
            finally { UnhookWindowsHookEx(handle); GC.KeepAlive(callback); }
        }
    }
}
