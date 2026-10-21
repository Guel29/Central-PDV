// Deterministic capture tests. Values are fictitious, not fiscal credentials.
const assert=require('node:assert/strict');
const TimedNumericKeys=require('../smartpdv/web/timed-keys.js');
function setup(enabled=true) {
  const sent=[];let pending=null;
  const keys=new TimedNumericKeys(e=>sent.push(e),()=>enabled,callback=>{pending=callback;return 1;},()=>{pending=null;});
  let stamp=0;
  function key(key,action='down',extra={}) {
    keys.key({key,code:/^[0-9]$/.test(key)?'Digit'+key:key,timeStamp:stamp++,...extra},action);
  }
  function scan(value='001234567890',enter=true) {
    for(const digit of value){key(digit);key(digit,'up');}
    if(enter){key('Enter');key('Enter','up');}
  }
  return {sent,keys,key,scan,idle:()=>pending?.()};
}
{
  const t=setup();t.scan();
  assert.equal(t.sent.length,1);assert.equal(t.sent[0].kind,'key_sequence');
  assert.equal(t.sent[0].events.filter(e=>e.action==='down').map(e=>e.key).join(''),'001234567890Enter');
  assert.deepEqual(t.sent[0].events.map(e=>e.at_ms),Array.from({length:26},(_,i)=>i));
}
{
  const t=setup();t.scan('001234',false);t.idle();
  assert.equal(t.sent.length,1);assert.equal(t.sent[0].events.length,12); // no invented Enter
}
{
  const t=setup(false);t.scan();assert.equal(t.sent.length,26);
  assert(t.sent.every(e=>e.kind==='key' && !('at_ms' in e))); // older Agents
}
{
  const t=setup();t.key('1');t.idle();t.key('1','up');t.scan('2345');
  assert.equal(t.sent[0].action,'down');assert.equal(t.sent[1].action,'up');
  assert.equal(t.sent[2].kind,'key_sequence');assert.equal(t.sent[2].events[0].action,'down');
}
{
  const t=setup();t.scan('0012',false);t.keys.cancel();t.idle();
  assert.equal(t.sent.length,0); // session end, blur, switch or disconnect drops pending capture
}
{
  const t=setup();t.key('Control');t.scan();t.key('Control','up');
  assert(t.sent.every(e=>e.kind==='key')); // do not replay scanner bursts under held modifiers
}
{
  const t=setup();t.scan('12',false);t.key('Tab');t.key('Tab','up');
  assert.equal(t.sent.length,6);assert(t.sent.every(e=>e.kind==='key'));
}
console.log('PASS timed capture: offsets, leading zeros, suffix, old Agents, slow typing, cancellation, modifiers and fallback');
