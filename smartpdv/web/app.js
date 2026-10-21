'use strict';
const $ = id => document.getElementById(id);
let opening = null;
let socket, pdvs = [], selected = null, audio, alarmTimer, reconnectTimer, stopped = true;
let alarm = {enabled:true,repeat_seconds:10}, lastPending = false, lastMove = 0;
const cards = new Map();
let peripherals = {keyboard:true,mouse:true};
let peripheralsDirty = false, savingPeripherals = false;
let knownPending = new Set();
function send(data) { if(socket?.readyState !== WebSocket.OPEN)return false;socket.send(JSON.stringify(data));return true; }
function input(event) {
  if(selected === null)return;
  if(event.kind==='key' && !peripherals.keyboard)return;
  if(['mouse','wheel'].includes(event.kind) && !peripherals.mouse)return;
  send({type:'input',number:selected,event});
}
function updatePeripherals() {
  if(!peripheralsDirty && !savingPeripherals)for(const key of ['keyboard','mouse'])$('allow-'+key).checked=peripherals[key];
  for(const key of ['keyboard','mouse'])$('allow-'+key).disabled=savingPeripherals || socket?.readyState!==WebSocket.OPEN;
  $('save-peripherals').disabled=savingPeripherals || socket?.readyState!==WebSocket.OPEN;
  $('windows-key').disabled=!peripherals.keyboard || selected===null;
  $('control-help').textContent=`Teclado ${peripherals.keyboard?'autorizado':'desativado'} · Mouse ${peripherals.mouse?'autorizado':'desativado'} · Clique na imagem para controlar · Esc no PDV; na tela cheia, o navegador pode sair`;
}
function beep() {
  if(!audio || audio.state !== 'running' || !alarm.enabled) return;
  for(let i=0;i<3;i++) {
    const osc=audio.createOscillator(), gain=audio.createGain(), t=audio.currentTime+i*.22;
    osc.frequency.value=1100; osc.type='square'; gain.gain.value=.035;
    osc.connect(gain); gain.connect(audio.destination); osc.start(t); osc.stop(t+.12);
  }
}
function updateAlarm() {
  const current = new Set(pdvs.filter(p=>p.online && p.pending).map(p=>`${p.number}:${p.requested_at}`));
  const pending=current.size>0;
  if(lastPending && [...current].some(id=>!knownPending.has(id)))beep();
  knownPending=current;
  if(pending && !lastPending) { beep(); alarmTimer=setInterval(beep,Math.max(10,alarm.repeat_seconds)*1000); }
  if(!pending) {clearInterval(alarmTimer);alarmTimer=null;}
  lastPending=pending;
}
function render() {
  $('summary').textContent=`${pdvs.filter(p=>p.online).length}/${pdvs.length} PDVs online · ${pdvs.filter(p=>p.pending && p.online).length} solicitações`;
  for(const p of pdvs) {
    if(!cards.has(p.number)) {
      const card=document.createElement('button'), title=document.createElement('h2'), img=document.createElement('img'), info=document.createElement('p');
      img.alt=`Miniatura do PDV ${p.number}`; card.append(title,img,info); card.onclick=()=>openRemote(p.number);
      $('cards').append(card); cards.set(p.number,{card,title,img,info});
    }
    const {card,title,img,info}=cards.get(p.number);
    card.className='card'+(!p.online?' offline':p.pending?' pending':p.active?' active':'');
    title.textContent=`PDV ${String(p.number).padStart(2,'0')}`;
    info.textContent=!p.online?'Desconectado':p.pending?'LIBERAÇÃO SOLICITADA':p.active?`Atendimento · ${p.supervisor}`:'Online · Disponível';
    if(p.thumbnail) img.src='data:image/jpeg;base64,'+p.thumbnail; else img.removeAttribute('src');
    card.disabled=!p.online;
  }
  if(selected!==null) {
    const p=pdvs.find(p=>p.number===selected);
    if(!p?.online || (!p.active && !p.pending)) {selected=null;updatePeripherals();$('remote').close();}
    else if(p.thumbnail) $('screen').src='data:image/jpeg;base64,'+p.thumbnail;
  }
  updateAlarm();
}
function openRemote(number) {
  input({kind:'release'});
  if(selected!==null && selected!==number) send({type:'end',number:selected,result:'Alternância de PDV'});
  selected=null;updatePeripherals();
  opening=number; send({type:'start',number});
}
function showRemote(number) {
  selected=number;
  $('remote-title').textContent=`PDV ${number} · Atendimento ativo`;
  $('input-status').textContent='Entrada remota: aguardando teclado';
  updatePeripherals();
  $('switch').replaceChildren(...pdvs.filter(p=>p.online).map(p=>new Option(`PDV ${p.number}`,p.number,false,p.number===number)));
  const p=pdvs.find(p=>p.number===number);
  if(p.thumbnail) $('screen').src='data:image/jpeg;base64,'+p.thumbnail;
  if(!$('remote').open) $('remote').showModal();
  $('screen').focus();
}
function endRemote() {
  input({kind:'release'});
  if(selected!==null) send({type:'end',number:selected,result:'Concluído'});
  selected=null;updatePeripherals();$('remote').close();
  if(document.fullscreenElement)document.exitFullscreen();
}
function connect() {
  clearTimeout(reconnectTimer);
  socket=new WebSocket(`wss://${location.host}/dashboard`);
  socket.onopen=()=>{$('connection').textContent='● Central conectada · TLS';updatePeripherals();};
  socket.onmessage=e=>{
    const data=JSON.parse(e.data);
    if(data.type==='state'){pdvs=data.pdvs;alarm=data.alarm;
      peripherals=data.peripherals || {keyboard:true,mouse:true};
      updatePeripherals();
      if(!peripheralsDirty && !savingPeripherals)$('peripherals-status').textContent='Autorizações aplicadas na Central';
      $('cards').style.setProperty('--columns',Math.max(1,Math.min(8,data.dashboard.columns||4)));render();}
    else if(data.type==='opened'){showRemote(data.number);opening=null;}
    else if(data.type==='error'){
      opening=null;
      if(savingPeripherals){savingPeripherals=false;$('peripherals-status').textContent=data.message;}
      updatePeripherals();alert(data.message);
    }
    else if(data.type==='peripherals_saved'){
      peripheralsDirty=false;savingPeripherals=false;updatePeripherals();
      $('peripherals-status').textContent='Autorizações salvas neste computador';
    }
    else if(data.type==='input_status' && selected===data.number){
      $('input-status').textContent=data.accepted
        ? 'Windows aceitou a entrada · confirme o resultado no aplicativo'
        : `Windows recusou a entrada remota (código ${data.error_code})`;
    }
    else if(data.type==='frame'){
      const p=pdvs.find(p=>p.number===data.number);if(!p)return;
      p.thumbnail=data.jpeg;const src='data:image/jpeg;base64,'+data.jpeg;
      if(cards.has(p.number))cards.get(p.number).img.src=src;
      if(selected===p.number)$('screen').src=src;
    }
  };
  socket.onclose=async()=>{
    $('connection').textContent='Central desconectada · Reconectando';
    clearInterval(alarmTimer);lastPending=false;selected=null;savingPeripherals=false;updatePeripherals();$('remote').close();
    $('peripherals-status').textContent='Central desconectada · alterações não confirmadas';
    for(const {card,info} of cards.values()){card.className='card offline';card.disabled=true;info.textContent='Conexão com a Central perdida';}
    if(!stopped){
      try{
        const response=await fetch('/session');
        if(response.status===401){
          stopped=true;$('connection').textContent='Acesso local indisponível';return;
        }
      }catch{ /* A Central pode estar reiniciando. */ }
      if(!stopped)reconnectTimer=setTimeout(connect,3000);
    }
  };
}
$('audio').onclick=async()=>{audio ||= new AudioContext();await audio.resume();$('audio').textContent='Alarme ativado';if(lastPending)beep();};
$('peripherals-form').onchange=()=>{peripheralsDirty=true;$('peripherals-status').textContent='Alterações ainda não salvas';};
$('peripherals-form').onsubmit=e=>{
  e.preventDefault();
  const settings=Object.fromEntries(['keyboard','mouse'].map(key=>[key,$('allow-'+key).checked]));
  if(!send({type:'peripherals',settings}))return;
  savingPeripherals=true;updatePeripherals();$('peripherals-status').textContent='Salvando autorizações…';
};
$('windows-key').onpointerdown=e=>e.preventDefault();
$('windows-key').onclick=()=>{
  input({kind:'release'});
  for(const action of ['down','up'])input({kind:'key',key:'Meta',code:'MetaLeft',action});
  $('screen').focus();
};
$('close').onclick=endRemote;$('remote').addEventListener('cancel',e=>{e.preventDefault();endRemote();});
$('switch').onchange=e=>openRemote(Number(e.target.value));
$('fullscreen').onclick=async()=>{
  try{if(document.fullscreenElement)await document.exitFullscreen();else await $('remote-content').requestFullscreen();}
  catch{$('connection').textContent='Tela cheia indisponível neste navegador';}
};
document.addEventListener('fullscreenchange',()=>{$('fullscreen').textContent=document.fullscreenElement?'Sair da tela cheia':'Tela cheia';});
const screen=$('screen');
function point(e,action){
  const r=screen.getBoundingClientRect(), ratio=(screen.naturalWidth||16)/(screen.naturalHeight||9);
  let width=r.width,height=width/ratio;if(height>r.height){height=r.height;width=height*ratio;}
  const x=(e.clientX-r.left-(r.width-width)/2)/width,y=(e.clientY-r.top-(r.height-height)/2)/height;
  if((x<0||x>1||y<0||y>1)&&action!=='up')return;
  input({kind:'mouse',action,x:Math.max(0,Math.min(1,x)),y:Math.max(0,Math.min(1,y)),button:e.button===2?2:0});
}
screen.onpointermove=e=>{if(performance.now()-lastMove>35){point(e,'move');lastMove=performance.now();}};
screen.onpointerdown=e=>{e.preventDefault();screen.focus();screen.setPointerCapture(e.pointerId);point(e,'down');};
screen.onpointerup=e=>{e.preventDefault();point(e,'up');};screen.oncontextmenu=e=>e.preventDefault();
for(const action of ['down','up'])screen.addEventListener('key'+action,e=>{e.preventDefault();input({kind:'key',action,key:e.key,code:e.code});});
screen.onblur=()=>input({kind:'release'});
screen.onpointercancel=()=>input({kind:'release'});
screen.addEventListener('wheel',e=>{e.preventDefault();input({kind:'wheel',delta:e.deltaY<0?120:-120});},{passive:false});

// Entrada direta, restrita ao computador Central, com sessão local automática.
async function restoreSession(){
  try{
    const response=await fetch('/session');
    if(!response.ok)throw Error('Abra o dashboard no próprio computador Central.');
    stopped=false;connect();
  }catch(e){$('connection').textContent=e.message;}
}
restoreSession();
