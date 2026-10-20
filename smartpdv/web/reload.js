'use strict';
// Somente no laboratório: CSS/HTML/JS alterados recarregam as duas abas.
let version;
setInterval(async()=>{
  try{
    const response=await fetch('/dev/version');if(!response.ok)return;
    const current=(await response.json()).version;
    if(version!==undefined&&version!==current)location.reload();
    version=current;
  }catch{ /* Servidor em reinício; a próxima consulta tentará novamente. */ }
},1500);
