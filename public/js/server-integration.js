/* Connect the static app's account forms to the deployed TRADELINE API. */
(()=>{
  'use strict';
  const CFG=window.TL_CONFIG||{};
  const API=(CFG.apiUrl||CFG.chatApi||'').replace(/\/$/,'');
  if(!API)return;

  async function request(path,body,auth=false){
    const headers={'Content-Type':'application/json'};
    const token=sessionStorage.getItem('tl_server_token');
    if(auth&&token)headers.Authorization='Bearer '+token;
    const response=await fetch(API+path,{method:'POST',headers,body:JSON.stringify(body||{})});
    let payload={};
    try{payload=await response.json()}catch(_){ }
    if(!response.ok){const error=new Error(payload.error||'request_failed');error.code=payload.error;error.status=response.status;throw error}
    return payload;
  }

  function showError(message){const el=document.querySelector('#er');if(el)el.textContent=message;else if(typeof toast==='function')toast(message)}
  function syncAccount(account){
    if(!account)return;
    load();
    let user=S.users.find(item=>item.email===account.email);
    if(!user){user={id:'server-'+account.id,email:account.email,name:account.name||account.email,role:'client',pw:null,ok:true};S.users.push(user)}
    user.name=account.name||user.name;
    user.ok=true;
    save();
    signIn(user);
  }

  window.auth=async function(){
    load();
    const email=V('em').toLowerCase();
    const password=document.querySelector('#pw')?.value||'';
    if(!/^\S+@\S+\.\S+$/.test(email)){showError('Enter a valid email address.');return}
    if(password.length<8){showError('Password must contain at least 8 characters.');return}
    try{
      let result;
      if(mode==='up'){
        const name=V('nm')||email;
        if(name.trim().length<2){showError('Enter your name.');return}
        result=await request('/api/auth/register',{name,email,password});
      }else{
        result=await request('/api/auth/login',{email,password});
      }
      if(result.token)sessionStorage.setItem('tl_server_token',result.token);
      sessionStorage.setItem('tl_server_email',email);
      syncAccount(result.account);
    }catch(error){
      if(error.code==='email_exists')showError('This email is already registered. Please sign in.');
      else if(error.code==='invalid_credentials')showError('The email or password is incorrect.');
      else if(error.code==='bad_request')showError('Check your name, email and password (at least 8 characters).');
      else showError('The account service is temporarily unavailable. Please try again shortly.');
    }
  };

  window.out=async function(){
    try{await request('/api/auth/logout',{},true)}catch(_){ }
    sessionStorage.removeItem('tl_server_token');
    sessionStorage.removeItem('tl_server_email');
    document.querySelector('#mod').innerHTML='';
    me=null;
    ssDel('tlu');
    ceid=null;
    go('');
  };
})();
