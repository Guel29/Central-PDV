// USB transport only: never call the desktop input or keyboard APIs here.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Management;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using System.Threading;

namespace SmartPDV.Legacy
{
    sealed class UsbReader
    {
        static string Package { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "SmartPDV-USB", "Client"); } }
        static string Exe { get { return Path.Combine(Package, "usbip.exe"); } }
        public static bool Available
        {
            get
            {
                try
                {
                    if (Environment.OSVersion.Platform != PlatformID.Win32NT) return false;
                    var approved = JsonFiles.Load(Path.Combine(Package, "approved.json"));
                    if ((string)approved["backend"] != "cezanne-v0.1.0") return false;
                    using (var sha = SHA256.Create())
                    using (var file = File.OpenRead(Exe))
                        return BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").Equals((string)approved["exe_sha256"], StringComparison.OrdinalIgnoreCase);
                }
                catch (Exception) { return false; }
            }
        }
        sealed class Session
        {
            public string Id;
            public readonly ManualResetEvent Stop = new ManualResetEvent(false);
            public TcpListener Listener;
            public TcpClient Socket;
            public LocalWebSocket Tunnel;
            public Process Importer;
            public Thread Worker;
            public void CloseTransport()
            {
                Stop.Set();
                try { if (Listener != null) Listener.Stop(); } catch (SocketException) { }
                if (Tunnel != null) Tunnel.Dispose();
                try { if (Socket != null) Socket.Close(); } catch (ObjectDisposedException) { }
            }
        }
        Session current;
        readonly object gate = new object();
        public void Stop(string expectedLease)
        {
            lock (gate)
            {
                Session old = current;
                if (old == null || expectedLease != null && old.Id != expectedLease) return;
                old.CloseTransport();
                // EOF normally makes the old importer detach its own virtual port.
                if (old.Worker != null && old.Worker != Thread.CurrentThread && !old.Worker.Join(10000))
                    throw new IOException("Componente USB anterior ainda esta encerrando.");
                current = null;
            }
        }
        public void Start(Dictionary<string, object> message, Configuration config, LocalWebSocket control)
        {
            string id = (string)message["lease"], bus = (string)message["busid"], instance = (string)message["instance"];
            if (!Regex.IsMatch(id, "^[A-Za-z0-9_-]{40,64}$") || !Regex.IsMatch(bus, "^[0-9]+-[0-9]+$") ||
                !Regex.IsMatch(instance, @"^USB\\VID_05E0&PID_[0-9A-F]{4}\\[^\\]+$", RegexOptions.IgnoreCase))
                throw new InvalidDataException("Concessao USB invalida.");
            Stop(null);
            if (!Available) { control.Send(new {type="usb_status", lease=id, ok=false}); return; }
            var session = new Session { Id=id };
            lock (gate) { current = session; }
            session.Worker = new Thread(delegate() { Work(session,bus,instance,config,control); }) { IsBackground=true, Name="SmartPDV USB" };
            session.Worker.Start();
        }
        static HashSet<string> Devices(string prefix)
        {
            var found = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            using (var query = new ManagementObjectSearcher("SELECT PNPDeviceID,ConfigManagerErrorCode FROM Win32_PnPEntity"))
            using (var rows = query.Get())
                foreach (ManagementObject device in rows)
                using (device)
                {
                    string id = device["PNPDeviceID"] as string;
                    if (id != null && id.StartsWith(prefix,StringComparison.OrdinalIgnoreCase) &&
                        Convert.ToInt32(device["ConfigManagerErrorCode"]) == 0) found.Add(id);
                }
            return found;
        }
        static byte[] Exact(Stream stream, int length)
        {
            var bytes = new byte[length]; int offset=0;
            while (offset<length) { int n=stream.Read(bytes,offset,length-offset); if (n==0) throw new EndOfStreamException(); offset+=n; }
            return bytes;
        }
        static void Work(Session s, string bus, string instance, Configuration config, LocalWebSocket control)
        {
            Thread upload=null, monitor=null;
            try
            {
                if(s.Stop.WaitOne(0)) return;
                string prefix=instance.Substring(0,instance.LastIndexOf('\\')+1);
                var before=Devices(prefix);
                s.Listener=new TcpListener(IPAddress.Loopback,0); s.Listener.Start(1);
                int port=((IPEndPoint)s.Listener.LocalEndpoint).Port;
                var info=new ProcessStartInfo(Exe,"--tcp-port " + port + " attach -r 127.0.0.1 -b " + bus) {
                    UseShellExecute=false, CreateNoWindow=true, WorkingDirectory=Package,
                    RedirectStandardOutput=true, RedirectStandardError=true
                };
                if(s.Stop.WaitOne(0)) return;
                s.Importer=new Process { StartInfo=info };
                // Drain and discard. Upstream diagnostic output never becomes an app log.
                s.Importer.OutputDataReceived += delegate { }; s.Importer.ErrorDataReceived += delegate { };
                s.Importer.Start(); s.Importer.BeginOutputReadLine(); s.Importer.BeginErrorReadLine();
                var pending=s.Listener.BeginAcceptTcpClient(null,null);
                try
                {
                    if (WaitHandle.WaitAny(new WaitHandle[]{s.Stop,pending.AsyncWaitHandle},10000)!=1) throw new TimeoutException();
                    s.Socket=s.Listener.EndAcceptTcpClient(pending);
                }
                finally { pending.AsyncWaitHandle.Close(); }
                s.Listener.Stop();
                s.Socket.NoDelay=true;
                NetworkStream local=s.Socket.GetStream(); local.ReadTimeout=10000; local.WriteTimeout=5000;
                byte[] preamble=Exact(local,40);
                byte[] expected=new byte[40]; expected[0]=1;expected[1]=0x11;expected[2]=0x80;expected[3]=3;
                byte[] name=System.Text.Encoding.ASCII.GetBytes(bus); Array.Copy(name,0,expected,8,name.Length);
                if (!preamble.SequenceEqual(expected)) throw new InvalidDataException("Importacao USB invalida.");
                s.Tunnel=new LocalWebSocket(config,s.Id);
                if (s.Stop.WaitOne(0)) throw new OperationCanceledException();
                s.Tunnel.SendBinary(preamble); local.ReadTimeout=Timeout.Infinite;
                upload=new Thread(delegate() {
                    try { byte[] buffer=new byte[65536]; int n; while ((n=local.Read(buffer,0,buffer.Length))>0) {
                        byte[] block=new byte[n];Array.Copy(buffer,block,n);s.Tunnel.SendBinary(block);
                    }} catch(Exception) { } finally {s.CloseTransport();}
                }) {IsBackground=true}; upload.Start();
                monitor=new Thread(delegate() {
                    try {
                        DateTime deadline=DateTime.UtcNow.AddSeconds(20); string attached=null;
                        while (!s.Stop.WaitOne(500)) {
                            if(s.Importer.HasExited) throw new IOException();
                            var present=Devices(prefix);
                            if(attached==null) {
                                attached=present.FirstOrDefault(value=>!before.Contains(value));
                                if(attached!=null) control.Send(new {type="usb_status",lease=s.Id,ok=true});
                                else if(DateTime.UtcNow>deadline) throw new TimeoutException();
                            } else if(!present.Contains(attached)) throw new IOException();
                        }
                    } catch(Exception) { } finally {s.CloseTransport();}
                }) {IsBackground=true}; monitor.Start();
                while(!s.Stop.WaitOne(0)) {byte[] bytes=s.Tunnel.ReceiveBinary();local.Write(bytes,0,bytes.Length);}
            }
            catch(Exception) { /* Only technical status; no payload, number or USB trace. */ }
            finally
            {
                s.CloseTransport();
                if(upload!=null) upload.Join(2000);
                if(monitor!=null) monitor.Join(2000);
                if(s.Importer!=null) {
                    try {if(!s.Importer.WaitForExit(3000)) {s.Importer.Kill();s.Importer.WaitForExit(1000);}}
                    catch(InvalidOperationException) { }
                    finally {s.Importer.Dispose();}
                }
                try {control.Send(new {type="usb_status",lease=s.Id,ok=false});} catch(Exception) { }
            }
        }
    }
}
