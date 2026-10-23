// Transport probe only. Does not attach USB, capture a desktop or read a card.
using System;
using System.Linq;
using System.Text;
namespace SmartPDV.Legacy
{
    static class UsbTransportProbe
    {
        public static int Main(string[] args)
        {
            try
            {
                var config=Configuration.Parse(JsonFiles.Load(args[0]),true);
                using(var ws=new LocalWebSocket(config,args[1]))
                {
                    byte[] import=new byte[40];import[0]=1;import[1]=0x11;import[2]=0x80;import[3]=3;
                    byte[] bus=Encoding.ASCII.GetBytes("1-2");Array.Copy(bus,0,import,8,bus.Length);
                    ws.SendBinary(import);
                    byte[] header=ws.ReceiveBinary();
                    if(!header.SequenceEqual(new byte[]{1,0x11,0,3,0,0,0,0})) return 2;
                    if(ws.ReceiveBinary().Length!=312) return 4;
                    byte[] payload=Enumerable.Range(0,65536).Select(n=>(byte)(n%256)).ToArray();
                    ws.SendBinary(payload);
                    int offset=0;
                    while(offset<payload.Length) {
                        byte[] received=ws.ReceiveBinary();
                        if(!received.SequenceEqual(payload.Skip(offset).Take(received.Length))) return 3;
                        offset+=received.Length;
                    }
                    Console.WriteLine("Pinned TLS and binary USB/IP framing passed; no physical USB was tested.");
                    return 0;
                }
            }
            catch(Exception ex) { for(Exception e=ex;e!=null;e=e.InnerException) Console.Error.WriteLine("USB probe: "+e.GetType().Name); Console.Error.WriteLine(ex.StackTrace);return 1; }
        }
    }
}
