'use strict';
const $ = id => document.getElementById(id);
let opening = null;
let socket, pdvs = [], selected = null, audio, alarmTimer, reconnectTimer, stopped = true;
let alarm = {enabled:true,repeat_seconds:10}, lastPending = false, lastMove = 0;
const cards = new Map();
let knownPending = new Set();
function send(data) { if(socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(data)); }
function input(event) { if(selected !== null) send({type:'input',number:selected,event}); }
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
    if(!p?.online || (!p.active && !p.pending)) {selected=null;$('remote').close();}
    else if(p.thumbnail) $('screen').src='data:image/jpeg;base64,'+p.thumbnail;
  }
  updateAlarm();
}
function openRemote(number) {
  if(selected!==null && selected!==number) send({type:'end',number:selected,result:'Alternância de PDV'});
  selected=null;
  opening=number; send({type:'start',number});
}
function showRemote(number) {
  selected=number;
  $('remote-title').textContent=`PDV ${number} · Atendimento ativo`;
  $('switch').replaceChildren(...pdvs.filter(p=>p.online).map(p=>new Option(`PDV ${p.number}`,p.number,false,p.number===number)));
  const p=pdvs.find(p=>p.number===number);
  if(p.thumbnail) $('screen').src='data:image/jpeg;base64,'+p.thumbnail;
  if(!$('remote').open) $('remote').showModal();
  $('screen').focus();
}
function endRemote() {
  if(selected!==null) send({type:'end',number:selected,result:'Concluído'});
  selected=null; $('remote').close();
  if(document.fullscreenElement)document.exitFullscreen();
}
function connect() {
  clearTimeout(reconnectTimer);
  socket=new WebSocket(`wss://${location.host}/dashboard`);
  socket.onopen=()=>{$('connection').textContent='● Central conectada · TLS';};
  socket.onmessage=e=>{
    const data=JSON.parse(e.data);
    if(data.type==='state'){pdvs=data.pdvs;alarm=data.alarm;
      $('cards').style.setProperty('--columns',Math.max(1,Math.min(8,data.dashboard.columns||4)));render();}
    else if(data.type==='opened'){showRemote(data.number);opening=null;}
    else if(data.type==='error'){opening=null;alert(data.message);}
    else if(data.type==='frame'){
      const p=pdvs.find(p=>p.number===data.number);if(!p)return;
      p.thumbnail=data.jpeg;const src='data:image/jpeg;base64,'+data.jpeg;
      if(cards.has(p.number))cards.get(p.number).img.src=src;
      if(selected===p.number)$('screen').src=src;
    }
  };
  socket.onclose=async()=>{
    $('connection').textContent='Central desconectada · Reconectando';
    clearInterval(alarmTimer);lastPending=false;selected=null;$('remote').close();
    for(const {card,info} of cards.values()){card.className='card offline';card.disabled=true;info.textContent='Conexão com a Central perdida';}
    if(!stopped){
      try{
        const response=await fetch('/session');
        if(response.status===401){
          stopped=true;$('workspace').hidden=true;$('login').hidden=false;
          $('connection').textContent='Sessão encerrada · Entre novamente';return;
        }
      }catch{ /* A Central pode estar reiniciando. */ }
      if(!stopped)reconnectTimer=setTimeout(connect,3000);
    }
  };
}
$('login').onsubmit=async e=>{
  e.preventDefault();const data=Object.fromEntries(new FormData(e.target));
  try{const response=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    if(!response.ok) throw Error('Credenciais inválidas ou limite de tentativas.');
    $('login').hidden=true;$('workspace').hidden=false;$('error').textContent='';e.target.reset();stopped=false;connect();
  }catch(err){$('error').textContent=err.message;}
};
$('logout').onclick=async()=>{stopped=true;clearTimeout(reconnectTimer);endRemote();await fetch('/logout',{method:'POST'});socket?.close();$('workspace').hidden=true;$('login').hidden=false;};
$('audio').onclick=async()=>{audio ||= new AudioContext();await audio.resume();$('audio').textContent='Alarme ativado';if(lastPending)beep();};
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
for(const action of ['down','up'])screen.addEventListener('key'+action,e=>{if(e.key==='Escape')return;e.preventDefault();input({kind:'key',action,key:e.key});});
screen.onblur=()=>input({kind:'release'});
screen.onpointercancel=()=>input({kind:'release'});
screen.addEventListener('wheel',e=>{e.preventDefault();input({kind:'wheel',delta:e.deltaY<0?120:-120});},{passive:false});

// Restaurar o login ao atualizar a página, sem persistir senha no navegador.
async function restoreSession(){
  try{
    const response=await fetch('/session');
    if(response.ok){$('login').hidden=true;$('workspace').hidden=false;stopped=false;connect();}
  }catch{ $('connection').textContent='Central indisponível'; }
}
restoreSession();
