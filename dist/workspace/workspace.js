'use strict';
const $=s=>document.querySelector(s),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const idx=()=>({vi:0,en:1,fr:2,de:3}[I18n.language]??1),t=(key)=>WorkspaceLabels[key]?.[idx()]??key;
let demo,live=false,ready=false,role=['cashier','manager','owner'].includes(new URL(location.href).searchParams.get('role'))?new URL(location.href).searchParams.get('role'):'cashier',view='tables',branch='q1',month='2026-11',currency=new URL(location.href).searchParams.get('currency')==='EUR'?'EUR':'GBP';
let session,data,summary,selected='T1',category='all',basket=[],receipt=null,trail=[],editId=null,errorDetail='',busy=false,serverOffset=0,accountIdentity=null,secretKey=null,pendingCheckout=null,verifiedPromotion=null,promotionDraft='';
const money=v=>v==null?t('notConfigured'):new Intl.NumberFormat(I18n.locale,{style:'currency',currency:session?.currency||currency}).format(v/100);
const num=v=>new Intl.NumberFormat(I18n.locale,{maximumFractionDigits:2}).format(v);
const ingredientName=(id,fallback)=>({rice:['Gạo','Rice','Riz','Reis'],chicken:['Thịt gà','Chicken','Poulet','Hähnchen']}[id]?.[idx()]||fallback||id);
const itemName=p=>p.names?.[I18n.language]||p.name||p.id;
const monthAt=(value,zone='Europe/Paris')=>{const parts=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit'}).formatToParts(new Date(value));return parts.find(p=>p.type==='year').value+'-'+parts.find(p=>p.type==='month').value};
const dateLabel=v=>v?new Intl.DateTimeFormat(I18n.locale,{dateStyle:'short',timeStyle:'short',timeZone:session?.timezone||'Europe/London'}).format(new Date(v)):'—';
const roleKey=r=>r==='manager'?'manager':r==='owner'?'owner':'cashier';
function toast(key){$('#toast').textContent=t(key);$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,4500)}
function failure(e){errorDetail=e.message;render();toast('error')}
async function api(path,body,key){const r=await fetch('/api/'+path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json','Idempotency-Key':key||crypto.randomUUID()}:{},...(body?{body:JSON.stringify(body)}:{})});let result;try{result=await r.json()}catch{throw Error('Backend response was not JSON')};if(!r.ok)throw Error(typeof result.detail==='string'?result.detail:'Request rejected');return result}
function input(id,key,value='',type='text',attrs=''){return `<label>${t(key)}<input id="${id}" type="${type}" value="${esc(value)}" ${attrs}></label>`}
function select(id,key,options,value){return `<label>${t(key)}<select id="${id}">${options.map(([v,l])=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(l)}</option>`).join('')}</select></label>`}
function details(title,id,fields,button='save',enabled=true){return `<details class="form-panel"><summary>${t(title)}</summary><form id="${id}"><div class="form-grid">${fields}</div><button class="primary" ${enabled?'':'disabled'}>${t(button)}</button></form></details>`}
function row(key,value){return `<div class="money-row"><span>${t(key)}</span><b>${money(value)}</b></div>`}
function metric(key,value,hint=''){return `<article class="metric"><span>${t(key)}</span><strong>${value}</strong>${hint?`<small>${t(hint)}</small>`:''}</article>`}
function catalog(){return role==='cashier'?session.catalog:data?.catalog||[]}
function localDay(){return new Intl.DateTimeFormat('en-CA',{timeZone:session?.timezone||'Europe/London',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(live?Date.now()+serverOffset:session?.server_now||'2026-11-08T12:00:00Z'))}
function amount(id){const v=$('#'+id).value.trim().replace(',','.');if(!/^\d+(\.\d{1,2})?$/.test(v))throw Error('Invalid monetary amount');const [a,b='']=v.split('.');const n=Number(a)*100+Number(b.padEnd(2,'0'));if(!Number.isSafeInteger(n))throw Error('Amount too large');return n}
function clock(){const s=session?.active_shift;if(!s)return '00:00:00';const end=live?Date.now()+serverOffset:new Date(session.server_now).getTime(),sec=Math.max(0,Math.floor((end-new Date(s.started_at).getTime())/1000));return [Math.floor(sec/3600),Math.floor(sec/60)%60,sec%60].map(x=>String(x).padStart(2,'0')).join(':')}
async function fetchDemo(){const r=await fetch(currency==='EUR'?'demo-eur.json':'demo.json',{cache:'no-store'});if(!r.ok)throw Error('Demo not available');demo=await r.json()}
async function load(auto=false){
 if(!live){if(role==='cashier'){session=demo.cashier.session;summary=demo.cashier.summary}else{data=role==='owner'&&!['branch','branchSettings','stock','staff','promotion'].includes(view)?demo.owner:demo.owner.branches.find(b=>b.branch_id===branch)||demo.manager;session={name:t(roleKey(role)),role,branches:demo.owner.branches.map(b=>b.branch_id),currency,timezone:currency==='EUR'?'Europe/Paris':'Europe/London',server_now:'2026-11-08T12:00:00Z'}}render();return}
 session=auto?await api('workspace/session/open',{branch_id:branch}):await api('workspace/session?branch='+encodeURIComponent(branch));role=session.role;currency=session.currency;if(auto)month=monthAt(session.server_now,session.timezone||'Europe/Paris');serverOffset=new Date(session.server_now).getTime()-Date.now();
 if(role==='cashier')summary=await api('workspace/shifts?branch='+encodeURIComponent(branch));else data=role==='owner'&&!['branch','branchSettings','stock','staff','promotion'].includes(view)?await api('workspace/owner?month='+month):await api('workspace/management?branch='+encodeURIComponent(branch)+'&month='+month);
 if(role==='manager'&&session.employee_id)summary=await api('workspace/shifts?branch='+encodeURIComponent(branch));
 render();
}
function nav(next){if(view==='receipt')return;trail.push(view);view=next;errorDetail='';if(role==='owner')load(false).catch(failure);else render();window.scrollTo({top:0,behavior:'instant'})}
function back(){if(view==='receipt')return;if(trail.length){view=trail.pop();if(role==='owner')load(false).catch(failure);else render()}else location.href='../'}
function header(){return `<header class="topbar"><a class="brand" href="../"><img src="../assets/icon-192.png" alt="" width="38" height="38"><span>bếp<span>finance</span></span></a><div class="top-actions"><button id="backButton" class="quiet" ${view==='receipt'?'disabled':''}>← ${t('back')}</button><label class="sr-only" for="language">Language</label><select id="language" aria-label="Language"><option value="vi" ${I18n.language==='vi'?'selected':''}>Tiếng Việt</option><option value="en" ${I18n.language==='en'?'selected':''}>English</option><option value="fr" ${I18n.language==='fr'?'selected':''}>Français</option><option value="de" ${I18n.language==='de'?'selected':''}>Deutsch</option></select><select id="currency" aria-label="${t('currency')}" ${live||view==='receipt'?'disabled':''}><option value="GBP" ${currency==='GBP'?'selected':''}>GBP · £</option><option value="EUR" ${currency==='EUR'?'selected':''}>EUR · €</option></select>${live?`<button id="logout" class="quiet">${t('logout')}</button>`:''}</div></header>`}
function sidebar(){const tabs=role==='cashier'?['tables','menu','payment','handover']:role==='manager'?['overview','stock','staff','promotion','settings','accounts',...(session.employee_id?['handover']:[])]:['branch','branchSettings','stock','staff','promotion'].includes(view)?['branch','stock','staff','promotion','branchSettings','overview']:['overview','forecast','settings','accounts'];return `<aside class="sidebar"><div class="workspace-label">${t(roleKey(role))}<small>${esc(session?.name||'Bếp Finance')}</small></div><nav>${tabs.map((key,i)=>`<button data-nav="${key}" ${view==='receipt'?'disabled':''} class="${view===key?'active':''}"><span class="nav-number">${String(i+1).padStart(2,'0')}</span>${t(key==='branch'?'overview':key==='branchSettings'?'settings':key)}</button>`).join('')}</nav><div class="side-bottom"><img src="../assets/bep-nho.webp" alt="Bếp Nhỏ" width="100" height="100"><p>${t(live?'ledgerHint':'currencyHint')}</p></div></aside>`}
function toolbar(){return `<div class="scope"><div class="badge ${live?'live':''}">${t(live?'live':'demo')}</div><div class="scope-fields">${role!=='cashier'?select('branch','branch',(session?.branches||['q1']).map(b=>[b,b]),branch)+input('month','month',month,'month'):''}<button id="refresh" class="quiet">↻ ${t('refresh')}</button></div></div>`}
function roles(){return `<div class="role-strip">${['cashier','manager','owner'].map(r=>`<button data-role="${r}" class="${r===role?'active':''}"><b>${t(r)}</b><span>${t(r+'Desc')}</span><small>${t('preview')} →</small></button>`).join('')}</div>`}
const tableStorageKey=()=>['bep-tables',currency,branch].join(':');
function demoTables(fallback){
 try{return JSON.parse(localStorage.getItem(tableStorageKey()))||fallback}catch{return fallback}
}
function openTableIds(){
 return live?data.open_table_ids||[]:(demo?.cashier?.session?.orders||[])
  .filter(o=>o.branch_id===branch&&!o.paid).map(o=>o.table_id);
}
function tableSetup(){
 const tables=live?data.tables||[]:demoTables(data.tables||[]);
 const occupied=openTableIds();
 return `<section id="tableSetup" class="panel section-gap" tabindex="-1"><div class="branch-row"><h2>${t('tableSetup')} · ${tables.length}</h2><button id="addTable">+ ${t('addTable')}</button></div>
 ${tables.map(table=>`<div class="branch-row"><b>${esc(table.label)}</b><span>${table.seats} ${t('seats')}</span>${occupied.includes(table.id)?`<small>${t('openTableOrder')}</small>`:`<button data-remove-table="${esc(table.id)}" aria-label="${t('removeTable')} ${esc(table.label)}">−</button>`}</div>`).join('')}</section>`;
}
async function changeTables(id){
 if(busy)return;
 busy=true;
 try{
  const tables=live?data.tables||[]:demoTables(data.tables||[]);
  if(id&&openTableIds().includes(id)){toast('openTableOrder');return}
  let table;
  if(!id){
   let n=1;
   while(tables.some(tb=>tb.label==='T'+n))n++;
   table={id:'T'+n+'-'+crypto.randomUUID().slice(0,8),label:'T'+n,seats:4,x:0,y:0};
  }
  if(live){await action(id?'table_remove':'table',id?{id}:table);return}
  localStorage.setItem(tableStorageKey(),JSON.stringify(id?tables.filter(tb=>tb.id!==id):[...tables,table]));
  render();
  toast('saved');
 }catch(e){failure(e)}finally{busy=false}
}
function tableLabel(id){
 if(id==='TA')return t('takeaway');
 const tables=live?session.tables||[]:demoTables(session.tables||[]);
 return tables.find(tb=>tb.id===id)?.label||id;
}
function orderAmount(order){
 try{return money(PosMath.quote(session.catalog||[],order.items).gross_minor)}
 catch{return '—'}
}
function receiptActions(){
 return `<div class="receipt-options"><div class="copy-picker">
 <span id="printCopiesLabel">${t('printCopies')}</span>
 <div class="stepper" role="group" aria-labelledby="printCopiesLabel">
 <button type="button" data-copy-step="-1" aria-label="${t('fewerCopies')}" disabled>−</button>
 <output id="printCopies" aria-live="polite">1</output>
 <button type="button" data-copy-step="1" aria-label="${t('moreCopies')}">+</button>
 </div></div>
 <button id="print" type="button" class="primary">${t('printReceipt')}</button>
 <button id="testPrint" type="button">${t('testPrint')}</button>
 ${details('emailReceipt','receiptEmailForm',input('receiptRecipient','customerEmail','','email','required maxlength="254"'),'openEmail')}</div>`;
}
function floor(){const tables=live?session.tables||[]:demoTables(session.tables||[]);if(selected!=='TA'&&!tables.some(tb=>tb.id===selected))selected=tables[0]?.id||'TA';const selectedLabel=tables.find(tb=>tb.id===selected)?.label||t('takeaway');return `<section class="page-heading"><div><span class="eyebrow">01 / ${t('cashier')}</span><h1>${t('tables')}</h1><p>${t('chooseTable')}</p></div><button data-takeaway class="primary">+ ${t('takeaway')}</button></section><div class="pos-grid"><div class="panel floor-panel"><div class="floor-legend"><span><i></i>${t('free')}</span><span><i class="occupied"></i>${t('occupied')}</span></div><div class="floor-plan ${tables.some(tb=>tb.x===0&&tb.y===0)?'table-grid':''}" role="group" aria-label="${t('tables')}">${tables.map(tb=>{const order=(session.orders||[]).find(o=>o.table_id===tb.id&&!o.paid);return `<button class="dining-table ${order?'occupied':''} ${selected===tb.id?'selected':''}" data-table="${esc(tb.id)}" style="left:${tb.x}%;top:${tb.y}%"><span class="chair c1"></span><span class="chair c2"></span>${tb.seats>2?'<span class="chair c3"></span><span class="chair c4"></span>':''}<b>${esc(tb.label)}</b><small>${tb.seats} ${t('seats')}</small><em>${t(order?'occupied':'free')}</em>${order?`<strong class="table-due" aria-label="${t('amountDue')}: ${orderAmount(order)}">${orderAmount(order)}</strong>`:''}</button>`}).join('')}</div></div><div class="panel table-intro"><span class="eyebrow">BẾP FINANCE</span><h2>${t('selectedTable')}</h2><div class="table-name">${esc(selectedLabel)}</div><p>${t('chooseTable')}</p><button id="openMenu" class="primary">${t('menu')} →</button><div class="mini-clock"><span>${t('clock')}</span><b data-clock>${clock()}</b><small>${t('clockHint')}</small></div>${receipt?`<details class="form-panel"><summary>${t('lastReceipt')}</summary>${receiptActions()}</details>`: ''}</div></div>`}
let removedItem=null;
function pickTable(id){removedItem=null;verifiedPromotion=null;promotionDraft='';selected=id;const saved=session.orders?.find(o=>o.table_id===id&&!o.paid);basket=saved?structuredClone(saved.items):[];receipt=null;nav('menu')}
function quote(){return PosMath.quote(session.catalog||[],basket)}
function orderPanel(){const q=quote();return `<aside class="panel order-panel"><div class="order-heading"><div><span>${t('order')}</span><h2>${t(selected==='TA'?'takeaway':'table')} ${selected==='TA'?'':esc(tableLabel(selected))}</h2></div><span class="order-count">${basket.reduce((s,i)=>s+i.quantity,0)}</span></div>${basket.length?basket.map((it,i)=>{const p=session.catalog.find(p=>p.id===it.product_id);return `<div class="basket-line"><div><b>${esc(itemName(p))}</b><small>${money(p.price_minor)} · ${t('vat')} ${num(p.vat_bps/100)}%</small></div><div class="stepper"><button data-minus="${i}" aria-label="− ${esc(itemName(p))}">−</button><b>${it.quantity}</b><button data-plus="${i}" aria-label="+ ${esc(itemName(p))}">+</button></div><strong>${money(p.price_minor*it.quantity)}</strong></div>`}).join(''):`<div class="empty-basket"><span>＋</span><p>${t('empty')}</p></div>`}${removedItem?.basket===basket?`<div class="undo-item" role="status"><span>${t('removedItem')} · ${esc(itemName(removedItem.product))}</span><button id="undoRemove">${t('undoRemove')}</button></div>`:''}<div class="order-total">${row('net',q.net_minor)}${row('vat',q.tax_minor)}${row('total',q.gross_minor)}</div><p class="muted">${t('inclusive')}</p><button id="saveOrder" ${basket.length?'':'disabled'}>${t('saveOrder')}</button><button id="toPayment" class="primary" ${basket.length?'':'disabled'}>${t('checkout')} · ${money(q.gross_minor)} →</button></aside>`}
const menuGroups=['entree','plat','dessert','drink','vin','supplementaire'];
const menuGroup=p=>['main','combo'].includes(p.category)?'plat':p.category;
function orderContext(total){
 const label=selected==='TA'?t('takeaway'):t('table')+' '+tableLabel(selected);
 return `<div class="order-context"><strong>${esc(label)}</strong><span>${t('total')} <b>${money(total)}</b></span></div>`;
}
function menuView(){const items=(session.catalog||[]).filter(p=>p.active&&(category==='all'||menuGroup(p)===category));return `<section class="page-heading"><div><span class="eyebrow">02 / ${t('cashier')}</span><h1>${t('menu')}</h1><p>${t('inclusive')}</p></div><button data-nav="tables">${t('tables')}</button></section>${orderContext(quote().gross_minor)}<div class="pos-grid"><section><div class="category-tabs">${['all',...menuGroups].map(c=>`<button data-category="${c}" class="${category===c?'active':''}">${t(c)}</button>`).join('')}</div><div class="menu-grid">${items.map(p=>`<button class="menu-card" data-add="${esc(p.id)}"><img src="icons/${esc(p.icon)}.svg" alt="" width="128" height="128"><span class="menu-category">${t(menuGroup(p))}</span><h3>${esc(itemName(p))}</h3><div><b>${money(p.price_minor)}</b><span class="add-circle">+</span></div></button>`).join('')||`<p class="muted">${t('emptyCategory')}</p>`}</div></section>${orderPanel()}</div>`}
function receiptHTML(r){const groups=new Map();for(const l of r.sale_lines||[]){const a=groups.get(l.vat_bps||0)||{net:0,tax:0};a.net+=l.net_minor??0;a.tax+=l.tax_minor??0;groups.set(l.vat_bps||0,a)}return `<div class="receipt"><h2>${esc(r.receipt_profile?.merchant_name||session.receipt_profile?.merchant_name||'BẾP FINANCE')}</h2><p>${esc(r.receipt_profile?.address||session.receipt_profile?.address||'')}<br>${t('vatNumber')}: ${esc(r.receipt_profile?.vat_number||session.receipt_profile?.vat_number||'—')}</p><p>${t(live?'receipt':'sampleReceipt')}</p><p>${esc(r.branch_id||branch)} · ${esc(tableLabel(r.table_id||selected))}<br>${esc(r.date||localDay())}<br>${esc(r.document_id||'DEMO')}${r.payment_method?`<br>${t('method')}: ${esc(t(r.payment_method))}`:''}</p><table><thead><tr><th>${t('item')}</th><th>${t('quantity')}</th><th>${t('unitPrice')}</th><th>${t('total')}</th></tr></thead><tbody>${(r.sale_lines||[]).map(l=>`<tr><td>${esc(itemName(l))}</td><td>${l.quantity}</td><td>${money(l.unit_price_minor)}</td><td>${money(l.gross_minor??l.subtotal_minor)}</td></tr>`).join('')}</tbody></table>${row('subtotal',r.subtotal_minor)}${row('discount',r.discount_minor)}${row('net',r.net_minor)}${row('vat',r.tax_minor)}<div class="receipt-total">${row('total',r.gross_minor)}</div><table><thead><tr><th>${t('vat')}</th><th>${t('net')}</th><th>${t('vat')}</th></tr></thead><tbody>${[...groups].map(([rate,v])=>`<tr><td>${num(rate/100)}%</td><td>${money(v.net)}</td><td>${money(v.tax)}</td></tr>`).join('')}</tbody></table><p class="receipt-note">${t('receiptLimit')}</p></div>`}
function payView(){const valid=verifiedPromotion&&verifiedPromotion.key===promotionDraft&&verifiedPromotion.items===JSON.stringify(basket),q=valid?verifiedPromotion.quote:quote();return `<section class="page-heading"><div><span class="eyebrow">03 / ${t('cashier')}</span><h1>${t('payment')}</h1><p>${t('inclusive')}</p></div></section>${orderContext(q.gross_minor)}<div class="two"><section class="panel">${receiptHTML(receipt||q)}${receipt?receiptActions():''}</section><section class="panel"><h2>${t('payment')}</h2>${!session.active_shift?.opening_confirmed?`<div class="notice">${t('opening')}</div>${details('opening','openingForm',input('openingCash','counted','0','number','min="0" step="0.01" required'),'opening')}`:''}<form id="payForm">${select('method','payment',[['cash',t('cash')],['bank',t('bank')],['ticket_restaurant','Ticket Restaurant']],'cash')}${input('promotionKey','promotionKey',promotionDraft,'password','autocomplete="off"')}<button type="button" id="verifyKey" ${live?'':'disabled'}>${t('verifyKey')}</button><p class="muted">${t('promotionPreview')}</p><button class="primary" ${basket.length&&session.active_shift?.opening_confirmed&&(!promotionDraft||valid)?'':'disabled'}>${t('reviewPayment')} · ${money(q.gross_minor)}</button></form><button data-nav="menu">${t('editOrder')}</button><p class="muted">${t('promotionHint')}</p></section></div>`}
function handoverView(){return `<section class="page-heading"><div><h1>${t('handover')}</h1><p>${t('clockHint')}</p></div></section><div class="two"><section class="panel"><h2>${t('clock')}</h2><div class="large-clock" data-clock>${clock()}</div>${!session.active_shift?`<p>${t('noShift')}</p>`:details('endShift','endForm',input('endCash','counted','0','number','min="0" step="0.01" required')+input('breaks','breaks','0','number','min="0" step="1" required')+select('recipient','recipient',[['',t('none')],...(session.handover_recipients||[]).map(e=>[e.employee_id,e.name])],'')+input('note','note'),'endShift')}<button id="printHandover">${t('printHandover')}</button></section><section class="panel"><h2>${t('hours')}</h2>${(summary?.shifts||[]).map(s=>`<article class="shift-card"><b>${esc(s.employee_name)}</b><p>${dateLabel(s.started_at)} → ${s.ended_at?dateLabel(s.ended_at):'…'}</p><strong>${num((s.paid_seconds||0)/3600)} ${t('hours')}</strong>${row('expected',s.expected_cash_minor)}${s.ended_at?row('difference',s.cash_difference_minor):''}${(s.sales||[]).filter(x=>x.kind==='sale').map(x=>`<div class="branch-row"><span>${esc(x.document_id.slice(0,8))}</span><b>${money(x.gross_minor)}</b><button data-receipt="${esc(x.document_id)}">${t('print')}</button></div>`).join('')}</article>`).join('')}</section></div>`}
function bars(items,percent=false){const total=percent?items.reduce((a,x)=>a+Math.max(0,x[1]),0):Math.max(1,...items.map(x=>Math.abs(x[1])));return items.map(([label,v])=>`<div class="chart-line"><div><span>${label}</span><b>${percent?num(total?v/total*100:0)+'%':money(v)}</b></div><div class="bar"><i style="width:${total?Math.min(100,Math.abs(v)/total*100):0}%;background:${v<0?'#b46b51':'#769b72'}"></i></div></div>`).join('')}
function pnlView(d){const p=d.financial.pnl;return `<div class="metrics">${metric('dailyRevenue',money(d.daily.pnl.revenue_minor))}${metric('dailyProfit',money(d.estimated_daily_profit_after_hours_minor),'dailyHint')}${metric('payroll',money(d.payroll.gross_minor))}${metric('profit',money(p.profit_before_interest_tax_minor))}</div><div class="two"><section class="panel"><h2>${t('costs')}</h2>${bars([[t('food'),p.food_minor],[t('labor'),p.labor_minor],[t('rent'),p.rent_minor],[t('other'),p.other_minor],[t('depreciation'),p.depreciation_minor]],true)}${details('expense','expenseForm',select('expenseCategory','costs',[['rent',t('rent')],['other',t('other')]],'rent')+input('expenseNet','net','','number','min="0.01" step="0.01" required')+input('expenseTax','vat','0','number','min="0" step="0.01" required')+input('expenseDate','date',localDay(),'date','required'),'expense',live)}</section><section class="panel"><h2>${t('overview')}</h2>${bars([[t('revenue'),p.revenue_minor],[t('costs'),p.food_minor+p.labor_minor+p.rent_minor+p.other_minor+p.depreciation_minor],[t('profit'),p.profit_before_interest_tax_minor]])}</section></div>`}
function ratioChart(items,total){
 return items.map(([label,value])=>{
  const ratio=total>0?value/total:null;
  const percentage=ratio===null?'—':new Intl.NumberFormat(I18n.locale,{style:'percent',maximumFractionDigits:1}).format(ratio);
  const width=ratio===null?0:Math.min(100,Math.abs(ratio)*100);
  return `<div class="chart-line"><div><span>${esc(label)}</span><b>${money(value)} · ${percentage}</b></div><div class="bar" aria-hidden="true"><i style="width:${width}%;background:${value<0?'#b46b51':'#769b72'}"></i></div></div>`;
 }).join('');
}
function ownerCostShare(pnls){
 const costs=[['food','food_minor'],['labor','labor_minor'],['rent','rent_minor'],['other','other_minor'],['depreciation','depreciation_minor']]
  .map(([label,key])=>[t(label),pnls.reduce((sum,p)=>sum+p[key],0)]);
 const revenue=pnls.reduce((sum,p)=>sum+p.revenue_minor,0);
 const example=revenue>0?t('foodPerHundred').replace('{revenue}',money(10000)).replace('{cost}',money(Math.round(costs[0][1]*10000/revenue))):'';
 return `<section class="panel"><h2>${t('costShare')}</h2><p class="muted">${t('costShareHint')}</p>${example?`<p class="cost-example">${esc(example)}</p>`:''}${ratioChart(costs,costs.reduce((sum,[,value])=>sum+value,0))}</section>`;
}
function ownerMargin(pnls){
 const revenue=pnls.reduce((sum,p)=>sum+p.revenue_minor,0);
 const profit=pnls.reduce((sum,p)=>sum+p.profit_before_interest_tax_minor,0);
 return `<section class="panel"><h2>${t('profitMargin')}</h2><p class="muted">${t('profitMarginHint')}</p>${ratioChart([[t('profit'),profit]],revenue)}</section>`;
}
function ownerView(){const pnls=data.branches.map(b=>b.financial.pnl);return `<section class="panel"><h2>${t('tableSetup')}</h2>${data.branches.map(b=>`<button data-open-branch="${esc(b.branch_id)}" data-floor-plan>${t('tableSetup')} · ${esc(b.branch_id)} →</button>`).join(' ')}</section><div class="metrics section-gap">${metric('revenue',money(data.revenue_minor))}${metric('profit',money(data.before_tax_minor))}${metric('estimatedTax',money(data.estimated_tax_minor))}${metric('afterTax',money(data.estimated_after_tax_minor))}</div><p class="notice">${t('taxHint')}</p><div class="two"><section class="panel"><h2>${t('revenueShare')}</h2><p class="muted">${t('revenueShareHint')}</p>${ratioChart(data.branches.map(b=>[b.branch_id,b.financial.pnl.revenue_minor]),data.revenue_minor)}</section>${ownerCostShare(pnls)}${ownerMargin(pnls)}<section class="panel"><h2>${t('profit')}</h2>${bars(data.branches.map(b=>[esc(b.branch_id),b.financial.pnl.profit_before_interest_tax_minor]))}</section><section class="panel"><h2>${t('branch')}</h2>${data.branches.map(b=>`<div class="branch-row"><b>${esc(b.branch_id)}</b><span>${money(b.financial.pnl.revenue_minor)}</span><button data-open-branch="${esc(b.branch_id)}">${t('openBranch')} →</button></div>`).join('')}</section></div>`}
function stockView(){return `<section class="panel"><h2>${t('stock')}</h2><div class="table-scroll"><table><thead><tr>${['ingredient','remaining','buyDay','buyWeek'].map(k=>`<th>${t(k)}</th>`).join('')}</tr></thead><tbody>${data.shopping.map(x=>`<tr><td>${esc(ingredientName(x.item_id,x.name))}</td><td>${num(x.current_quantity)}</td><td>${num(x.today_buy)}</td><td>${num(x.week_buy)}</td></tr>`).join('')}</tbody></table></div>${details('purchase','purchaseForm',select('purchaseItem','ingredient',data.daily.stock.map(x=>[x.item_id,ingredientName(x.item_id,x.name)]))+input('purchaseQty','quantity','1000','number','min="1" step="1" required')+input('purchaseNet','purchasePrice','','number','min="0.01" step="0.01" required')+input('purchaseTax','vat','0','number','min="0" step="0.01" required')+input('purchaseDate','date',localDay(),'date','required'),'purchase',live)}<h3>${t('prices')}</h3>${data.purchases.slice(-5).map(x=>`<div class="money-row"><span>${esc(x.item_id)} · ${esc(x.date)}</span><b>${money(x.price_per_kg_minor)}</b></div>`).join('')}</section>`}
function staffView(){return `<div class="two"><section class="panel"><h2>${t('payroll')}</h2><p class="muted">${t('payrollHint')}</p>${bars(data.payroll.employees.map(e=>[esc(e.name),e.gross_minor]))}<table><thead><tr>${['employee','hours','payroll'].map(k=>`<th>${t(k)}</th>`).join('')}</tr></thead><tbody>${data.payroll.employees.map(e=>`<tr><td>${esc(e.name)}</td><td>${num(e.paid_seconds/3600)}</td><td>${money(e.gross_minor)}</td></tr>`).join('')}</tbody></table>${details('accrue','payrollForm',input('payDate','date',month+'-01','date','required'),'accrue',live)}${data.employees.map(e=>`<div class="money-row"><span>${esc(e.name)} · ${esc(e.employee_id)}</span><b>${money(e.hourly_minor)} / ${t('hours')}</b></div>`).join('')}${details('employee','employeeForm',input('employeeId','employeeId','','text','required')+input('employeeName','name','','text','required')+input('hourly','hourly','15','number','min="0.01" step="0.01" required')+input('inactive','inactive','','date'),'save',live)}</section><section class="panel"><h2>${t('hours')}</h2>${data.shifts.filter(s=>s.ended_at).map(s=>`<article class="shift-card"><b>${esc(s.employee_name)}</b><p>${dateLabel(s.started_at)} → ${dateLabel(s.ended_at)}</p><div class="money-row"><span>${num(s.paid_seconds/3600)} ${t('hours')}</span><b>${t(s.reviewed?'approved':'pending')}</b></div>${row('difference',s.cash_difference_minor)}${!s.reviewed?`<button data-review="${esc(s.shift_id)}" ${live?'':'disabled'}>${t('review')}</button>`:''}</article>`).join('')}</section></div>`}
function settingsView(){if(role==='owner'&&view!=='branchSettings')return `<section class="panel"><h2>${t('taxScenario')}</h2><p class="muted">${t('taxHint')}</p>${details('taxScenario','taxForm',select('taxBranch','branch',data.branches.map(b=>[b.branch_id,b.branch_id]))+input('taxRate','taxScenario','20','number','min="0" max="100" step="0.01" required'),'save',live)}<h3>${t('menuSettings')}</h3>${data.branches.map(b=>`<button data-open-branch="${esc(b.branch_id)}">${esc(b.branch_id)} → ${t('settings')}</button>`).join('')}</section>`;
const p=data.catalog.find(p=>p.id===editId);return `<section class="panel"><h2>${t('menuSettings')}</h2><p class="muted">${t('menuHint')}</p><div class="table-scroll"><table><thead><tr>${['item','unitPrice','vat','edit'].map(k=>`<th>${t(k)}</th>`).join('')}</tr></thead><tbody>${data.catalog.map(p=>`<tr><td><span class="item-cell"><img src="icons/${esc(p.icon)}.svg" alt="" width="42" height="42">${esc(itemName(p))}</span></td><td>${money(p.price_minor)}</td><td>${num(p.vat_bps/100)}%</td><td><button data-edit="${esc(p.id)}">${t('edit')}</button></td></tr>`).join('')}</tbody></table></div>${p?`<form id="menuForm" class="edit-menu"><h3>${t('translatedNames')} · ${esc(p.id)}</h3><div class="form-grid">${[['vi','Tiếng Việt'],['en','English'],['fr','Français'],['de','Deutsch']].map(([code,name])=>`<label>${name}<input id="name-${code}" value="${esc(p.names[code])}" required maxlength="120"></label>`).join('')}${input('menuPrice','unitPrice',String(p.price_minor/100),'number','min="0.01" step="0.01" required')}${input('menuVat','vatRate',String(p.vat_bps/100),'number','min="0" max="100" step="0.01" required')}${select('menuGroup','menuGroup',menuGroups.map(g=>[g,t(g)]),menuGroup(p))}${select('menuActive','active',[['true',t('active')],['false',t('inactiveItem')]],String(p.active))}</div><button class="primary">${t('save')}</button></form>`:''}${details('business','businessForm',input('merchantName','name',data.receipt_profile?.merchant_name||'','text','required')+input('merchantAddress','address',data.receipt_profile?.address||'','text','required')+input('merchantVat','vatNumber',data.receipt_profile?.vat_number||''),'save',live)}${details('timezone','timezoneForm',input('timezone','timezone',data.timezone,'text','required'),'save',live)}</section>`}
function accountsView(){return `<section class="panel"><h2>${t('accounts')}</h2><p>${t('accountHint')}</p>${!live?`<div class="notice">${t('backendRequired')}</div>`:''}${details('changePassword','passwordForm',input('oldPassword','currentPassword','','password','required autocomplete="current-password"')+input('newPassword','newPassword','','password','required minlength="12" maxlength="128" autocomplete="new-password"'),'changePassword',live)}${details('createAccount','accountForm',input('accountEmail','email','','email','required')+input('accountPassword','newPassword','','password','required minlength="12" maxlength="128" autocomplete="new-password"')+input('accountName','name','','text','required')+select('accountRole','role',(role==='owner'?['cashier','manager','owner']:['cashier']).map(r=>[r,t(r)]),'cashier')+input('accountEmployee','employeeId')+input('accountBranch','branch',branch,'text','required'),'createAccount',live)}</section>`}
function promotionView(){return `<section class="panel"><h2>${t('promotion')}</h2>${data.campaigns.map(c=>`<div class="money-row"><span>${esc(c.name)}</span><b>${num(c.discount_bps/100)}%</b></div>`).join('')}${details('campaign','campaignForm',input('campaignId','campaign','','text','required')+input('campaignName','name','','text','required')+input('discountRate','discountRate','10','number','min="0.01" max="100" step="0.01" required')+input('starts','starts','','datetime-local','required')+input('ends','ends','','datetime-local','required'),'save',live)}${details('grant','grantForm',select('grantCampaign','campaign',data.campaigns.map(c=>[c.campaign_id,c.name]))+select('grantEmployee','employee',data.employees.map(e=>[e.employee_id,e.name])),'grant',live)}${secretKey?`<output class="secret">${esc(secretKey)}</output>`:''}</section>`}
function forecastView(){return `<section class="panel"><h2>${t('forecast')}</h2><p>${t('forecastHint')}</p><button id="forecastButton" class="primary" ${live?'':'disabled'}>${t('check')}</button><div id="forecastResult"></div></section>`}
function receiptStep(){
 return `<section class="page-heading"><div><h1>${t('receiptStep')}</h1><p>${t('paid')}</p></div></section>
 <div class="two receipt-step"><section class="panel receipt-preview">${receiptHTML(receipt)}</section><section class="panel receipt-controls">
 <p>${t('receiptStepHint')}</p>${receiptActions()}
 <button id="receiptDone" class="primary">${t('receiptDone')}</button>
 </section></div>`;
}
function content(){if(role==='cashier')return view==='tables'?floor():view==='menu'?menuView():view==='payment'?payView():view==='receipt'?receiptStep():handoverView();if(view==='handover')return handoverView();if(view==='accounts')return accountsView();if(view==='forecast')return forecastView();if(view==='settings'||view==='branchSettings')return settingsView();if(view==='promotion')return promotionView();if(view==='stock')return stockView();if(view==='staff')return staffView();if(role==='owner'&&view!=='branch')return ownerView();return pnlView(data)+(view==='branch'?tableSetup():'')+(role==='owner'&&view==='branch'?`<div class="two section-gap">${ownerCostShare([data.financial.pnl])}${ownerMargin([data.financial.pnl])}</div>`:'')+(view==='branch'?`<section class="panel section-gap"><h2>${t('menuSettings')}</h2>${data.catalog.map(p=>`<div class="money-row"><span>${esc(itemName(p))}</span><b>${money(p.price_minor)}</b><button data-owner-edit="${esc(p.id)}">${t('edit')}</button></div>`).join('')}</section>`:'')}
function render(){if(!session)return;$('#app').innerHTML=header()+`<div class="app-shell">${sidebar()}<main>${!live?roles():''}${toolbar()}${!live?`<div class="login-bar"><span>${t(role+'Desc')}</span><button id="loginButton" class="primary">${t('login')} · ${t(role)}</button></div>`:''}${errorDetail?`<div class="error"><p>${t('error')}</p><details><summary>${t('technical')}</summary><pre>${esc(errorDetail)}</pre></details></div>`:''}${role!=='cashier'?`<section class="page-heading"><div><span class="eyebrow">BẾP FINANCE / ${t(roleKey(role))}</span><h1>${t(view==='branch'?'overview':view==='branchSettings'?'settings':view)}</h1></div></section>`:''}${content()}<footer>© Bếp Finance · ${t('receiptLimit')}</footer></main></div>`;bind()}
async function action(kind,payload){const r=await api('workspace/actions',{branch_id:branch,kind,payload});await load(false);toast('saved');return r}
async function saveOrder(){if(selected==='TA')return null;const existing=session.orders?.find(o=>o.table_id===selected&&!o.paid),payload={table_id:selected,items:structuredClone(basket),revision:existing?.revision||0};if(!live){const order={...payload,order_id:existing?.order_id||crypto.randomUUID(),branch_id:branch,revision:payload.revision+1,paid:false};session.orders=(session.orders||[]).filter(o=>o.table_id!==selected||o.paid);session.orders.push(order);return order}
 const r=await api('workspace/actions',{branch_id:branch,kind:'order_save',payload});session=await api('workspace/session?branch='+branch);return r}
function finishCheckout(){
 removedItem=null;
 basket=[];pendingCheckout=null;verifiedPromotion=null;promotionDraft='';
 view='receipt';trail=[];window.scrollTo({top:0,behavior:'instant'});
}
function hook(id,fn){const f=$('#'+id);if(f)f.onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;const button=f.querySelector('button.primary')||f.querySelector('button');button.disabled=true;try{await fn()}catch(e){failure(e)}finally{busy=false;if(button.isConnected)button.disabled=false}}}
function bind(){
 if($('#addTable'))$('#addTable').onclick=()=>changeTables();
 document.querySelectorAll('[data-remove-table]').forEach(b=>b.onclick=()=>changeTables(b.dataset.removeTable));
 $('#backButton').onclick=back;$('#language').onchange=e=>I18n.setLanguage(e.target.value);$('#currency').onchange=async e=>{currency=e.target.value;verifiedPromotion=null;promotionDraft='';try{localStorage.setItem('bep-currency',currency)}catch{}basket=[];receipt=null;selected='T1';view=role==='cashier'?'tables':'overview';try{await fetchDemo();await load(false)}catch(e){failure(e)}};
 if($('#logout'))$('#logout').onclick=logout;
 if($('#loginButton'))$('#loginButton').onclick=()=>authDialog('login');
 document.querySelectorAll('[data-role]').forEach(b=>b.onclick=()=>{role=b.dataset.role;view=role==='cashier'?'tables':'overview';trail=[];verifiedPromotion=null;promotionDraft='';basket=[];receipt=null;branch='q1';load(false).catch(failure)});
 document.querySelectorAll('[data-nav]').forEach(b=>b.onclick=()=>nav(b.dataset.nav));
 if($('#branch'))$('#branch').onchange=async e=>{branch=e.target.value;await load(role!=='owner').catch(failure)};
 if($('#month'))$('#month').onchange=async e=>{month=e.target.value;await load(false).catch(failure)};
 $('#refresh').onclick=()=>load(false).catch(failure);
 document.querySelectorAll('[data-table]').forEach(b=>b.onclick=()=>pickTable(b.dataset.table));if($('#openMenu'))$('#openMenu').onclick=()=>pickTable(selected);
 document.querySelectorAll('[data-takeaway]').forEach(b=>b.onclick=()=>pickTable('TA'));
 document.querySelectorAll('[data-category]').forEach(b=>b.onclick=()=>{category=b.dataset.category;render()});
 document.querySelectorAll('[data-add]').forEach(b=>b.onclick=()=>{const p=basket.find(p=>p.product_id===b.dataset.add);if(p)p.quantity=Math.min(10000,p.quantity+1);else basket.push({product_id:b.dataset.add,quantity:1});receipt=null;render()});
 document.querySelectorAll('[data-minus]').forEach(b=>b.onclick=()=>{const index=Number(b.dataset.minus),item=basket[index];item.quantity--;if(item.quantity===0){basket.splice(index,1);removedItem={basket,index,item:{...item,quantity:1},product:session.catalog.find(p=>p.id===item.product_id)}}render()});document.querySelectorAll('[data-plus]').forEach(b=>b.onclick=()=>{basket[+b.dataset.plus].quantity=Math.min(10000,basket[+b.dataset.plus].quantity+1);render()});
 if($('#undoRemove'))$('#undoRemove').onclick=()=>{
  const {index,item}=removedItem;
  const existing=basket.find(line=>line.product_id===item.product_id);
  if(existing)existing.quantity=Math.min(10000,existing.quantity+1);
  else basket.splice(index,0,item);
  removedItem=null;
  render();
 };
 if($('#saveOrder'))$('#saveOrder').onclick=async()=>{try{await saveOrder();toast('saved')}catch(e){failure(e);toast('retryOrder')}};
 if($('#toPayment'))$('#toPayment').onclick=async()=>{try{await saveOrder();nav('payment')}catch(e){failure(e);toast('retryOrder')}};
 if($('#testPrint'))$('#testPrint').onclick=()=>testPrint(receipt);
 document.querySelectorAll('[data-copy-step]').forEach(button=>button.onclick=()=>{
  const output=$('#printCopies');
  const copies=Math.max(1,Math.min(10,Number(output.textContent)+Number(button.dataset.copyStep)));
  output.textContent=copies;
  $('[data-copy-step="-1"]').disabled=copies===1;
  $('[data-copy-step="1"]').disabled=copies===10;
 });
 if($('#print'))$('#print').onclick=()=>print(receiptHTML(receipt),Number($('#printCopies').textContent));
 if($('#receiptDone'))$('#receiptDone').onclick=()=>{view='tables';render();window.scrollTo({top:0,behavior:'instant'})};
 if($('#receiptEmailForm'))$('#receiptEmailForm').onsubmit=e=>{
  e.preventDefault();
  const email=$('#receiptRecipient').value.trim();
  const template=document.createElement('template');
  template.innerHTML=receiptHTML(receipt);
  template.content.querySelectorAll('br').forEach(br=>br.replaceWith('\n'));
  const body=[...template.content.querySelector('.receipt').children].map(section=>{
   if(section.matches('table'))return [...section.rows].map(row=>[...row.cells].map(cell=>cell.textContent).join(' | ')).join('\n');
   if(section.matches('.money-row, .receipt-total'))return [...section.querySelectorAll('span, b')].map(part=>part.textContent).join(': ');
   return section.textContent;
  }).join('\n\n');
  const subject=t('receipt')+' '+receipt.document_id;
  const recipient=encodeURIComponent(email).replace(/%40/g,'@');
  location.href='mailto:'+recipient+'?subject='+encodeURIComponent(subject)+'&body='+encodeURIComponent(body);
 };
 document.querySelectorAll('[data-receipt]').forEach(b=>b.onclick=async()=>{try{const r=live?await api('workspace/receipt/'+b.dataset.receipt):demo.cashier.receipt;print(receiptHTML(r))}catch(e){failure(e)}});
 if($('#printHandover'))$('#printHandover').onclick=()=>print(`<h2>${t('handover')}</h2>`+(summary?.shifts||[]).map(s=>`<h3>${esc(s.employee_name)}</h3><p>${dateLabel(s.started_at)} → ${s.ended_at?dateLabel(s.ended_at):'…'}</p>${row('expected',s.expected_cash_minor)}${s.ended_at?row('counted',s.counted_cash_minor)+row('difference',s.cash_difference_minor):''}`).join(''));
 hook('openingForm',async()=>{const value=amount('openingCash');if(!live){session.active_shift.opening_cash_minor=value;session.active_shift.opening_confirmed=true;render();return}await action('till_open',{shift_id:session.active_shift.shift_id,opening_cash_minor:value})});
 if($('#promotionKey'))$('#promotionKey').oninput=()=>{const key=$('#promotionKey').value;promotionDraft=key;const verified=verifiedPromotion&&verifiedPromotion.key===key&&verifiedPromotion.items===JSON.stringify(basket);$('#payForm button.primary').disabled=!basket.length||!session.active_shift?.opening_confirmed||Boolean(key&&!verified)};
 if($('#verifyKey'))$('#verifyKey').onclick=async()=>{try{const key=$('#promotionKey').value;const q=await api('workspace/quote',{branch_id:branch,items:structuredClone(basket),activation_key:key||null});verifiedPromotion={key,items:JSON.stringify(basket),quote:q};render()}catch(e){failure(e)}};
 hook('payForm',async()=>{
  const key=$('#promotionKey').value;if(key&&(!verifiedPromotion||verifiedPromotion.key!==key||verifiedPromotion.items!==JSON.stringify(basket)))throw Error('Verify the key and total before payment');const q=key?verifiedPromotion.quote:quote(),method=$('#method').value;
  if(!await reviewPayment(q.gross_minor,method))return;
  if(!live){if(key)throw Error('Promotion keys require backend verification');receipt={...q,payment_method:method,date:localDay(),branch_id:branch,table_id:selected,document_id:'DEMO-'+crypto.randomUUID().slice(0,8),receipt_profile:structuredClone(session.receipt_profile||{})};const o=session.orders?.find(o=>o.table_id===selected&&!o.paid);if(o)o.paid=true;finishCheckout();render();toast('paid');return}
  const order=selected==='TA'?null:session.orders?.find(o=>o.table_id===selected&&!o.paid),body={document:{kind:'sale',branch_id:branch,date:localDay(),items:structuredClone(basket),payment:method,tax_minor:0},activation_key:key||null,order_id:order?.order_id||null,order_revision:order?.revision||null,expected_gross_minor:q.gross_minor};
  const serialized=JSON.stringify(body);if(!pendingCheckout||pendingCheckout.serialized!==serialized)pendingCheckout={serialized,key:crypto.randomUUID()};const result=await api('workspace/checkout',body,pendingCheckout.key);receipt=await api('workspace/receipt/'+result.document_id);finishCheckout();await load(false);toast('paid');
 });
 hook('endForm',async()=>{const p={shift_id:session.active_shift.shift_id,counted_cash_minor:amount('endCash'),break_seconds:Number($('#breaks').value)*60,handover_to:$('#recipient').value||null,note:$('#note').value};if(!live){const s=session.active_shift;s.ended_at=session.server_now;s.paid_seconds=Math.max(0,Math.floor((new Date(s.ended_at)-new Date(s.started_at))/1000)-p.break_seconds);s.counted_cash_minor=p.counted_cash_minor;s.cash_difference_minor=p.counted_cash_minor-(summary.shifts.find(x=>x.shift_id===s.shift_id)?.expected_cash_minor||0);session.active_shift=null;render();return}await action('shift_close',p)});
 document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>{editId=b.dataset.edit;render();$('#menuForm')?.scrollIntoView({behavior:'smooth',block:'center'})});
 hook('menuForm',async()=>{const p=structuredClone(data.catalog.find(p=>p.id===editId));p.names=Object.fromEntries(['vi','en','fr','de'].map(code=>[code,$('#name-'+code).value]));p.name=p.names.en;p.price_minor=amount('menuPrice');p.vat_bps=Math.round(Number($('#menuVat').value)*100);p.category=$('#menuGroup').value;p.active=$('#menuActive').value==='true';delete p.branch_id;if(live){await action('menu',p)}else{Object.assign(data.catalog.find(x=>x.id===p.id),p);Object.assign(demo.cashier.session.catalog.find(x=>x.id===p.id)||{},p);render();toast('saved')}});
 hook('businessForm',()=>action('receipt_profile',{merchant_name:$('#merchantName').value,address:$('#merchantAddress').value,vat_number:$('#merchantVat').value}));
 hook('timezoneForm',()=>action('settings',{timezone:$('#timezone').value}));
 hook('employeeForm',()=>action('employee',{employee_id:$('#employeeId').value,name:$('#employeeName').value,hourly_minor:amount('hourly'),inactive_from:$('#inactive').value||null}));
 hook('payrollForm',async()=>{await api('workspace/payroll/accrue',{branch_id:branch,month,date:$('#payDate').value});await load(false)});
 hook('purchaseForm',async()=>{await api('erp/documents',{kind:'purchase',branch_id:branch,date:$('#purchaseDate').value,item_id:$('#purchaseItem').value,quantity:Number($('#purchaseQty').value),net_minor:amount('purchaseNet'),tax_minor:amount('purchaseTax'),payment:'credit'});await load(false)});
 hook('expenseForm',async()=>{await api('erp/documents',{kind:'expense',branch_id:branch,date:$('#expenseDate').value,category:$('#expenseCategory').value,net_minor:amount('expenseNet'),tax_minor:amount('expenseTax'),payment:'bank'});await load(false)});
 hook('accountForm',async()=>{await api('auth/accounts',{email:$('#accountEmail').value,password:$('#accountPassword').value,name:$('#accountName').value,role:$('#accountRole').value,branches:[$('#accountBranch').value],...($('#accountEmployee').value?{employee_id:$('#accountEmployee').value}:{})});$('#accountPassword').value='';toast('saved')});
 hook('passwordForm',async()=>{await api('auth/password',{current_password:$('#oldPassword').value,new_password:$('#newPassword').value});await logout();toast('passwordChanged')});
 hook('campaignForm',()=>action('campaign',{campaign_id:$('#campaignId').value,name:$('#campaignName').value,discount_bps:Math.round(Number($('#discountRate').value)*100),enabled:true,starts_at:$('#starts').value+':00Z',ends_at:$('#ends').value+':00Z'}));
 hook('grantForm',async()=>{const r=await api('workspace/actions',{branch_id:branch,kind:'grant',payload:{campaign_id:$('#grantCampaign').value,employee_id:$('#grantEmployee').value}});secretKey=r.activation_key;render()});
 hook('taxForm',async()=>{await api('workspace/actions',{branch_id:$('#taxBranch').value,kind:'tax',payload:{rate_bps:Math.round(Number($('#taxRate').value)*100)}});await load(false)});
 document.querySelectorAll('[data-review]').forEach(b=>b.onclick=async()=>{const reason=prompt(t('reason'));if(reason)try{await action('shift_review',{shift_id:b.dataset.review,reason})}catch(e){failure(e)}});
 document.querySelectorAll('[data-open-branch]').forEach(b=>b.onclick=async()=>{try{branch=b.dataset.openBranch;trail.push(view);view='branch';data=live?await api('workspace/management?branch='+branch+'&month='+month):demo.owner.branches.find(x=>x.branch_id===branch);render();if(b.hasAttribute('data-floor-plan')){const panel=$('#tableSetup');panel.focus({preventScroll:true});panel.scrollIntoView({block:'start'})}}catch(e){failure(e)}});
 document.querySelectorAll('[data-owner-edit]').forEach(b=>b.onclick=()=>{editId=b.dataset.ownerEdit;trail.push(view);view='branchSettings';render();});
 if($('#forecastButton'))$('#forecastButton').onclick=async()=>{try{const r=await api('erp/forecast?branch='+branch+'&horizon=3');$('#forecastResult').innerHTML=(r.forecast||[]).map(f=>`<h3>${esc(f.month)}</h3>${bars([[t('revenue'),f.revenue_minor],[t('profit'),f.profit_before_interest_tax_minor]])}`).join('')}catch(e){$('#forecastResult').innerHTML='<p>'+t('forecastHint')+'</p><details><summary>'+t('technical')+'</summary><pre>'+esc(e.message)+'</pre></details>'}};
}
function reviewPayment(total,method){
 const dialog=document.createElement('dialog');
 dialog.className='payment-review';
 const table=selected==='TA'?t('takeaway'):t('table')+' '+tableLabel(selected);
 dialog.innerHTML=`<form method="dialog">
 <h2>${t('reviewPayment')}</h2>
 <div class="money-row"><span>${esc(table)}</span><b>${money(total)}</b></div>
 <p>${t('method')} · <strong>${esc(t(method))}</strong></p>
 <div class="payment-review-actions"><button value="cancel" autofocus>${t('reviewOrder')}</button>
 <button value="confirm" class="primary">${t('confirmPayment')}</button></div>
 </form>`;
 document.body.append(dialog);
 return new Promise(resolve=>{
  dialog.addEventListener('close',()=>{
   const confirmed=dialog.returnValue==='confirm';
   dialog.remove();
   resolve(confirmed);
  },{once:true});
  dialog.showModal();
 });
}
function testPrint(receipt){
 const html=receiptHTML(receipt);
 const dialog=document.createElement('dialog');
 dialog.innerHTML=`<div class="dialog-heading"><h2>${t('testPrint')}</h2><button type="button" aria-label="${t('closePreview')}">✕</button></div><p class="muted">${t('testPrintHint')}</p>${html}<button class="primary" data-confirm-print>${t('print')}</button>`;
 dialog.querySelector('button').onclick=()=>dialog.close();
 dialog.querySelector('[data-confirm-print]').onclick=()=>{dialog.close();print(html,Number($('#printCopies')?.textContent||1))};
 dialog.addEventListener('close',()=>dialog.remove(),{once:true});
 document.body.append(dialog);
 dialog.showModal();
}
window.addEventListener('storage',event=>{
 if(!live&&session&&event.key===tableStorageKey()&&['tables','branch'].includes(view))render();
});
function print(html,copies=1){
 $('#printReceipt').innerHTML=Array.from({length:copies},()=>`<div class="receipt-copy">${html}</div>`).join('');
 window.print();
}
async function logout(){if(live){try{await api('auth/logout',{})}catch(e){failure(e);return}}live=false;accountIdentity=null;secretKey=null;verifiedPromotion=null;promotionDraft='';receipt=null;basket=[];view=role==='cashier'?'tables':'overview';await fetchDemo();await load(false)}
function authDialog(mode='login'){
 const dialog=$('#authDialog');dialog.innerHTML=`<div class="dialog-heading"><h2>${t(mode==='forgot'?'reset':mode==='reset'?'newPassword':'login')}${mode==='login'?' · '+t(role):''}</h2><button id="closeAuth" class="quiet">✕</button></div>${!ready?`<p class="notice">${t('backendRequired')}</p>`:''}<form id="authForm">${mode==='reset'?'':input('authEmail','email','','email','required autocomplete="username"')}${mode==='forgot'?'':input('authPassword',mode==='reset'?'newPassword':'password','','password',`required ${mode==='reset'?'minlength="12" maxlength="128" autocomplete="new-password"':'autocomplete="current-password"'}`)}<button class="primary" ${ready?'':'disabled'}>${t(mode==='forgot'?'send':mode==='reset'?'save':'login')}</button></form>${mode==='login'?`<button id="forgot" class="text-button">${t('forgot')}</button>`:''}<p id="authMessage" role="status"></p>`;
 $('#closeAuth').onclick=()=>dialog.close();if($('#forgot'))$('#forgot').onclick=()=>authDialog('forgot');if(!dialog.open)dialog.showModal();
 $('#authForm').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;try{if(mode==='forgot'){await api('auth/forgot',{email:$('#authEmail').value});$('#authMessage').textContent=t('resetSent')}else if(mode==='reset'){await api('auth/reset',{token:recoveryToken,password:$('#authPassword').value});recoveryToken=null;$('#authPassword').value='';$('#authMessage').textContent=t('passwordChanged')}else{const r=await api('auth/login',{email:$('#authEmail').value,password:$('#authPassword').value,role});accountIdentity=r.identity;branch=r.identity.branches[0];month=monthAt(new Date());live=true;view=role==='cashier'?'tables':'overview';receipt=null;basket=[];await load(true);dialog.close()}}catch(e){$('#authMessage').textContent=t('error');const d=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('pre');s.textContent=t('technical');p.textContent=e.message;d.append(s,p);$('#authMessage').append(d)}finally{button.disabled=false}};
}
view=role==='cashier'?'tables':'overview';
let recoveryToken=location.hash.startsWith('#reset=')?location.hash.slice(7):null;if(recoveryToken)history.replaceState(null,'',location.pathname+location.search);
window.addEventListener('bep:languagechange',()=>{const values=[...document.querySelectorAll('main input,main select')].filter(x=>x.type!=='password').map(x=>[x.id,x.value]);const opened=[...document.querySelectorAll('main details[open] form')].map(x=>x.id);render();for(const [id,value] of values){const el=document.getElementById(id);if(el)el.value=value}for(const id of opened)document.getElementById(id)?.closest('details')?.setAttribute('open','')});
setInterval(()=>{if(live)document.querySelectorAll('[data-clock]').forEach(el=>el.textContent=clock())},1000);
(async()=>{try{await fetchDemo();await load(false);try{ready=(await api('auth/status')).password_accounts===true;if(ready){try{accountIdentity=(await api('auth/me')).identity;live=true;role=accountIdentity.role;branch=accountIdentity.branches[0];view=role==='cashier'?'tables':'overview';month=monthAt(new Date());await load(true)}catch{live=false;await load(false)}}}catch{}if(recoveryToken)authDialog('reset')}catch(e){$('#app').textContent=t('error');console.error(e)}})();
