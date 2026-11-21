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
  function saveServerEmail(email){sessionStorage.setItem('tl_server_email',email)}
  function syncServerAccount(account){
    if(!account)return;
    let u=S.users.find(x=>x.email===account.email);
    if(!u){u={id:'server-'+account.id,email:account.email,name:account.name||account.email,role:'client',pw:null,ok:true};S.users.push(u)}
    u.ok=true;u.name=account.name||u.name;save();signIn(u);
  }
  function acceptLogin(result,email){sessionStorage.setItem('tl_server_token',result.token);saveServerEmail(email);syncServerAccount(result.account)}

  window.auth=async function(){
    load();const email=V('em').toLowerCase(),password=document.getElementById('pw').value,er=$('#er');
    if(!/^\S+@\S+\.\S+$/.test(email)||password.length<8){er.textContent='Enter a valid email and a password with at least 8 characters.';return}
    try{
      if(mode==='up'){
        const result=await api('/api/auth/register',{name:V('nm')||email,email,password});acceptLogin(result,email);return;
      }
      const result=await api('/api/auth/login',{email,password});acceptLogin(result,email);
    }catch(error){
      if(error.code==='email_exists')er.textContent='This email is already registered. Sign in with your password.';
      else if(error.code==='invalid_credentials')er.textContent='Wrong email or password.';
      else er.textContent='The account service is temporarily unavailable.';
    }
  };

  window.verify=function(){return '<h1>Email confirmation is off</h1><p class="mu">No email code is needed. Sign in with your email and password.</p><button onclick="mode=\'in\';go(\'login\')">Go to sign in</button>';};
  window.vok=function(){mode='in';go('login');};
  window.vres=function(){toast('Email confirmation is disabled.');};
  window.out=async function(){try{await api('/api/auth/logout',{},true)}catch(_){}sessionStorage.removeItem('tl_server_token');sessionStorage.removeItem('tl_server_email');$('#mod').innerHTML='';me=null;ssDel('tlu');go('')};

  window.forgot=function(){return '<h1>Password reset unavailable</h1><p class="mu">Email recovery is disabled. Keep your password safe; contact TRADELINE support if you lose access.</p><button onclick="mode=\'in\';go(\'login\')">Back to sign in</button>';};
  window.fpSend=function(){toast('Email recovery is disabled.');};
  window.fpDo=function(){toast('Email recovery is disabled.');};

  window.askAI=async function(all,onPart,signal){
    const msgs=all.filter(m=>!m.err).slice(-12).map(m=>({role:m.role,content:m.content}));
    try{
      const response=await fetch(API+'/api/chat',{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:msgs,visitor:vid(),email:me&&me.email||''})});
      const payload=await response.json();
      if(!response.ok)return {err:payload.error==='limit'?'limit':payload.error==='not_configured'?'server':'server'};
      return {text:payload.reply};
    }catch(error){if(error&&error.name==='AbortError')return {err:'aborted'};return {err:'server'};}
  };
})();
