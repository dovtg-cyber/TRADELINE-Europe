/* ---------- app router ---------- */
function app(){if(!me)return '<h1>Please sign in</h1><button onclick="go(\'login\')">Sign in</button>';return me.role==='admin'?admin():client()}
/* ---------- shared helpers: map, tables, files ---------- */
function P(c){c=String(c||'').trim();if(CITY[c])return[(CITY[c][1]+12)/57*700,(63-CITY[c][0])/30*400];const m=c.match(/^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/);return m?[(+m[2]+12)/57*700,(63-+m[1])/30*400]:null}
function mapHtml(rows){let g='',ln='',miss=[];const used=new Set();
 for(let l=-10;l<=40;l+=10)g+=`<line x1="${(l+12)/57*700}" x2="${(l+12)/57*700}" y1="0" y2="400" stroke="var(--ln)"/>`;for(let a=35;a<=60;a+=5)g+=`<line y1="${(63-a)/30*400}" y2="${(63-a)/30*400}" x1="0" x2="700" stroke="var(--ln)"/>`;
 const dots=Object.keys(CITY).map(c=>{const p=P(c);return `<circle cx="${p[0]}" cy="${p[1]}" r="2" fill="var(--mu)" opacity=".4"/>`}).join('');
 rows.forEach(r=>{const a=P(r.from),b=P(r.to);if(r.from&&!a)miss.push(r.from);if(r.to&&!b)miss.push(r.to);if(a)used.add(r.from);if(b)used.add(r.to);
  if(a&&b){const col=r.st==='Delayed'?'var(--bad)':r.st==='Delivered'?'var(--ok)':'var(--ac)';ln+=`<path d="M${a[0]},${a[1]} Q${(a[0]+b[0])/2},${(a[1]+b[1])/2-30} ${b[0]},${b[1]}" fill="none" stroke="${col}" stroke-width="2.5"><title>${esc(r.ship||'')} ${esc(r.from)} → ${esc(r.to)}</title></path>`}});
 const pts=[...used].map(c=>{const p=P(c);return `<circle cx="${p[0]}" cy="${p[1]}" r="5" fill="var(--fg)"/><text x="${p[0]+8}" y="${p[1]+4}" font-size="12" fill="var(--fg)">${esc(c)}</text>`}).join('');
 return `<svg class="map" viewBox="0 0 700 400">${g}${dots}${ln}${pts}</svg><p class="mu sm" style="margin-top:6px">Route map. Blue: planned or in transit · green: delivered · red: delayed.${miss.length?' Not placed: '+esc([...new Set(miss)].join(', ')):''}</p>`}
function roTable(cols,rows){if(!rows.length)return '<div class="empty">No records yet.</div>';return `<div class="sc"><table><tr>${cols.map(c=>`<th>${c.l}</th>`).join('')}</tr>${rows.map(r=>`<tr>${cols.map(c=>`<td>${esc(r[c.k]||'')}</td>`).join('')}</tr>`).join('')}</table></div>`}
const dlCap=async()=>{try{return window.claude?await window.claude.use('downloads'):null}catch(e){return null}};
async function saveFile(name,data){const d=await dlCap();if(!d){try{const b=data instanceof Blob?data:new Blob([data]),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),4000);toast('Downloading…')}catch(e){toast('Download failed')}return}try{await d.save({filename:name,data});toast('Saved')}catch(e){toast(e.code==='rejected_extension'?'This file type cannot be downloaded here':e.code==='declined'?'Cancelled':'Download failed')}}
async function dlf(e,d,i){const f=S.eng.find(x=>x.id===e).deliv.find(x=>x.id===d).files[i],b=await idb.get(f.fid);if(!b){toast('The file is not available in this browser');return}saveFile(f.name,b)}
function delivHtml(e,all){const ds=all?e.deliv:e.deliv.slice(0,3);if(!ds.length)return '';
 return `<h2>${all?'Documents':'Delivered to you'}</h2>${ds.map(d=>`<div class="card"><b>${esc(d.title)}</b> <span class="sm mu">${dt(d.ts)}</span>${d.note?`<p class="sm" style="margin:6px 0">${esc(d.note)}</p>`:''}<div class="row">${d.files.map((f,i)=>`<button class="g" onclick="dlf('${e.id}','${d.id}',${i})">⬇ ${esc(f.name)}</button>`).join('')||'<span class="sm mu">No files attached</span>'}</div></div>`).join('')}`}
const up=e=>(e.events||[]).filter(v=>dd(v.d)>=new Date(new Date().toDateString())).sort((a,b)=>(a.d+a.tm).localeCompare(b.d+b.tm));
function apptHtml(list,head,eid){if(!list.length)return '';const L={requested:'Awaiting confirmation',proposed:'New time proposed',confirmed:'Confirmed'};
 return (head?`<h2>${head}</h2>`:'')+list.map(v=>{const d=dd(v.d),s=v.st||'confirmed';return `<div class="ap"><div class="dd"><b>${d.getDate()}</b>${d.toLocaleString('en-GB',{month:'short'})}</div><div><b>${esc(v.title||'Consultation')}</b> <span class="tag ${s==='confirmed'?'active':'pending'}">${L[s]}</span><br>${d.toLocaleDateString('en-GB',{weekday:'long'})}${v.tm?', '+esc(v.tm):''}${v.note?`<br><span class="sm mu">${esc(v.note)}</span>`:''}${s==='proposed'&&v.prev?`<br><span class="sm mu">You asked for: ${esc(v.prev)}</span>`:''}${s==='proposed'&&eid?`<br><button style="margin-top:6px" onclick="accEv('${eid}','${v.id}')">Accept this time</button> <span class="sm mu">or write to ${esc(S.mail)}</span>`:''}</div></div>`}).join('')}
function accEv(id,vid){load();const e=S.eng.find(x=>x.id===id),v=e.events.find(x=>x.id===vid);v.st='confirmed';mail(S.mail,'Consultation time accepted',usr(e.uid).email+' accepted '+v.d+' '+(v.tm||''));log('Client accepted the proposed time');save();toast('Time accepted');draw()}
/* exports */
function expData(e){return [COLS.contacts.map(c=>c.l),...e.rows.contacts.map(r=>COLS.contacts.map(c=>r[c.k]||''))]}
const ascii=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/ł/g,'l').replace(/Ł/g,'L').replace(/[^\x20-\x7e]/g,'?');
async function exp(id,f){const e=S.eng.find(x=>x.id===id),a=expData(e),n='tradeline-database-'+new Date().toISOString().slice(0,10);
 if(f==='csv'||f==='gs'){saveFile(n+'.csv','\ufeff'+a.map(r=>r.map(x=>'"'+String(x).replace(/"/g,'""')+'"').join(',')).join('\r\n'));if(f==='gs')toast('In Google Sheets: File → Import → Upload this CSV file');return}
 if(f==='xlsx'){if(!window.XLSX){toast('Excel export is unavailable here');return}const wb=XLSX.utils.book_new();XLSX.utils.book_append_sheet(wb,XLSX.utils.aoa_to_sheet(a),'Database');saveFile(n+'.xlsx',XLSX.write(wb,{bookType:'xlsx',type:'array'}));return}
 if(f==='pdf'){if(!window.jspdf||!window.jspdf.jsPDF){toast('PDF export is unavailable here');return}const d=new window.jspdf.jsPDF({orientation:'landscape'});d.setFontSize(14);d.text('TRADELINE EUROPE — database',14,14);
  if(d.autoTable)d.autoTable({startY:20,head:[a[0].map(ascii)],body:a.slice(1).map(r=>r.map(ascii)),styles:{fontSize:7}});saveFile(n+'.pdf',d.output('arraybuffer'))}}
function expBar(e){return `<div class="row" style="margin:10px 0"><span class="sm mu">Export:</span><button class="g" onclick="exp('${e.id}','xlsx')">Excel</button><button class="g" onclick="exp('${e.id}','pdf')">PDF</button><button class="g" onclick="exp('${e.id}','gs')">Google Sheets</button><button class="g" onclick="exp('${e.id}','csv')">CSV</button></div>`}
/* ---------- client workspace ---------- */
function eLine(e){const s=svc(e.sid);if(e.sub)return 'Ongoing · '+e.rows.proc.filter(r=>r.st!=='Done').length+' open process(es)';
 if(s.kind==='ai')return (e.until||0)>Date.now()?'Active until '+new Date(e.until).toLocaleDateString('en-GB'):'Expired';
 if(s.kind==='consult'){const n=up(e)[0];return n?'Next: '+dd(n.d).toLocaleDateString('en-GB',{day:'numeric',month:'short'})+(n.tm?', '+n.tm:''):'Time to be agreed'}
 if(s.kind==='contacts')return e.ready?'Ready · '+e.rows.contacts.length+' records':'In preparation';
 if(s.kind==='logi')return e.rows.ship.length+' shipment(s) on your map';
 return e.st==='done'?'Completed':e.deliv.length?e.deliv.length+' delivered':'In progress'}
function client(){const my=S.eng.filter(e=>e.uid===me.id),rs=S.requests.filter(r=>r.uid===me.id).slice().reverse(),ns=S.notes.filter(n=>n.uid===me.id);
 if(ceid){const e=my.find(x=>x.id===ceid);if(e)return cView(e);ceid=null}
 const un=ns.filter(n=>!n.read).length;
 return `<div class="eb" style="margin-top:28px">Workspace</div><h1 style="margin-top:6px">Hello, ${esc(me.name)}</h1>
 ${ns.length?`<h2>Notifications ${un?`<span class="bd">${un}</span>`:''}</h2>${ns.slice(0,5).map(n=>`<div class="nt ${n.read?'':'u'}" onclick="rdN('${n.id}')"><b>${esc(n.t)}</b><span class="sm">${esc(n.body)}</span><br><span class="sm mu">${dt(n.ts)}</span></div>`).join('')}${un?'<button class="g" onclick="rdN()">Mark all as read</button>':''}`:''}
 <h2>Your services</h2>${my.length?`<div class="grid">${my.map(e=>{const s=svc(e.sid);return `<a class="sv" onclick="ceid='${e.id}';ctab='ov';cq='';draw()"><div class="mu sm">${SG[s.g]}</div><b>${esc(s.t)}</b><span class="mu sm">${eLine(e)}</span></a>`}).join('')}</div>`:`<div class="empty">Nothing here yet.<br>Choose a service or send a request.<br><br><button onclick="go('services')">Browse services</button></div>`}
 <h2>Requests and orders</h2>${rs.map(rcard).join('')||'<p class="mu sm">No requests yet.</p>'}<div class="row"><button onclick="reqStart([])">New request</button></div>`}
function rdN(id){load();S.notes.forEach(n=>{if(n.uid===me.id&&(!id||n.id===id)){n.read=true;if(id&&n.eid&&S.eng.find(e=>e.id===n.eid))ceid=n.eid}});save();draw()}
function cView(e){const s=svc(e.sid);let b;
 if(e.sub)b=dept(e);else if(s.kind==='consult')b=(up(e).length?apptHtml(up(e),'',e.id):`<div class="card"><b>Not scheduled yet</b><br><span class="sm mu">We will agree the date and time with you. The appointment will appear here and you will be notified by email.</span></div>`)+delivHtml(e,true);
 else if(s.kind==='ai')b=`<div class="card"><b>Active until ${new Date(e.until||0).toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric'})}</b><br><span class="sm mu">Unlimited questions to the assistant.</span><div class="row" style="margin-top:8px"><button class="g" onclick="buyFixed('ai')">Renew for 30 days</button></div></div>${chatHtml()}`;
 else if(s.kind==='logi')b=(e.rows.ship.length?mapHtml(e.rows.ship)+'<h2>Shipments</h2>'+roTable(COLS.ship,e.rows.ship):'<div class="empty">Your shipments will appear on the map once we enter them.</div>')+apptHtml(up(e),'Appointments',e.id)+delivHtml(e,true);
 else if(s.kind==='contacts')b=e.ready?expBar(e)+`<input placeholder="Search…" value="${esc(cq)}" oninput="cq=this.value;fillC('${e.id}')"><div id="ct">${cTable(e)}</div>`+delivHtml(e,true):`<div class="card"><b>In preparation</b><br><span class="sm mu">We are building your database. You will be notified by email when it is ready.</span></div>`;
 else{const a=up(e)[0];b=`<div class="card"><b>${e.st==='done'?'✓ Completed':'In progress'}</b><br><span class="sm mu">${e.st==='done'?'Your order is complete. The documents are below.':'We are working on it. Documents appear here and you are notified by email.'}</span></div>${a?`<div class="card" style="border:1px dashed var(--ac)"><b>Reminder</b><br>Consultation on ${dd(a.d).toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long'})}${a.tm?' at '+esc(a.tm):''}${a.note?` — ${esc(a.note)}`:''}</div>`:''}`+delivHtml(e,true)}
 return `<p><a class="lk" onclick="ceid=null;draw()">← Workspace</a></p><div class="mu sm">${SG[s.g]}</div><h1 style="margin-top:4px">${esc(s.t)}</h1>${b}`}
function cTable(e){const t=cq.toLowerCase();return roTable(COLS.contacts,e.rows.contacts.filter(r=>!t||JSON.stringify(Object.values(r)).toLowerCase().includes(t)))}
function fillC(id){const e=S.eng.find(x=>x.id===id);$('#ct').innerHTML=cTable(e)}
function dept(e){const T=[['ov','Overview'],['proc','Processes'],['ship','Shipments'],['docs','Documents'],['con','Contacts']],pr=e.rows.proc,sh=e.rows.ship;let b;
 if(ctab==='ov')b=`<div class="card"><b>Your operations department</b><br><span class="sm mu">TRADELINE runs your trade operations from Poland. Everything we do for you appears here: processes, shipments, documents and updates.</span></div>
  <div class="kp"><div><b>${pr.filter(r=>r.st!=='Done').length}</b><span class="sm mu">open processes</span></div><div><b>${sh.filter(r=>r.st!=='Delivered').length}</b><span class="sm mu">shipments en route</span></div><div><b>${e.deliv.length}</b><span class="sm mu">deliveries</span></div></div>
  ${apptHtml(up(e),'Appointments',e.id)}<h2>Latest updates</h2>${e.feed.length?e.feed.slice(0,8).map(f=>`<div class="nt"><span class="sm mu">${dt(f.ts)}</span><br>${esc(f.t)}</div>`).join(''):'<p class="mu sm">No updates yet.</p>'}${delivHtml(e,false)}`;
 else if(ctab==='proc')b=roTable(COLS.proc,pr);
 else if(ctab==='ship')b=sh.length?mapHtml(sh)+'<h2>Shipments</h2>'+roTable(COLS.ship,sh):'<div class="empty">No shipments yet.</div>';
 else if(ctab==='docs')b=e.deliv.length?delivHtml(e,true):'<div class="empty">No documents yet.</div>';
 else b=expBar(e)+`<input placeholder="Search…" value="${esc(cq)}" oninput="cq=this.value;fillC('${e.id}')"><div id="ct">${cTable(e)}</div>`;
 return `<div class="tabs">${T.map(([k,l])=>`<button class="${ctab===k?'on':''}" onclick="ctab='${k}';draw()">${l}</button>`).join('')}</div>${b}`}
