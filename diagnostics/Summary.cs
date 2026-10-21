using System;
using System.Collections.Generic;
using System.Linq;
using System.Web.Script.Serialization;
using System.Text;

namespace SmartPDV.Diagnostics
{
    // Only categories and aggregates survive a callback. No key sequence, VK,
    // scan code, device path, serial number, character, or card hash is retained.
    sealed class Summary
    {
        public const string Version = "0.1.0", Schema = "smartpdv-input-summary-v1";
        public static readonly string[] Scenarios = { "product_local", "product_remote", "card_local", "card_remote", "manual" };
        public static readonly string[] Categories = { "digit", "keypad_digit", "letter", "enter", "tab", "modifier", "function", "navigation", "other" };
        public static readonly string[] Counters = { "down", "up", "extended", "scan_present", "scan_missing", "lower_integrity", "focus_changes", "digit", "keypad_digit", "letter", "enter", "tab", "modifier", "function", "navigation", "other", "gap_lt5ms", "gap_5to19ms", "gap_20to49ms", "gap_50to99ms", "gap_ge100ms" };
        readonly Dictionary<string, object> streams = new Dictionary<string, object>();
        readonly Dictionary<string, double> lastDown = new Dictionary<string, double>();
        readonly Dictionary<string, IntPtr> lastFocus = new Dictionary<string, IntPtr>();
        readonly string location, scenario, observerMode;
        public int Events { get; private set; }
        public const int EventLimit = 10000;
        public Summary(string location, string scenario, string observerMode = "keyboard_hook")
        {
            if ((location != "central" && location != "pdv") || !Scenarios.Contains(scenario)) throw new ArgumentException("Invalid diagnostic selection");
            if (observerMode != "keyboard_hook" && observerMode != "raw_keyboard") throw new ArgumentException("Invalid observer mode");
            this.location = location; this.scenario = scenario; this.observerMode = observerMode;
        }
        public static string Category(uint key)
        {
            if (key >= 0x30 && key <= 0x39) return "digit";
            if (key >= 0x60 && key <= 0x69) return "keypad_digit";
            if (key >= 0x41 && key <= 0x5a) return "letter";
            if (key == 13) return "enter";
            if (key == 9) return "tab";
            if ((key >= 16 && key <= 18) || (key >= 0xa0 && key <= 0xa5) || key == 0x5b || key == 0x5c) return "modifier";
            if (key >= 0x70 && key <= 0x87) return "function";
            if ((key >= 0x21 && key <= 0x28) || key == 0x2d || key == 0x2e) return "navigation";
            return "other";
        }
        public static bool ValidSource(string source)
        {
            if (source == "ll_not_injected" || source == "ll_injected" || source == "raw_keyboard_no_device") return true;
            int number;
            return source.StartsWith("raw_keyboard_", StringComparison.Ordinal) && int.TryParse(source.Substring(13), out number) && number >= 1 && number <= 16 && source == "raw_keyboard_" + number;
        }
        public bool Add(string source, uint key, bool down, bool extended, bool hasScan, bool lowerIntegrity, double milliseconds, IntPtr focus)
        {
            if (!ValidSource(source)) throw new ArgumentException("Invalid event source");
            if (Events >= EventLimit) return false;
            Events++;
            object value;
            if (!streams.TryGetValue(source, out value))
            {
                var created = Counters.ToDictionary(k => k, k => (object)0);
                created["first_down_category"] = "none"; created["last_down_category"] = "none";
                streams[source] = value = created;
            }
            var s = (Dictionary<string, object>)value;
            Increment(s, down ? "down" : "up");
            if (extended) Increment(s, "extended");
            Increment(s, hasScan ? "scan_present" : "scan_missing");
            if (lowerIntegrity) Increment(s, "lower_integrity");
            if (down)
            {
                string category = Category(key);
                Increment(s, category);
                if ((string)s["first_down_category"] == "none") s["first_down_category"] = category;
                s["last_down_category"] = category;
                double last;
                if (lastDown.TryGetValue(source, out last))
                {
                    double gap = Math.Max(0, milliseconds - last);
                    Increment(s, gap < 5 ? "gap_lt5ms" : gap < 20 ? "gap_5to19ms" : gap < 50 ? "gap_20to49ms" : gap < 100 ? "gap_50to99ms" : "gap_ge100ms");
                }
                lastDown[source] = milliseconds;
                IntPtr previous;
                if (lastFocus.TryGetValue(source, out previous) && focus != previous) Increment(s, "focus_changes");
                lastFocus[source] = focus;
            }
            return true;
        }
        static void Increment(Dictionary<string, object> s, string key) { s[key] = (int)s[key] + 1; }
        public Dictionary<string, object> Export(int elapsed, string reason, int keyboards, int hids, int serialPorts)
        {
            return new Dictionary<string, object> {
                { "schema", Schema }, { "tool_version", Version }, { "location", location }, { "scenario", scenario }, { "observer_mode", observerMode },
                { "elapsed_ms", Math.Min(30000, Math.Max(0, elapsed)) }, { "stop_reason", reason },
                { "inventory", new Dictionary<string, object> { { "raw_keyboard_devices", keyboards }, { "raw_hid_devices", hids }, { "serial_port_count", serialPorts } } },
                { "streams", streams.ToDictionary(p => p.Key, p => (object)new Dictionary<string, object>((Dictionary<string, object>)p.Value)) }
            };
        }
        public static JavaScriptSerializer Serializer() { return new JavaScriptSerializer { MaxJsonLength = 65536, RecursionLimit = 12 }; }
        static void Exact(Dictionary<string, object> d, IEnumerable<string> keys)
        { if (d.Count != keys.Count() || keys.Any(k => !d.ContainsKey(k))) throw new ArgumentException("Invalid summary schema"); }
        static void Integer(object value, int minimum, int maximum)
        { if (!(value is int) || (int)value < minimum || (int)value > maximum) throw new ArgumentException("Invalid summary counter"); }
        public static Dictionary<string, object> Parse(string text)
        {
            if (text.Length > 65536) throw new ArgumentException("Summary too large");
            var d = Serializer().DeserializeObject(text) as Dictionary<string, object>;
            if (d == null) throw new ArgumentException("Invalid summary");
            Exact(d, new[] { "schema", "tool_version", "location", "scenario", "observer_mode", "elapsed_ms", "stop_reason", "inventory", "streams" });
            if (!Schema.Equals(d["schema"]) || !Version.Equals(d["tool_version"]) || !(new object[] { "central", "pdv" }).Contains(d["location"]) || !Scenarios.Contains(d["scenario"] as string) || !(new object[] { "manual", "timeout", "event_limit" }).Contains(d["stop_reason"])) throw new ArgumentException("Invalid summary metadata");
            if (!(new object[] { "keyboard_hook", "raw_keyboard" }).Contains(d["observer_mode"])) throw new ArgumentException("Invalid observer mode");
            Integer(d["elapsed_ms"], 0, 30000);
            var inventory = d["inventory"] as Dictionary<string, object>;
            if (inventory == null) throw new ArgumentException("Invalid inventory");
            Exact(inventory, new[] { "raw_keyboard_devices", "raw_hid_devices", "serial_port_count" });
            foreach (object v in inventory.Values) Integer(v, -1, 10000);
            var sources = d["streams"] as Dictionary<string, object>;
            if (sources == null || sources.Count > 19) throw new ArgumentException("Invalid streams");
            foreach (var source in sources)
            {
                var s = source.Value as Dictionary<string, object>;
                if (!ValidSource(source.Key) || s == null) throw new ArgumentException("Invalid source");
                Exact(s, Counters.Concat(new[] { "first_down_category", "last_down_category" }));
                foreach (string key in Counters) Integer(s[key], 0, EventLimit);
                if (!Categories.Concat(new[] { "none" }).Contains(s["first_down_category"] as string) || !Categories.Concat(new[] { "none" }).Contains(s["last_down_category"] as string)) throw new ArgumentException("Invalid category");
                int down = (int)s["down"], up = (int)s["up"];
                if (down + up > EventLimit || Categories.Sum(k => (int)s[k]) != down) throw new ArgumentException("Inconsistent summary");
            }
            return d;
        }
        static int Total(Dictionary<string, object> d, string prefix, string counter)
        {
            return ((Dictionary<string, object>)d["streams"]).Where(s => s.Key.StartsWith(prefix, StringComparison.Ordinal))
                .Sum(s => (int)((Dictionary<string, object>)s.Value)[counter]);
        }
        public static string Compare(string first, string second)
        {
            var a = Parse(first); var b = Parse(second);
            if (!Equals(a["observer_mode"], b["observer_mode"])) throw new ArgumentException("Compare the same observer mode");
            var text = new StringBuilder("Comparação agregada — não compara dígitos nem comprova o mecanismo da VR.\r\n");
            text.AppendLine("A: " + a["location"] + " / " + a["scenario"] + " | B: " + b["location"] + " / " + b["scenario"]);
            text.AppendLine("Observador: " + a["observer_mode"]);
            text.AppendLine("Métrica | A | B");
            foreach (string counter in new[] { "down", "up", "digit", "keypad_digit", "enter", "tab", "modifier", "focus_changes", "gap_lt5ms", "gap_5to19ms", "gap_20to49ms", "gap_50to99ms", "gap_ge100ms" })
                text.AppendLine("LL " + counter + " | " + Total(a, "ll_", counter) + " | " + Total(b, "ll_", counter));
            text.AppendLine("LL injetado down | " + Total(a, "ll_injected", "down") + " | " + Total(b, "ll_injected", "down"));
            text.AppendLine("Raw Input down | " + Total(a, "raw_keyboard_", "down") + " | " + Total(b, "raw_keyboard_", "down"));
            text.AppendLine("\r\nAusência de Raw Input e presença de LL injetado mostram diferença observada neste diagnóstico; não demonstram que a VR exige Raw Input. A marca de injeção ausente também não comprova hardware físico.");
            text.AppendLine("Compare quantidade de eventos, Enter/Tab/modificadores, foco e faixas de tempo. Os intervalos são os observados pelos callbacks, não uma medição de barramento USB. Confirme o mecanismo da tela fiscal com a VR.");
            text.AppendLine("\r\nDetalhes A: " + Serializer().Serialize(a));
            text.AppendLine("\r\nDetalhes B: " + Serializer().Serialize(b));
            return text.ToString();
        }
    }
}
