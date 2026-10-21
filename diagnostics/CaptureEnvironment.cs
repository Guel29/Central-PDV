using System;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
namespace SmartPDV.Diagnostics
{
    // Environment health only. No desktop names, user names or key values leave this class.
    static class CaptureEnvironment
    {
        [StructLayout(LayoutKind.Sequential)] struct LastInput { public uint Size, Time; }
        [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LastInput info);
        [DllImport("user32.dll", SetLastError=true)] static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint access);
        [DllImport("user32.dll")] static extern bool CloseDesktop(IntPtr desktop);
        [DllImport("user32.dll")] static extern IntPtr GetThreadDesktop(uint thread);
        [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
        [DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern bool GetUserObjectInformation(IntPtr handle, int index, StringBuilder value, uint length, out uint needed);
        public static bool LastActivity(out uint time)
        {
            var info = new LastInput { Size=(uint)Marshal.SizeOf(typeof(LastInput)) };
            bool ok=GetLastInputInfo(ref info); time=info.Time; return ok;
        }
        static string DesktopName(IntPtr desktop)
        {
            if(desktop==IntPtr.Zero)return null;
            uint needed; var value=new StringBuilder(512);
            return GetUserObjectInformation(desktop,2,value,1024,out needed)?value.ToString():null;
        }
        public static string InputDesktop()
        {
            IntPtr input=OpenInputDesktop(0,false,1);
            if(input==IntPtr.Zero)return "unavailable";
            try {
                string current=DesktopName(GetThreadDesktop(GetCurrentThreadId())), active=DesktopName(input);
                return current==null||active==null?"unavailable":string.Equals(current,active,StringComparison.OrdinalIgnoreCase)?"same":"different";
            } finally { CloseDesktop(input); }
        }
        public static string TokenLevel()
        {
            try { using(var identity=WindowsIdentity.GetCurrent()) return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator)?"administrator":"standard"; }
            catch { return "unavailable"; }
        }
    }
}
