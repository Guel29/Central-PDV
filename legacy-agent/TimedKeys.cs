using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;

namespace SmartPDV.Legacy
{
    // Bounded observed keyboard timings, not USB/HID redirection.
    static class TimedKeys
    {
        [DllImport("winmm.dll")] static extern uint timeBeginPeriod(uint period);
        [DllImport("winmm.dll")] static extern uint timeEndPeriod(uint period);
        public static List<Dictionary<string,object>> Validate(Dictionary<string,object> value)
        {
            object raw;
            if(value.Count!=2 || !value.TryGetValue("kind",out raw) || (raw as string)!="key_sequence" ||
                !value.TryGetValue("events",out raw)) return null;
            var items=raw as IList;
            if(items==null || items.Count<8 || items.Count>64) return null;
            var result=new List<Dictionary<string,object>>();
            string held=null; int digits=0,last=0; bool ending=false;
            for(int i=0;i<items.Count;i++)
            {
                var item=items[i] as Dictionary<string,object>;
                if(item==null || item.Count!=4 || !item.ContainsKey("key") || !item.ContainsKey("code") ||
                    !item.ContainsKey("action") || !item.ContainsKey("at_ms") || !(item["at_ms"] is int)) return null;
                string key=item["key"] as string, code=item["code"] as string, action=item["action"] as string;
                int at=(int)item["at_ms"];
                if(at<last || at>250 || i==0 && at!=0 || key==null || code==null) return null;
                last=at;
                bool digit=key.Length==1 && key[0]>='0' && key[0]<='9' && (code=="Digit"+key || code=="Numpad"+key);
                bool enter=key=="Enter" && (code=="Enter" || code=="NumpadEnter");
                if(!digit && !enter || digit && ending) return null;
                if(action=="down")
                {
                    if(held!=null || enter && (digits<4 || i!=items.Count-2)) return null;
                    held=code; if(digit)digits++; ending=enter;
                }
                else if(action=="up" && held==code) held=null;
                else return null;
                result.Add(item);
            }
            return held==null && digits>=4 ? result : null;
        }
        public static void Replay(List<Dictionary<string,object>> events, Action<Dictionary<string,object>> send)
        {
            // Restore timer resolution even if SendInput fails. Win7 otherwise
            // commonly rounds Thread.Sleep to a much larger scheduler interval.
            bool timer=timeBeginPeriod(1)==0;
            try
            {
                long started=Stopwatch.GetTimestamp();
                foreach(var item in events)
                {
                    double remaining=(int)item["at_ms"]-(Stopwatch.GetTimestamp()-started)*1000.0/Stopwatch.Frequency;
                    if(remaining>0) Thread.Sleep((int)Math.Ceiling(remaining));
                    send(item);
                }
            }
            finally { if(timer)timeEndPeriod(1); }
        }
    }
}
