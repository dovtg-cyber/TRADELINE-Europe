(()=>{
  'use strict';
  const CFG=window.TL_CONFIG||{};
  const API=(CFG.apiUrl||CFG.chatApi||'').replace(/\/$/,'');
  if(!API)return;

  async function api(path,body,auth=false){
    const headers={'Content-Type':'application/json'};
    const token=sessionStorage.getItem('tl_server_token');
    if(auth&&token)headers.Authorization='Bearer '+token;
    const response=await fetch(API+path,{method:'POST',headers,body:JSON.stringify(body||{})});
    let payload={};try{payload=await response.json()}catch(_){}
    if(!response.ok){const error=new Error(payload.error||'request_failed');error.status=response.status;error.code=payload.error;throw error}
    return payload;
  }

  window.auth=async function(){
    load();const email=V('em').toLowerCase(),password=document.getElementById('pw').value,er=$('#er');
    if(!/^\S+@\S+\.\S+$/.test(email)||password.length<8){er.textContent='Enter a valid email and a password with at least 8 characters.';return}
    try{
      if(mode==='up'){
        await api('/api/auth/register',{name:V('nm')||email,email,password});vemail=email;saveServerEmail(email);go('verify');return;
      }
      const result=await api('/api/auth/login',{email,password});
      sessionStorage.setItem('tl_server_token',result.token);saveServerEmail(email);syncServerAccount(result.account);
    }catch(error){
      if(error.code==='unverified'){vemail=email;go('verify');return}
      if(error.code==='email_exists')er.textContent='This email is already registered.';
      else if(error.code==='invalid_credentials')er.textContent='Wrong email or password.';
      else er.textContent='The account service is temporarily unavailable.';
    }
  };

  function saveServerEmail(email){sessionStorage.setItem('tl_server_email',email)}
  function syncServerAccount(account){
    if(!account)return;
    let u=S.users.find(x=>x.email===account.email);
    if(!u){u={id:'server-'+account.id,email:account.email,name:account.name||account.email,role:'client',pw:null,ok:true};S.users.push(u)}
    u.ok=true;u.name=account.name||u.name;save();signIn(u);
  }

  window.verify=function(){
    const email=vemail||sessionStorage.getItem('tl_server_email')||'';
    return `<h1>Confirm your email</h1><p class="mu">Enter the 6-digit code sent to <b>${esc(email)}</b>.</p><label>Code</label><input id="vc" inputmode="numeric" maxlength="6"><div class="row"><button class="big" onclick="vok()">Confirm</button><button class="g" onclick="vres()">Send again</button></div><p id="er" class="sm" style="color:var(--bad)"></p>`;
  };

  window.vok=async function(){
    const email=vemail||sessionStorage.getItem('tl_server_email')||'';
    try{await api('/api/auth/verify',{email,code:V('vc')});const pw=document.getElementById('pw')?.value||'';if(pw){const login=await api('/api/auth/login',{email,password:pw});sessionStorage.setItem('tl_server_token',login.token);syncServerAccount(login.account)}else{mode='in';toast('Email confirmed. Please sign in.');go('login')}}catch(error){$('#er').textContent='That code is not correct or has expired.'}
  };

  window.vres=async function(){const email=vemail||sessionStorage.getItem('tl_server_email')||'';try{await api('/api/auth/resend',{email});toast('A new code was sent')}catch(_){toast('The email service is temporarily unavailable')}};

  window.out=async function(){try{await api('/api/auth/logout',{},true)}catch(_){ }sessionStorage.removeItem('tl_server_token');sessionStorage.removeItem('tl_server_email');$('#mod').innerHTML='';me=null;ssDel('tlu');ceid=null;go('')};

  window.fpSend=async function(){const email=V('fe').toLowerCase();if(!/^\S+@\S+\.\S+$/.test(email)){$('#er').textContent='Enter a valid email.';return}try{await api('/api/auth/forgot',{email});fp={email};draw()}catch(_){$('#er').textContent='The email service is temporarily unavailable.'}};
  window.fpDo=async function(){const email=fp?.email||'';const password=document.getElementById('f1').value;try{await api('/api/auth/reset',{email,code:V('fc'),password});fp=null;mode='in';toast('Password updated. Please sign in.');go('login')}catch(error){$('#er').textContent=error.code==='invalid_or_expired'?'The code is not correct or has expired.':'Password must contain at least 8 characters.'}};

  const originalAskAI=window.askAI;
  window.askAI=async function(all,onPart,signal){const msgs=all.filter(m=>!m.err).slice(-12).map(m=>({role:m.role,content:m.content}));try{const response=await fetch(API+'/api/chat',{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:msgs,visitor:window.vid?window.vid():localStorage.getItem('tlv')||'visitor0001',email:sessionStorage.getItem('tl_server_email')||''})});let payload={};try{payload=await response.json()}catch(_){ }if(!response.ok)throw payload;return{text:payload.reply||ERR[payload.error]||ERR.server,demo:false,left:payload.left}}catch(error){if(error&&error.error==='limit')throw {err:'limit'};throw error}};
})();
