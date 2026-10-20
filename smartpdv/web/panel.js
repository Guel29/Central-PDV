'use strict';
const operators=document.getElementById('operators');
const message=document.getElementById('operator-message');
const rows=new Map();
async function action(number,action){
  try{
    const r=await fetch('/dev/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({number,action})});
    if(!r.ok)throw Error(r.status===401?'Sessão encerrada: atualize a Central neste computador.':'Não foi possível executar o comando.');
    message.textContent=`PDV ${number}: comando ${action} enviado.`;
    await refresh();
  }catch(e){message.textContent=e.message;}
}
async function refresh(){
  try{
    const r=await fetch('/dev/state');
    if(!r.ok)throw Error('Abra a Central neste computador para continuar.');
    const data=await r.json();
    for(const p of data.pdvs){
      if(!rows.has(p.number)){
        const section=document.createElement('section');section.className='operator-card';
        const title=document.createElement('h2'),status=document.createElement('p'),screen=document.createElement('pre'),bar=document.createElement('nav');
        for(const [text,command] of [['Solicitar liberação (F11)','request'],['Desconectar','disconnect'],['Reconectar','connect'],['Limpar venda simulada','reset']]){
          const button=document.createElement('button');button.textContent=text;button.dataset.action=command;
          button.onclick=()=>action(p.number,command);bar.append(button);
        }
        section.append(title,status,screen,bar);operators.append(section);rows.set(p.number,{title,status,screen,section});
      }
      const row=rows.get(p.number);row.title.textContent=`PDV ${p.number} · SIMULADO`;
      row.status.textContent=!p.online?'Offline':p.active?'Atendimento remoto ativo':p.pending?'Liberação pendente':'Online · Disponível';
      row.screen.textContent=`VENDA DE TESTE\nTotal: R$ 125,90\nResultado: ${p.approved?'LIBERADO':'Aguardando'}\nTexto recebido da Central: ${p.text||'(nenhum)'}\nCursor remoto: ${p.cursor.map(v=>Math.round(v*100)+'%').join(', ')}`;
    }
  }catch(e){message.textContent=e.message;}
}
document.addEventListener('keydown',e=>{if(e.key==='F11'){e.preventDefault();action(1,'request');}});
refresh();setInterval(refresh,1000);
