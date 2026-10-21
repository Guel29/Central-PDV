'use strict';
// Numeric bursts only. This does not identify a USB device or create one remotely.
class TimedNumericKeys {
  constructor(send, enabled, schedule=(callback,ms)=>setTimeout(callback,ms), unschedule=id=>clearTimeout(id)) {
    this.send=send; this.enabled=enabled; this.schedule=schedule; this.unschedule=unschedule;
    this.events=[]; this.held=new Set(); this.timer=null;
  }
  cancel() {
    this.unschedule(this.timer); this.timer=null; this.events=[]; this.held.clear();
  }
  flush() {
    this.unschedule(this.timer); this.timer=null;
    const events=this.events; this.events=[];
    const digits=events.filter(e=>e.action==='down' && e.key!=='Enter').length;
    const balanced=this.held.size===0;
    if(events.length && digits>=4 && balanced && this.enabled()) {
      const start=events[0].stamp;
      this.send({kind:'key_sequence',events:events.map(({key,code,action,stamp})=>({key,code,action,at_ms:Math.round(stamp-start)}))});
    } else for(const {key,code,action} of events)this.send({kind:'key',key,code,action});
  }
  key(e,action) {
    const key=e.key,code=e.code,stamp=e.timeStamp;
    const digit=/^[0-9]$/.test(key) && (code==='Digit'+key || code==='Numpad'+key);
    const enter=key==='Enter' && ['Enter','NumpadEnter'].includes(code);
    const modifiers=e.ctrlKey || e.altKey || e.shiftKey || e.metaKey || e.isComposing || e.repeat;
    const start=this.events.length ? this.events[0].stamp : stamp;
    const previous=this.events[this.events.length-1];
    const candidate=this.enabled() && !modifiers && Number.isFinite(stamp) && stamp>=start &&
      Math.round(stamp-start)<=250 && this.events.length<64 &&
      (digit || enter && this.events.length>0) &&
      (!previous || previous.key!=='Enter' || action==='up' && code===previous.code) &&
      (action==='down' ? this.held.size===0 : this.events.length>0 && this.held.has(code));
    if(!candidate) {
      this.flush();
      this.send({kind:'key',key,code,action});
    } else {
      this.events.push({key,code,action,stamp});
    }
    if(action==='down')this.held.add(code); else this.held.delete(code);
    if(this.events.length) {
      this.unschedule(this.timer);
      if(enter && action==='up')this.flush();
      else this.timer=this.schedule(()=>this.flush(),35);
    }
  }
}
if(typeof module!=='undefined')module.exports=TimedNumericKeys;
