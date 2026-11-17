/* ---------- AI assistant chat: 5 free generations, then $20 / month ---------- */
const CFG=window.TL_CONFIG||{};
const FREE=5;
SVC.push({id:'ai',g:3,kind:'ai',fx:20,cur:'USD',u:'month',t:'AI Assistant Access',d:'Unlimited AI assistant for 30 days.',long:'Unlimited use of the TRADELINE AI assistant for 30 days: questions about international trade, customs documents, logistics and our services. The assistant gives orientation, not legal advice, and never presents guesses as legal facts.',incl:['Unlimited questions for 30 days','Answers in your language','Renew any time'],bench:'Consumer AI-assistant subscriptions are commonly priced around $20 per month (check current provider pricing).'});
const CK='tlc2',DEMO='The AI engine is not connected in this version of the site, so I cannot generate an answer yet. To get your question answered, write to dovtg@icloud.com or on WhatsApp +48 793 683 931.';
let chatBusy=false,chatCtl=null;
/* ---- storage: conversations (like ChatGPT) ---- */
function cdb(){let o=null;try{o=JSON.parse(stGet(CK)||'null')}catch(e){}
 if(!o||!Array.isArray(o.threads)){o={n:0,cur:null,threads:[]};try{const old=JSON.parse(stGet('tlc1')||'null');if(old&&old.msgs&&old.msgs.length){const t={id:rid(),title:'Earlier chat',ts:Date.now(),msgs:old.msgs};o.threads.push(t);o.cur=t.id;o.n=old.n||0}}catch(e){}}return o}
function csave(o){o.threads=o.threads.slice(0,30);o.threads.forEach(t=>{t.msgs=t.msgs.slice(-40)});stSet(CK,JSON.stringify(o))}
const curT=o=>o.threads.find(t=>t.id===o.cur)||null;
function vid(){let v=stGet('tlv');if(!v){v=rid()+rid()+rid();stSet('tlv',v)}return v}
function aiPaid(){if(!me)return false;if(me.role==='admin')return true;return S.eng.some(e=>e.uid===me.id&&e.sid==='ai'&&e.st==='active'&&(e.until||0)>Date.now())}
function aiUsed(){return Math.max(cdb().n,(me&&me.aiUsed)||0)}
const aiLeft=()=>Math.max(0,FREE-aiUsed());
/* ---- the specification of the assistant ---- */
const SYS=()=>`You are TRADELINE Legal Intelligence, the assistant of TRADELINE EUROPE, a trade-support company in Warsaw, Poland. You help entrepreneurs, importers, exporters and trade specialists with international trade (customs and duties, import and export requirements, documents, VAT and other taxes on cross-border operations, contracts and delivery terms, compliance, logistics) and with the company's services. Jurisdictions: the European Union and Poland first; say clearly when a question is outside them.
Evidence first:
- Never present a guess as a legal fact. Separate what is mandatory from what is only recommended.
- Name the official source where the answer can be checked (EUR-Lex, TARIC, the Polish ISAP and Dziennik Ustaw, the Ministry of Finance). Mention a specific act or article only if you are certain it exists and applies; otherwise say which source to search. Never invent regulation numbers, article numbers, rates or links.
- Law changes and depends on the date. When the date of the operation, the goods (CN/TARIC code), the country of origin or the roles of the parties matter and are missing, ask for them (at most three short questions) and give general orientation meanwhile.
- If you cannot confirm something, say so plainly and say what is missing.
- You give information, not legal advice. For high-risk operations or binding conclusions recommend verification by a qualified specialist or the TRADELINE team.
Style: reply in the user's language; be concise and structured (short paragraphs or bullet lists), about 200 words unless asked for more.
Company services and prices: ${SVC.map(s=>s.t+' ('+prc(s)+')').join('; ')}.`;
async function askAI(all,onPart,signal){let msgs=all.filter(m=>!m.err).slice(-12).map(m=>({role:m.role,content:m.content}));while(msgs.length&&msgs[0].role!=='user')msgs.shift();
 if(CFG.chatApi){const r=await fetch(CFG.chatApi.replace(/\/$/,'')+'/api/chat',{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:msgs,visitor:vid(),email:me?me.email:''})});let j={};try{j=await r.json()}catch(e){}if(r.status===429)return{err:'limit'};if(!r.ok||!j.reply)return{err:'server'};return{text:j.reply}}
 try{const s=window.claude?await window.claude.use('sample'):null;if(s){const turns=msgs.map((m,i)=>i===0?{role:'user',content:SYS()+'\n\nThe conversation starts now. User: '+m.content}:m);const o=await s(turns,{modelTier:'quick',signal,onText:x=>{if(onPart)onPart(x.text)}});return{text:o.text}}}catch(e){return{err:(e&&e.code)||'error',partial:e&&e.text}}
 return{text:DEMO,demo:true}}
const ERR={limit:'The free limit is reached.',not_granted:'You declined to let the assistant use your Claude account. Send again and allow it to continue.',rate_limited:'Too many requests. Please wait a moment.',aborted:'Stopped.',cancelled:'Stopped.',server:'The assistant is unavailable right now. Please try again.'};
/* ---- rendering ---- */
function md(t){const out=[];let list=null;const inl=s=>s.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/`(.+?)`/g,'<code>$1</code>').replace(/(https:\/\/[^\s<)]+)/g,'<a class="lk2" href="$1" target="_blank" rel="noopener">$1</a>');
 for(const l of esc(t).split('\n')){const m=l.match(/^\s*(?:[-*•]|(\d+)[.)])\s+(.*)/);
  if(m){const tag=m[1]?'ol':'ul';if(list!==tag){if(list)out.push('</'+list+'>');out.push('<'+tag+'>');list=tag}out.push('<li>'+inl(m[2])+'</li>')}
  else{if(list){out.push('</'+list+'>');list=null}if(l.trim())out.push('<p>'+inl(l)+'</p>')}}
 if(list)out.push('</'+list+'>');return out.join('')}
const chatEx=['What documents do I need to import wooden furniture from China to Poland?','What changed for low-value parcels entering the EU in 2026?','How is import VAT handled for goods arriving in Poland?','Explain DAP and DDP for a supplier contract'];
function chatMsgs(th,thinking){const m=((th&&th.msgs)||[]).map(x=>x.role==='user'?`<div class="msg me">${esc(x.content).replace(/\n/g,'<br>')}</div>`:`<div class="msg">${md(x.content)}</div>`).join('');
 const empty=!th||!th.msgs.length;
 return (empty?`<div class="msg"><p><b>TRADELINE Legal Intelligence</b></p><p>Ask about customs, duties, import and export requirements, documents, taxes on cross-border operations, contracts and logistics. I name the official source to check, ask for the data I need, and tell you when I cannot confirm something.</p></div>${chatEx.map((t,i)=>`<span class="chip" onclick="chatSend(chatEx[${i}])">${esc(t)}</span>`).join('')}`:m)+(thinking?'<div class="msg" id="live"><span class="mu">Thinking…</span></div>':'')}
function chatFoot(){const paid=aiPaid(),left=aiLeft();
 if(!paid&&left<=0)return `<div class="card" style="margin:8px 0 0;background:var(--bg);border:1px solid var(--ac)"><b>You have used your ${FREE} free generations.</b><p class="sm mu" style="margin:4px 0 8px">Unlimited AI assistant for 30 days: <b>$20 / month</b>. Pay by PayPal, bank transfer or BLIK. The owner confirms the payment and access starts at once.</p><div class="row"><button class="big" onclick="aiBuy()">Get access · $20 / month</button>${me?'':`<button class="g" onclick="mode='in';go('login')">Sign in</button>`}</div></div>`;
 return `<textarea id="chat_in" placeholder="Ask about trade, customs, documents, law…" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();chatSend()}"></textarea><div class="row" style="justify-content:space-between">${chatBusy?'<button class="g" onclick="chatStop()">Stop</button>':'<button onclick="chatSend()">Send</button>'}<span class="sm mu">${paid?(me&&me.role==='admin'?'Owner: unlimited':'Unlimited access'):`${left} of ${FREE} free generations left`}</span></div><p class="sm mu" style="margin:6px 0 0">AI answers can contain mistakes. Check the official sources. This is information, not legal advice.</p>`}
function chatHtml(full){const o=cdb();return `<div class="chat${full?' full':''}" id="chat"><div id="chm" class="chm">${chatMsgs(curT(o),false)}</div><div id="chf">${chatFoot()}</div></div>`}
function chatPage(){const o=cdb();
 return `<div class="eb" style="margin-top:28px">TRADELINE LEGAL INTELLIGENCE</div><h1 style="margin-top:6px">Ask about trade, customs and law</h1><p class="mu" style="max-width:680px">Evidence first: the assistant separates mandatory requirements from recommendations, names the official source to check, and says when it cannot confirm something. For high-risk operations, have a specialist verify the answer.</p>
 <div class="row" style="margin-top:12px"><button class="g" onclick="newChat()">＋ New chat</button><select id="cth" onchange="openChat(this.value)" style="max-width:340px;margin:0">${histOpts(o)}</select></div>
 ${chatHtml(true)}<p class="sm mu" style="margin-top:14px">Need a written, sourced report prepared by our specialists? <a class="lk2" onclick="reqStart(['s13'])">Send a request</a>.</p>`}
function legalPage(){return chatPage()}
function chatScroll(){const m=document.getElementById('chm');if(m)m.scrollTop=m.scrollHeight}
function histOpts(o){return `<option value="">${o.threads.length?'Previous chats':'No previous chats'}</option>${o.threads.map(t=>`<option value="${t.id}" ${t.id===o.cur?'selected':''}>${esc(t.title)}</option>`).join('')}`}
function chatRefresh(th){const m=document.getElementById('chm'),f=document.getElementById('chf'),hs=document.getElementById('cth');if(hs)hs.innerHTML=histOpts(cdb());if(m){m.innerHTML=chatMsgs(curT(cdb()),!!th);chatScroll()}if(f)f.innerHTML=chatFoot()}
function newChat(){const o=cdb();o.cur=null;csave(o);if(route==='legal')draw();else chatRefresh()}
function openChat(id){if(!id)return;const o=cdb();o.cur=id;csave(o);chatRefresh()}
function chatStop(){if(chatCtl)chatCtl.abort()}
function aiBuy(){buyFixed('ai')}
async function chatSend(t){if(chatBusy)return;const inp=document.getElementById('chat_in');t=(t||(inp&&inp.value)||'').trim();if(!t)return;
 if(!aiPaid()&&aiLeft()<=0){chatRefresh();return}
 const o=cdb();let th=curT(o);if(!th){th={id:rid(),title:t.slice(0,48),ts:Date.now(),msgs:[]};o.threads.unshift(th);o.cur=th.id}
 th.msgs.push({role:'user',content:t});csave(o);const tid=th.id,hist=th.msgs.slice();if(inp)inp.value='';chatBusy=true;chatCtl=new AbortController();chatRefresh(true);
 let r;try{r=await askAI(hist,x=>{const l=document.getElementById('live');if(l){l.innerHTML=md(x);chatScroll()}},chatCtl.signal)}catch(e){r={err:e&&e.name==='AbortError'?'aborted':'server'}}
 chatBusy=false;chatCtl=null;const o2=cdb(),t2=o2.threads.find(x=>x.id===tid);if(!t2){chatRefresh();return}
 if(r.text){t2.msgs.push({role:'assistant',content:r.text});
  if(!r.demo&&!aiPaid()){const used=Math.max(o2.n,(me&&me.aiUsed)||0)+1;o2.n=used;if(me){load();const u=S.users.find(x=>x.id===me.id);if(u){u.aiUsed=used;save()}}}}
 else t2.msgs.push({role:'assistant',content:ERR[r.err]||ERR.server,err:true});
 csave(o2);chatRefresh()}
