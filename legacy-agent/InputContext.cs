// Read-only token/process facts. No key capture, screenshots or credentials.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
namespace SmartPDV.Legacy
{
    static class InputContext
    {
        [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
        [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
        [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern bool QueryFullProcessImageName(IntPtr handle,uint flags,StringBuilder name,ref uint length);
        [DllImport("advapi32.dll", SetLastError=true)] static extern bool OpenProcessToken(IntPtr process,uint access,out IntPtr token);
        [DllImport("advapi32.dll", SetLastError=true)] static extern bool GetTokenInformation(IntPtr token,int kind,IntPtr info,uint size,out uint needed);
        [DllImport("advapi32.dll")] static extern IntPtr GetSidSubAuthorityCount(IntPtr sid);
        [DllImport("advapi32.dll")] static extern IntPtr GetSidSubAuthority(IntPtr sid,uint index);
        [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window,out uint pid);
        static int? Integrity(IntPtr process)
        {
            IntPtr token;
            if(!OpenProcessToken(process,8,out token)) return null;
            try
            {
                uint needed;
                GetTokenInformation(token,25,IntPtr.Zero,0,out needed);
                if(needed==0 || needed>65536) return null;
                IntPtr data=Marshal.AllocHGlobal((int)needed);
                try
                {
                    if(!GetTokenInformation(token,25,data,needed,out needed)) return null;
                    IntPtr sid=Marshal.ReadIntPtr(data);
                    byte count=Marshal.ReadByte(GetSidSubAuthorityCount(sid));
                    return count==0 ? (int?)null : Marshal.ReadInt32(GetSidSubAuthority(sid,(uint)(count-1)));
                }
                finally { Marshal.FreeHGlobal(data); }
            }
            finally { CloseHandle(token); }
        }
        static string Label(int? rid)
        {
            if(!rid.HasValue) return "unknown";
            if(rid>=0x4000) return "system";
            if(rid>=0x3000) return "high";
            if(rid>=0x2000) return "medium";
            return "low";
        }
        public static Dictionary<string,object> Capture()
        {
            int? agent=Integrity(GetCurrentProcess()), target=null;
            uint pid; GetWindowThreadProcessId(GetForegroundWindow(),out pid);
            string name=""; int error=0;
            IntPtr process=pid==0 ? IntPtr.Zero : OpenProcess(0x1000,false,pid);
            if(process!=IntPtr.Zero)
            {
                try
                {
                    var text=new StringBuilder(4096); uint size=(uint)text.Capacity;
                    if(QueryFullProcessImageName(process,0,text,ref size)) name=Path.GetFileName(text.ToString());
                    target=Integrity(process);
                }
                finally { CloseHandle(process); }
            }
            else if(pid!=0) error=Marshal.GetLastWin32Error();
            return new Dictionary<string,object> {
                {"type","input_diagnostics"},{"agent_version","0.1.3"},
                {"agent_integrity",Label(agent)},{"target_integrity",Label(target)},
                {"target_name",name.Length>120 ? name.Substring(0,120) : name}, {"target_pid",pid},
                {"query_error",Math.Max(0,Math.Min(65535,error))},
                {"comparison",!agent.HasValue || !target.HasValue ? "unknown" : agent<target ? "agent_lower" : "not_lower"} };
        }
    }
}
