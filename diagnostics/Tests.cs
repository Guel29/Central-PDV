// Test binary only. Never part of the shipped observer or Agent.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Windows.Forms;
namespace SmartPDV.Diagnostics
{
    static class Tests
    {
        static void Check(bool condition, string name) { if (!condition) throw new Exception(name); }
        static void Reject(Action action, string name) { bool rejected = false; try { action(); } catch (ArgumentException) { rejected = true; } Check(rejected, name); }
        static string Fake(string digits, string source)
        {
            var s = new Summary("pdv", "card_remote"); double now = 0;
            foreach (char c in digits)
            {
                s.Add(source, c, true, false, true, false, now, IntPtr.Zero);
                s.Add(source, c, false, false, true, false, now + 1, IntPtr.Zero); now += 25;
            }
            s.Add(source, 13, true, false, true, false, now, IntPtr.Zero);
            s.Add(source, 13, false, false, true, false, now + 1, IntPtr.Zero);
            return Summary.Serializer().Serialize(s.Export(2000, "manual", 2, 3, 1));
        }
        static void Unit()
        {
            string a = Fake("001234567890", "ll_injected"), b = Fake("998877665544", "ll_injected");
            Check(a == b, "Same aggregate for different numeric contents, including leading zeros");
            foreach (string secret in new[] { "001234567890", "998877665544", "scan_code", "key_sequence", "hash", "device_path" })
                Check(!a.Contains(secret), "No secret or identifying sequence in summary");
            Summary.Parse(a);
            var legacy=Summary.Parse(a); legacy.Remove("capture_health"); legacy["tool_version"]="0.1.0";
            Summary.Parse(Summary.Serializer().Serialize(legacy));
            var empty=Summary.Parse(Summary.Serializer().Serialize(new Summary("central","manual").Export(30000,"timeout",0,0,0)));
            Check((string)((Dictionary<string,object>)empty["capture_health"])["status"]=="no_events","Empty capture is explicitly inconclusive");
            Reject(()=>Summary.Parse(a.Replace("\"hook_callbacks\":0","\"hook_callbacks\":true")),"Health counters have strict types");
            Reject(()=>Summary.Parse(a.Replace("\"input_desktop\":\"unavailable\"","\"input_desktop\":\"secret-desktop\"")),"Do not import desktop names");
            var report = Summary.Parse(a); var streams = (Dictionary<string, object>)report["streams"];
            var channel = (Dictionary<string, object>)streams["ll_injected"];
            Check((int)channel["digit"] == 12 && (int)channel["enter"] == 1, "Digit and suffix counts");
            Check((string)channel["first_down_category"] == "digit" && (string)channel["last_down_category"] == "enter", "Only boundary categories");
            Check((int)channel["gap_20to49ms"] == 12, "Cadence histogram");
            Reject(() => Summary.Parse(a.Replace("\"elapsed_ms\":2000", "\"elapsed_ms\":true")), "Reject boolean counter");
            Reject(() => Summary.Parse(a.Replace("\"schema\":", "\"card\":\"001234567890\",\"schema\":")), "Reject unexpected secret field");
            Reject(() => Summary.Parse(a.Replace("\"first_down_category\":\"digit\"", "\"first_down_category\":\"001234567890\"")), "Reject secret in categorical field");
            Reject(() => Summary.Parse(new string('x', 65537)), "Bound imported file size");
            Check(Summary.Compare(a, Fake("789789789789", "ll_not_injected")).Contains("LL injetado down | 13 | 0"), "Compare observed injection metadata");
            var limited = new Summary("central", "manual");
            for (int i = 0; i < Summary.EventLimit; i++) Check(limited.Add("ll_injected", 48, true, false, true, false, i, IntPtr.Zero), "Bounded events accepted");
            Check(!limited.Add("ll_injected", 49, true, false, true, false, 10001, IntPtr.Zero), "Event bound");
            Summary.Parse(Summary.Serializer().Serialize(limited.Export(30000, "event_limit", 0, 0, 0)));
            Reject(() => Summary.Compare(a, a.Replace("\"observer_mode\":\"keyboard_hook\"", "\"observer_mode\":\"raw_keyboard\"")), "Do not compare inactive observer channels");
            Reject(() => new Summary("operator-secret", "manual"), "No free-text location");
            Check(!Summary.ValidSource("raw_keyboard_17") && !Summary.ValidSource("raw_keyboard_device-secret"), "Bound anonymous device labels");
            string folder = Path.Combine(Path.GetTempPath(), "smartpdv-diag-test-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            try
            {
                string path = Path.Combine(folder, "summary.json"); Reports.SaveNew(path, a);
                Check(Reports.Read(path) == a, "Export aggregate");
                Check(new FileInfo(path).GetAccessControl().AreAccessRulesProtected, "Protected report ACL");
                bool overwrite = false; try { Reports.SaveNew(path, b); } catch (IOException) { overwrite = true; }
                Check(overwrite && Reports.Read(path) == a, "No overwrite or corruption");
                Check(Directory.GetFiles(folder).Length == 1, "No residual temporary files");
                string huge = Path.Combine(folder, "large.json"); File.WriteAllText(huge, new string('x', 65537));
                Reject(() => Reports.Read(huge), "Bounded report reader");
            }
            finally { Directory.Delete(folder, true); }
        }
        [StructLayout(LayoutKind.Sequential)] struct MouseInput { public int X,Y; public uint Data,Flags,Time; public UIntPtr Extra; }
        [StructLayout(LayoutKind.Sequential)] struct KeyboardInput { public ushort Vk,Scan; public uint Flags,Time; public UIntPtr Extra; }
        [StructLayout(LayoutKind.Explicit)] struct InputUnion { [FieldOffset(0)] public MouseInput Mouse; [FieldOffset(0)] public KeyboardInput Key; }
        [StructLayout(LayoutKind.Sequential)] struct Input { public uint Type; public InputUnion Data; }
        [DllImport("user32.dll", SetLastError=true)] static extern uint SendInput(uint count, Input[] inputs, int size);
        sealed class TestWindow : Form
        {
            public NativeCapture Capture;
            protected override void WndProc(ref Message message)
            {
                if (message.Msg == 0xff && Capture != null) Capture.RawInput(message.LParam);
                base.WndProc(ref message);
            }
        }
        static void Pump(int milliseconds)
        {
            var clock = Stopwatch.StartNew();
            while (clock.ElapsedMilliseconds < milliseconds) { Application.DoEvents(); System.Threading.Thread.Sleep(1); }
        }
        static void Native(bool raw)
        {
            var summary = new Summary("pdv", "manual", raw ? "raw_keyboard" : "keyboard_hook");
            using (var window = new TestWindow { Text = "SmartPDV diagnostic CI inert input target" })
            using (var capture = new NativeCapture(summary, raw))
            using (var timer = new Timer { Interval = 60 })
            {
                int delivered = 0, index = 0; Exception failure = null;
                window.KeyPreview = true;
                window.KeyDown += delegate { delivered++; };
                ushort[] scans = { 0x0b, 0x0b, 0x08, 0x1c };
                window.Shown += delegate {
                    try {
                        window.Capture = capture;
                        capture.Start(window.Handle); timer.Start();
                    } catch (Exception ex) { failure = ex; window.Close(); }
                };
                timer.Tick += delegate {
                    try {
                        if (index < 8) {
                            var input = new Input { Type = 1, Data = new InputUnion { Key = new KeyboardInput { Scan = scans[index / 2], Flags = index % 2 == 0 ? 8u : 10u } } };
                            Check(SendInput(1, new[] { input }, Marshal.SizeOf(typeof(Input))) == 1, "Native CI injection accepted");
                            index++;
                        } else {
                            timer.Stop(); capture.Stop("manual"); window.Close();
                        }
                    } catch (Exception ex) { failure = ex; timer.Stop(); window.Close(); }
                };
                try {
                    // Use the same WinForms message loop as the shipped tool.
                    Application.Run(window);
                    if (failure != null) throw failure;
                    var report = capture.Report(); Summary.Parse(Summary.Serializer().Serialize(report));
                    var streams = (Dictionary<string, object>)report["streams"];
                    string source = raw ? "raw_keyboard_no_device" : "ll_injected";
                    Check(streams.ContainsKey(source), "Observe actual injected Windows input: failed=" + capture.ObservationFailed + " delivered=" + delivered + " events=" + summary.Events + " summary=" + Summary.Serializer().Serialize(report));
                    var stream = (Dictionary<string, object>)streams[source];
                    Check((int)stream["digit"] == 3 && (int)stream["enter"] == 1 && (int)stream["up"] == 4, "Native observer category counts");
                    Check(delivered >= 4, "Passive observer leaves keyboard input delivered to the target form");
                    Check(!capture.ObservationFailed, "No observer callback failure");
                    capture.Dispose(); Check(!capture.Active, "Explicit stop removes observer");
                    int previous = summary.Events;
                    Pump(150); Check(summary.Events == previous, "No collection after stop");
                } finally {
                    timer.Stop(); capture.Dispose();
                }
            }
        }
        [STAThread] static int Main(string[] args)
        {
            try
            {
                Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
                Unit(); Console.WriteLine("PASS: content-independent aggregates, strict import schema, numeric burst metadata, event bounds, protected atomic export, no overwrite");
                Native(args.Contains("--raw")); Console.WriteLine("PASS: real Windows observer " + (args.Contains("--raw") ? "Raw Input" : "keyboard hook") + ", injected digit/Enter categories, passive target delivery, no collection after stop; no physical USB or VR validation");
                using (var form = new DiagnosticWindow()) { form.Show(); Pump(100); form.Close(); }
                Console.WriteLine("PASS: diagnostic window opens and closes without automatically arming capture");
                return 0;
            }
            catch (Exception ex) { Console.Error.WriteLine(ex.GetType().Name + ": " + ex.Message); return 1; }
        }
    }
}
