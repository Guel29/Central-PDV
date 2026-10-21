// CI only: drives the actual distributed WinExe; injects fictitious data into
// this test process's own blank window. Never compiled into the diagnostic.
using System;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Automation;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using System.Collections.Generic;
namespace SmartPDV.Diagnostics
{
    static class UiProbe
    {
        [StructLayout(LayoutKind.Sequential)] struct Mouse { public int X,Y; public uint Data,Flags,Time; public UIntPtr Extra; }
        [StructLayout(LayoutKind.Sequential)] struct Keyboard { public ushort Vk,Scan; public uint Flags,Time; public UIntPtr Extra; }
        [StructLayout(LayoutKind.Explicit)] struct Union { [FieldOffset(0)] public Mouse Mouse; [FieldOffset(0)] public Keyboard Keyboard; }
        [StructLayout(LayoutKind.Sequential)] struct Input { public uint Type; public Union Data; }
        [DllImport("user32.dll")] static extern uint SendInput(uint count, Input[] inputs, int size);
        static void Pump(int milliseconds) { var clock=Stopwatch.StartNew(); while(clock.ElapsedMilliseconds<milliseconds) { Application.DoEvents(); Thread.Sleep(5); } }
        static void Press(ushort scan)
        {
            foreach (uint flags in new uint[] { 8,10 })
            {
                var input=new Input { Type=1, Data=new Union { Keyboard=new Keyboard { Scan=scan, Flags=flags } } };
                if(SendInput(1,new[] { input },Marshal.SizeOf(typeof(Input)))!=1) throw new Exception("CI input failed");
                Pump(50);
            }
        }
        static AutomationElement Control(AutomationElement root, ControlType type, string name)
        { return root.FindFirst(TreeScope.Descendants,new AndCondition(new PropertyCondition(AutomationElement.ControlTypeProperty,type),new PropertyCondition(AutomationElement.NameProperty,name))); }
        static bool Active(AutomationElement root)
        {
            return root.FindAll(TreeScope.Descendants,new PropertyCondition(AutomationElement.ControlTypeProperty,ControlType.Text))
                .Cast<AutomationElement>().Any(e=>e.Current.Name.StartsWith("Coleta ativa",StringComparison.Ordinal));
        }
        static string Report(AutomationElement root)
        {
            foreach(AutomationElement e in root.FindAll(TreeScope.Descendants,new PropertyCondition(AutomationElement.ControlTypeProperty,ControlType.Edit)))
            {
                object pattern;
                if(e.TryGetCurrentPattern(ValuePattern.Pattern,out pattern))
                {
                    string value=((ValuePattern)pattern).Current.Value;
                    if(value.StartsWith("{\"schema\":",StringComparison.Ordinal)) return value;
                }
            }
            return null;
        }
        static void Wait(Func<bool> ready,int milliseconds,string message)
        {
            var clock=Stopwatch.StartNew(); while(clock.ElapsedMilliseconds<milliseconds) { if(ready())return; Pump(100); }
            throw new Exception(message);
        }
        static void Run(string file,bool raw)
        {
            using(var process=Process.Start(file))
            using(var target=new Form { Text="CI fictitious input target" })
            {
                try
                {
                    AutomationElement root=null;
                    Wait(()=>{ process.Refresh(); if(process.MainWindowHandle==IntPtr.Zero)return false; root=AutomationElement.FromHandle(process.MainWindowHandle); return root!=null; },15000,"Distributed UI did not open");
                    var combos=root.FindAll(TreeScope.Descendants,new PropertyCondition(AutomationElement.ControlTypeProperty,ControlType.ComboBox)).Cast<AutomationElement>().ToArray();
                    if(combos.Length!=3)throw new Exception("Expected three UI selectors");
                    if(raw) { combos[2].SetFocus(); Press(0xe04f); } // End selects Raw Input.
                    var start=Control(root,ControlType.Button,"Preparar coleta");
                    ((InvokePattern)start.GetCurrentPattern(InvokePattern.Pattern)).Invoke();
                    Wait(()=>Active(root),12000,"UI did not arm capture after grace period");
                    int delivered=0; target.KeyPreview=true; target.KeyDown+=delegate { delivered++; };
                    target.Show(); target.Activate(); target.Focus(); Pump(200);
                    foreach(ushort scan in new ushort[] {0x0b,0x0b,0x08,0x1c})Press(scan);
                    if(delivered<4)throw new Exception("Fictitious input did not reach CI target");
                    if(raw) ((InvokePattern)Control(root,ControlType.Button,"Parar").GetCurrentPattern(InvokePattern.Pattern)).Invoke();
                    string json=null; Wait(()=>{ json=Report(root); return json!=null; },35000,"Distributed UI did not finish capture");
                    var d=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(json);
                    var streams=(Dictionary<string,object>)d["streams"];
                    string expected=raw?"raw_keyboard":"keyboard_hook";
                    if(!expected.Equals(d["observer_mode"]))throw new Exception("Wrong UI observer selection");
                    if(streams.Count==0)throw new Exception("Distributed UI exported empty streams after CI typing: "+json);
                    int digits=streams.Values.Sum(v=>(int)((Dictionary<string,object>)v)["digit"]);
                    int enters=streams.Values.Sum(v=>(int)((Dictionary<string,object>)v)["enter"]);
                    if(digits<3||enters<1)throw new Exception("Distributed UI missed fictitious input categories: "+json);
                    Console.WriteLine("PASS distributed WinExe button -> grace -> background "+expected+" -> fictitious input delivered -> "+(raw?"manual stop":"automatic timeout")+" -> nonempty report");
                }
                finally { if(!process.HasExited) { process.CloseMainWindow(); if(!process.WaitForExit(3000))process.Kill(); } }
            }
        }
        [STAThread] static int Main(string[] args)
        {
            try { Application.EnableVisualStyles(); Run(System.IO.Path.GetFullPath(args[0]),args.Contains("--raw")); return 0; }
            catch(Exception ex) { Console.Error.WriteLine(ex.GetType().Name+": "+ex.Message); return 1; }
        }
    }
}
