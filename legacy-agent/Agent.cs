using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Security;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Authentication;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace SmartPDV.Legacy
{
    static class JsonFiles
    {
        public static JavaScriptSerializer Serializer()
        {
            return new JavaScriptSerializer { MaxJsonLength = 2000000, RecursionLimit = 24 };
        }
        public static Dictionary<string, object> Load(string path)
        {
            return Serializer().Deserialize<Dictionary<string, object>>(File.ReadAllText(path, Encoding.UTF8));
        }
        public static void Secure(string folder)
        {
            Directory.CreateDirectory(folder);
            var acl = new DirectoryInfo(folder).GetAccessControl();
            var inheritance = InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit;
            acl.AddAccessRule(new FileSystemAccessRule(WindowsIdentity.GetCurrent().User,
                FileSystemRights.FullControl, inheritance, PropagationFlags.None, AccessControlType.Allow));
            acl.AddAccessRule(new FileSystemAccessRule(new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
                FileSystemRights.FullControl, inheritance, PropagationFlags.None, AccessControlType.Allow));
            acl.SetAccessRuleProtection(true, false);
            new DirectoryInfo(folder).SetAccessControl(acl);
        }
        public static void Save(string path, object data)
        {
            Secure(Path.GetDirectoryName(path));
            string temporary = Path.Combine(Path.GetDirectoryName(path), ".pending-" + Guid.NewGuid().ToString("N"));
            try
            {
                byte[] bytes = new UTF8Encoding(false).GetBytes(Serializer().Serialize(data));
                using (var f = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                { f.Write(bytes, 0, bytes.Length); f.Flush(true); }
                if (File.Exists(path)) File.Replace(temporary, path, null);
                else File.Move(temporary, path);
            }
            finally { if (File.Exists(temporary)) File.Delete(temporary); }
        }
    }

    sealed class Configuration
    {
        public int Number;
        public string ComputerId, Host, Fingerprint, Token;
        public int Port, KeyboardMinPress;
        public bool F11;
        public static Configuration Parse(Dictionary<string, object> value, bool pairing)
        {
            var c = new Configuration();
            c.Number = Convert.ToInt32(value["number"], CultureInfo.InvariantCulture);
            c.ComputerId = Convert.ToString(value["computer_id"], CultureInfo.InvariantCulture);
            c.Host = Convert.ToString(value["central"], CultureInfo.InvariantCulture);
            c.Port = Convert.ToInt32(value["port"], CultureInfo.InvariantCulture);
            c.Fingerprint = Convert.ToString(value["fingerprint"], CultureInfo.InvariantCulture);
            c.KeyboardMinPress = value.ContainsKey("keyboard_min_press_ms") ? Convert.ToInt32(value["keyboard_min_press_ms"], CultureInfo.InvariantCulture) : 20;
            if (c.KeyboardMinPress < 0 || c.KeyboardMinPress > 100) throw new InvalidDataException("keyboard_min_press_ms deve estar entre 0 e 100.");
            c.F11 = !value.ContainsKey("f11") || Convert.ToBoolean(value["f11"], CultureInfo.InvariantCulture);
            if (pairing) c.Token = Convert.ToString(value["token"], CultureInfo.InvariantCulture);
            else
            {
                var secret = (Dictionary<string, object>)value["token"];
                if ((string)secret["format"] != "dpapi") throw new InvalidDataException("Credencial Windows DPAPI obrigatoria.");
                c.Token = Encoding.UTF8.GetString(ProtectedData.Unprotect(Convert.FromBase64String((string)secret["data"]), null, DataProtectionScope.CurrentUser));
            }
            if (c.Number <= 0 || c.Port < 1 || c.Port > 65535 || c.ComputerId.Length < 1 || c.ComputerId.Length > 128 ||
                c.ComputerId.Any(ch => ch < 33 || ch > 126) || string.IsNullOrEmpty(c.Token) ||
                c.Token.Any(ch => ch < 33 || ch > 126) || c.Fingerprint.Length != 64 ||
                !c.Fingerprint.All(Uri.IsHexDigit) || string.IsNullOrWhiteSpace(c.Host) || c.Host.Any(char.IsWhiteSpace) ||
                c.Host.IndexOfAny(new char[] { '/', '\\', '@', '\r', '\n' }) >= 0)
                throw new InvalidDataException("Cadastro de PDV invalido.");
            return c;
        }
        public static IPAddress LocalAddress(string host)
        {
            IPAddress[] addresses = Dns.GetHostAddresses(host);
            if (addresses.Length == 0 || addresses.Any(ip => !IsLocal(ip)))
                throw new InvalidDataException("A Central deve estar na rede local.");
            return addresses[0];
        }
        static bool IsLocal(IPAddress ip)
        {
            if (IPAddress.IsLoopback(ip) || ip.IsIPv6LinkLocal || ip.IsIPv6SiteLocal) return true;
            if (ip.IsIPv4MappedToIPv6) return IsLocal(ip.MapToIPv4());
            byte[] b = ip.GetAddressBytes();
            if (b.Length == 16) return (b[0] & 0xfe) == 0xfc;
            return b[0] == 10 || (b[0] == 172 && b[1] >= 16 && b[1] <= 31) ||
                (b[0] == 192 && b[1] == 168) || (b[0] == 169 && b[1] == 254);
        }
    }

    // RFC 6455 gerenciado: nao depende de websocket.dll, ausente no Windows 7.
    sealed class LocalWebSocket : IDisposable
    {
        readonly TcpClient tcp;
        readonly SslStream stream;
        readonly object writeLock = new object();
        volatile bool closed;
        static readonly UTF8Encoding Utf8 = new UTF8Encoding(false, true);
        public LocalWebSocket(Configuration c)
        {
            IPAddress ip = Configuration.LocalAddress(c.Host);
            tcp = new TcpClient(ip.AddressFamily);
            try
            {
                var connect = tcp.BeginConnect(ip, c.Port, null, null);
                try
                {
                    if (!connect.AsyncWaitHandle.WaitOne(10000)) throw new TimeoutException("Conexao LAN expirou.");
                    tcp.EndConnect(connect);
                }
                finally { connect.AsyncWaitHandle.Close(); }
                tcp.NoDelay = true;
                stream = new SslStream(tcp.GetStream(), false, delegate(object sender, X509Certificate certificate,
                    X509Chain chain, SslPolicyErrors errors)
                {
                    if (certificate == null) return false;
                    using (var sha = SHA256.Create())
                    {
                        string actual = BitConverter.ToString(sha.ComputeHash(certificate.GetRawCertData())).Replace("-", "");
                        // Pin SHA-256 exato, igual ao Agent Python; nunca aceitar certificado arbitrario.
                        return string.Equals(actual, c.Fingerprint, StringComparison.OrdinalIgnoreCase);
                    }
                });
                stream.ReadTimeout = 20000; stream.WriteTimeout = 5000;
                stream.AuthenticateAsClient(c.Host, null, SslProtocols.Tls12, false);
                byte[] nonce = new byte[16]; using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(nonce);
                string key = Convert.ToBase64String(nonce);
                string host = c.Host.IndexOf(':') >= 0 ? "[" + c.Host + "]" : c.Host;
                string headers = "GET /agent HTTP/1.1\r\nHost: " + host + ":" + c.Port +
                    "\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key +
                    "\r\nAuthorization: Bearer " + c.Token + "\r\nX-Computer-ID: " + c.ComputerId + "\r\n\r\n";
                byte[] request = Encoding.ASCII.GetBytes(headers); stream.Write(request, 0, request.Length);
                var response = new StringBuilder();
                while (!response.ToString().EndsWith("\r\n\r\n", StringComparison.Ordinal))
                {
                    int b = stream.ReadByte(); if (b < 0) throw new EndOfStreamException();
                    response.Append((char)b); if (response.Length > 16384) throw new InvalidDataException("Upgrade muito grande.");
                }
                string[] lines = response.ToString().Split(new string[] { "\r\n" }, StringSplitOptions.None);
                if (!lines[0].StartsWith("HTTP/1.1 101 ", StringComparison.Ordinal)) throw new AuthenticationException("Pareamento rejeitado pela Central.");
                var fields = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                foreach (string line in lines.Skip(1))
                {
                    int colon = line.IndexOf(':'); if (colon > 0) fields[line.Substring(0, colon)] = line.Substring(colon + 1).Trim();
                }
                string accept;
                using (var sha = SHA1.Create()) accept = Convert.ToBase64String(sha.ComputeHash(Encoding.ASCII.GetBytes(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")));
                if (!fields.ContainsKey("Sec-WebSocket-Accept") || fields["Sec-WebSocket-Accept"] != accept ||
                    !fields.ContainsKey("Upgrade") || !string.Equals(fields["Upgrade"], "websocket", StringComparison.OrdinalIgnoreCase) ||
                    !fields.ContainsKey("Connection") || !fields["Connection"].Split(',').Any(v => v.Trim().Equals("Upgrade", StringComparison.OrdinalIgnoreCase)))
                    throw new AuthenticationException("Upgrade WebSocket invalido.");
                // A Central pode nao enviar mensagens enquanto recebe miniaturas regularmente.
                // Escritas limitadas e o socket fechado detectam quedas, sem reconectar por inatividade.
                stream.ReadTimeout = Timeout.Infinite;
            }
            catch { tcp.Close(); throw; }
        }
        byte[] Exact(int size)
        {
            byte[] data = new byte[size]; int offset = 0;
            while (offset < size)
            {
                int read = stream.Read(data, offset, size - offset);
                if (read == 0) throw new EndOfStreamException(); offset += read;
            }
            return data;
        }
        public string Receive()
        {
            using (var fragments = new MemoryStream())
            {
                bool fragmented = false;
                while (!closed)
                {
                    byte[] head = Exact(2); bool final = (head[0] & 128) != 0;
                    int opcode = head[0] & 15;
                    if ((head[0] & 112) != 0 || (head[1] & 128) != 0) throw new InvalidDataException("Frame invalido.");
                    ulong length = (ulong)(head[1] & 127);
                    if (length == 126) { byte[] b = Exact(2); length = (ulong)(b[0] * 256 + b[1]); }
                    else if (length == 127) { length = 0; foreach (byte b in Exact(8)) { if (length > 8192) throw new InvalidDataException(); length = length * 256 + b; } }
                    if (length > 8192 || opcode >= 8 && (!final || length > 125)) throw new InvalidDataException("Mensagem grande demais.");
                    byte[] payload = Exact((int)length);
                    if (opcode == 8) { Dispose(); throw new EndOfStreamException(); }
                    if (opcode == 9) { Frame(10, payload); continue; }
                    if (opcode == 10) continue;
                    if (opcode == 1 && !fragmented) fragmented = true;
                    else if (opcode != 0 || !fragmented) throw new InvalidDataException("Tipo de mensagem invalido.");
                    fragments.Write(payload, 0, payload.Length);
                    if (fragments.Length > 8192) throw new InvalidDataException("Mensagem grande demais.");
                    if (final) return Utf8.GetString(fragments.ToArray());
                }
            }
            throw new EndOfStreamException();
        }
        public void Send(object value) { Frame(1, Utf8.GetBytes(JsonFiles.Serializer().Serialize(value))); }
        void Frame(int opcode, byte[] payload)
        {
            lock (writeLock)
            {
                if (closed) throw new ObjectDisposedException("WebSocket");
                using (var frame = new MemoryStream())
                {
                    frame.WriteByte((byte)(128 | opcode));
                    if (payload.Length < 126) frame.WriteByte((byte)(128 | payload.Length));
                    else if (payload.Length <= 65535)
                    {
                        frame.WriteByte(254); frame.WriteByte((byte)(payload.Length >> 8)); frame.WriteByte((byte)payload.Length);
                    }
                    else
                    {
                        frame.WriteByte(255); ulong size = (ulong)payload.Length;
                        for (int shift = 56; shift >= 0; shift -= 8) frame.WriteByte((byte)(size >> shift));
                    }
                    byte[] mask = new byte[4]; using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(mask);
                    frame.Write(mask, 0, 4);
                    byte[] masked = new byte[payload.Length];
                    for (int i = 0; i < payload.Length; i++) masked[i] = (byte)(payload[i] ^ mask[i % 4]);
                    frame.Write(masked, 0, masked.Length);
                    byte[] bytes = frame.ToArray(); stream.Write(bytes, 0, bytes.Length); stream.Flush();
                }
            }
        }
        public void Dispose()
        {
            closed = true;
            try { tcp.Close(); } catch (ObjectDisposedException) { }
        }
    }

    sealed class Desktop
    {
        [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
        [DllImport("user32.dll")] static extern void mouse_event(uint flags, uint x, uint y, uint data, UIntPtr extra);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern short VkKeyScan(char key);
        readonly object inputLock = new object();
        readonly Dictionary<string, ushort> keys = new Dictionary<string, ushort>();
        readonly HashSet<int> buttons = new HashSet<int>();
        readonly Dictionary<string, byte> special = new Dictionary<string, byte> {
            {"Enter",13},{"Escape",27},{"Tab",9},{"Backspace",8},{"Delete",46},{"ArrowLeft",37},{"ArrowUp",38},
            {"ArrowRight",39},{"ArrowDown",40},{"Shift",16},{"Control",17},{"Alt",18},{"Meta",91},{" ",32},
            {"Home",36},{"End",35},{"PageUp",33},{"PageDown",34} };
        public string Capture(bool active)
        {
            Rectangle bounds = Screen.PrimaryScreen.Bounds;
            using (var full = new Bitmap(bounds.Width, bounds.Height, PixelFormat.Format24bppRgb))
            {
                using (var graphics = Graphics.FromImage(full)) graphics.CopyFromScreen(bounds.Location, Point.Empty, bounds.Size);
                double factor = Math.Min(1, Math.Min((active ? 1280.0 : 320.0) / bounds.Width, (active ? 720.0 : 180.0) / bounds.Height));
                using (var small = new Bitmap(Math.Max(1, (int)(bounds.Width * factor)), Math.Max(1, (int)(bounds.Height * factor))))
                using (var graphics = Graphics.FromImage(small))
                using (var output = new MemoryStream())
                using (var parameters = new EncoderParameters(1))
                {
                    graphics.InterpolationMode = InterpolationMode.Low;
                    graphics.DrawImage(full, 0, 0, small.Width, small.Height);
                    parameters.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, active ? 60L : 40L);
                    small.Save(output, ImageCodecInfo.GetImageEncoders().First(e => e.MimeType == "image/jpeg"), parameters);
                    return Convert.ToBase64String(output.ToArray());
                }
            }
        }
        public bool Input(Dictionary<string, object> e)
        {
            lock (inputLock)
            {
                string kind = (string)e["kind"];
                if (kind == "release") { Release(); return false; }
                if (kind == "wheel")
                {
                    int delta = Convert.ToInt32(e["delta"]); if (delta != -120 && delta != 120) return false;
                    mouse_event(0x0800, 0, 0, unchecked((uint)delta), UIntPtr.Zero); return false;
                }
                string action = (string)e["action"];
                if (kind == "mouse")
                {
                    double x = Convert.ToDouble(e["x"], CultureInfo.InvariantCulture), y = Convert.ToDouble(e["y"], CultureInfo.InvariantCulture);
                    if (double.IsNaN(x) || double.IsNaN(y) || x < 0 || x > 1 || y < 0 || y > 1) return false;
                    Rectangle bounds = Screen.PrimaryScreen.Bounds;
                    SetCursorPos(bounds.Left + (int)Math.Round(x * (bounds.Width - 1)), bounds.Top + (int)Math.Round(y * (bounds.Height - 1)));
                    int button = Convert.ToInt32(e["button"]);
                    if ((button != 0 && button != 2) || action != "down" && action != "up") return false;
                    bool down = action == "down";
                    mouse_event(button == 0 ? (down ? 2u : 4u) : (down ? 8u : 16u), 0, 0, 0, UIntPtr.Zero);
                    if (down) buttons.Add(button); else buttons.Remove(button);
                }
                else if (kind == "key" && (action == "down" || action == "up"))
                {
                    string key = (string)e["key"]; byte vk; int f; object raw;
                    ushort scan, held; string identity;
                    if(e.TryGetValue("code",out raw) && ScanKeyboard.TryPhysical(raw as string,out scan))
                        identity="physical:"+(string)raw;
                    else
                    {
                        if (!special.TryGetValue(key, out vk))
                        {
                            if (key.StartsWith("F", StringComparison.Ordinal) && int.TryParse(key.Substring(1), out f) && f >= 1 && f <= 12) vk = (byte)(111 + f);
                            else if (key.Length == 1) { short mapped = VkKeyScan(key[0]); if (mapped == -1) return false; vk = (byte)(mapped & 255); }
                            else return false;
                        }
                        identity="vk:"+vk;
                        scan=ScanKeyboard.Resolve(vk);
                    }
                    if(keys.TryGetValue(identity,out held)) scan=held;
                    bool down = action == "down";
                    ScanKeyboard.Send(scan, down);
                    if (down) keys[identity] = scan; else keys.Remove(identity);
                    return true;
                }
            }
            return false;
        }
        public void Release()
        {
            lock (inputLock)
            {
                foreach (ushort scan in keys.Values)
                {
                    // A blocked/elevated desktop must not kill the reconnect worker during cleanup.
                    try { ScanKeyboard.Send(scan, false); }
                    catch (System.ComponentModel.Win32Exception) { }
                }
                foreach (int button in buttons) mouse_event(button == 0 ? 4u : 16u, 0, 0, 0, UIntPtr.Zero);
                keys.Clear(); buttons.Clear();
            }
        }
    }

    sealed class AgentContext : ApplicationContext
    {
        [DllImport("user32.dll", SetLastError = true)] static extern bool RegisterHotKey(IntPtr handle, int id, uint modifiers, uint key);
        [DllImport("user32.dll")] static extern bool UnregisterHotKey(IntPtr handle, int id);
        sealed class HotkeyWindow : NativeWindow, IDisposable
        {
            readonly Action callback;
            public HotkeyWindow(Action onRequest, bool enabled)
            {
                callback = onRequest;
                CreateHandle(new CreateParams { Caption = "SmartPDV Agent Win7", Parent = new IntPtr(-3) });
                if (enabled && !RegisterHotKey(Handle, 1, 0x4000, 0x7a))
                    throw new InvalidOperationException("F11 ja esta registrado. Encerre outra instancia do Agent.");
            }
            protected override void WndProc(ref Message message)
            {
                if (message.Msg == 0x0312) callback();
                base.WndProc(ref message);
            }
            public void Dispose() { UnregisterHotKey(Handle, 1); DestroyHandle(); }
        }
        readonly Configuration config;
        readonly Desktop desktop = new Desktop();
        readonly HotkeyWindow window;
        readonly ManualResetEvent stopping = new ManualResetEvent(false);
        volatile bool active, pending;
        public AgentContext(Configuration c)
        {
            config = c;
            window = new HotkeyWindow(delegate { if (!active) pending = true; }, c.F11);
            new Thread(Work) { IsBackground = true, Name = "SmartPDV LAN" }.Start();
        }
        void Work()
        {
            int delay = 1000;
            while (!stopping.WaitOne(0))
            {
                try
                {
                    using (var connection = new LocalWebSocket(config))
                    {
                        delay = 1000; bool connected = true;
                        var reader = new Thread(delegate()
                        {
                            try
                            {
                                bool? lastAccepted = null; int lastCode = 0;
                                DateTime lastReport = DateTime.MinValue;
                                while (true)
                                {
                                    var message = JsonFiles.Serializer().Deserialize<Dictionary<string, object>>(connection.Receive());
                                    string type = (string)message["type"];
                                    if (type == "session")
                                    {
                                        lastAccepted = null; lastReport = DateTime.MinValue;
                                        active = (bool)message["active"]; desktop.Release(); if (active) pending = false;
                                    }
                                    else if (type == "input" && active)
                                    {
                                        bool? accepted = null; int error = 0;
                                        try { if (desktop.Input((Dictionary<string, object>)message["event"])) accepted = true; }
                                        catch (System.ComponentModel.Win32Exception ex)
                                        {
                                            accepted = false; error = ex.NativeErrorCode;
                                            if (error < 0 || error > 65535) error = 0;
                                        }
                                        if (accepted.HasValue && (lastAccepted != accepted || lastCode != error || (DateTime.UtcNow-lastReport).TotalSeconds >= 2))
                                        {
                                            connection.Send(new { type = "input_status", accepted = accepted.Value, error_code = error });
                                            lastAccepted = accepted; lastCode = error; lastReport = DateTime.UtcNow;
                                        }
                                    }
                                }
                            }
                            catch (Exception) { }
                            finally { Volatile.Write(ref connected, false); connection.Dispose(); }
                        }) { IsBackground = true };
                        reader.Start();
                        try
                        {
                            bool sent = false; DateTime lastFrame = DateTime.MinValue;
                            while (!stopping.WaitOne(30) && Volatile.Read(ref connected))
                            {
                                if (pending && !sent) { connection.Send(new { type = "request" }); sent = true; }
                                if (!pending) sent = false;
                                if ((DateTime.UtcNow - lastFrame).TotalMilliseconds >= (active ? 250 : 2000))
                                {
                                    connection.Send(new { type = "frame", jpeg = desktop.Capture(active) }); lastFrame = DateTime.UtcNow;
                                }
                            }
                        }
                        finally { connection.Dispose(); reader.Join(1000); }
                    }
                }
                catch (Exception) { /* Nao registrar tokens, imagens, teclas nem payloads. */ }
                finally { active = false; desktop.Release(); }
                if (stopping.WaitOne(delay)) break; delay = Math.Min(delay * 2, 15000);
            }
        }
        protected override void Dispose(bool disposing)
        {
            stopping.Set(); window.Dispose(); desktop.Release(); base.Dispose(disposing);
        }
    }

    static class Program
    {
        static string Ask(string title, string initial)
        {
            using (var form = new Form { Text = title, Width = 520, Height = 150, StartPosition = FormStartPosition.CenterScreen,
                FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false })
            {
                var input = new TextBox { Left = 15, Top = 15, Width = 470, Text = initial };
                var ok = new Button { Text = "OK", Left = 310, Top = 50, DialogResult = DialogResult.OK };
                var cancel = new Button { Text = "Cancelar", Left = 400, Top = 50, DialogResult = DialogResult.Cancel };
                form.Controls.AddRange(new Control[] { input, ok, cancel }); form.AcceptButton = ok; form.CancelButton = cancel;
                if (form.ShowDialog() != DialogResult.OK) throw new OperationCanceledException("Configuracao cancelada.");
                return input.Text.Trim();
            }
        }
        static void Setup(string directory)
        {
            string path = Path.Combine(directory, "agent.json");
            if (File.Exists(path)) throw new InvalidOperationException("Agent ja configurado. Preserve o cadastro existente antes de refazer.");
            using (var dialog = new OpenFileDialog { Title = "Pareamento exportado pela Central", Filter = "Cadastro PDV (*.json)|*.json" })
            {
                if (dialog.ShowDialog() != DialogResult.OK) return;
                var value = JsonFiles.Load(dialog.FileName);
                var config = Configuration.Parse(value, true);
                string host = Ask("Endereco IP ou nome LAN da Central", config.Host);
                int number;
                if (!int.TryParse(Ask("Numero do PDV", config.Number.ToString(CultureInfo.InvariantCulture)), out number) || number != config.Number)
                    throw new InvalidDataException("O numero deve corresponder ao cadastro da Central.");
                Configuration.LocalAddress(host); value["central"] = host;
                value["token"] = new Dictionary<string, object> {
                    {"format","dpapi"}, {"data",Convert.ToBase64String(ProtectedData.Protect(Encoding.UTF8.GetBytes(config.Token), null, DataProtectionScope.CurrentUser))} };
                JsonFiles.Save(path, value);
                MessageBox.Show("PDV configurado. Remova as copias do arquivo de pareamento. O Agent pode iniciar em segundo plano.", "Smart PDV Win7");
            }
        }
        static void Probe(Configuration config, string directory)
        {
            bool started = false, input = false;
            using (var connection = new LocalWebSocket(config))
            {
                connection.Send(new { type = "request" });
                while (true)
                {
                    var message = JsonFiles.Serializer().Deserialize<Dictionary<string, object>>(connection.Receive());
                    string type = (string)message["type"];
                    if (type == "session")
                    {
                        if ((bool)message["active"]) started = true;
                        else if (started)
                        {
                            JsonFiles.Save(Path.Combine(directory,"network-probe.json"), new { tls = true, started = started, input = input, ended = true }); return;
                        }
                    }
                    else if (type == "input" && started) input = true;
                }
            }
        }
        [STAThread]
        static int Main(string[] args)
        {
            string directory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SmartPDV", "agent");
            bool background = args.Contains("--background"), probe = args.Contains("--network-probe");
            for (int i = 0; i < args.Length; i++) if (args[i] == "--data" && i + 1 < args.Length) directory = Path.GetFullPath(args[++i]);
            try
            {
                Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
                if (args.Contains("setup")) { Setup(directory); return 0; }
                string path = Path.Combine(directory, "agent.json");
                if (!File.Exists(path))
                {
                    if (background) return 0;
                    Setup(directory); if (!File.Exists(path)) return 0;
                }
                var config = Configuration.Parse(JsonFiles.Load(path), false);
                ScanKeyboard.MinimumPressMilliseconds = config.KeyboardMinPress;
                if (probe) { Probe(config, directory); return 0; }
                bool created;
                using (var mutex = new Mutex(true, "Local\\SmartPDV-Agent-Win7-" + WindowsIdentity.GetCurrent().User.Value, out created))
                {
                    if (!created) return 0;
                    try { using (var context = new AgentContext(config)) Application.Run(context); }
                    finally { mutex.ReleaseMutex(); }
                }
                return 0;
            }
            catch (Exception ex)
            {
                // Somente metadados de inicializacao; nao salvar o erro completo com dados do cadastro.
                try { JsonFiles.Save(Path.Combine(directory, "legacy-startup-error.json"), new { error = ex.GetType().Name }); } catch (Exception) { }
                if (!background && !probe) MessageBox.Show(ex.Message, "SmartPDV Agent Win7", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }
    }
}
