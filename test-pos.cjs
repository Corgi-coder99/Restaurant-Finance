const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {quote}=require('./dist/workspace/pos-math.js');require('./dist/workspace/labels.js');
for(const [key,values] of Object.entries(WorkspaceLabels)){assert.equal(values.length,4,key);for(const value of values)assert.ok(value.trim(),key)}
const src=fs.readFileSync('dist/workspace/workspace.js','utf8');
for(const match of src.matchAll(/\bt\('([^']+)'\)/g))assert.ok(WorkspaceLabels[match[1]],'Missing label '+match[1]);
const data=JSON.parse(fs.readFileSync('dist/workspace/demo.json')),eur=JSON.parse(fs.readFileSync('dist/workspace/demo-eur.json'));
assert.equal(data.cashier.session.currency,'GBP');assert.equal(eur.cashier.session.currency,'EUR');assert.notEqual(data.cashier.session.catalog[0].price_minor,eur.cashier.session.catalog[0].price_minor);
const menu=data.cashier.session.catalog;
const q=quote(menu,[{product_id:'rice_chicken',quantity:1}]);assert.equal(q.net_minor,1000);assert.equal(q.tax_minor,200);assert.equal(q.gross_minor,1200);
for(let bps of [0,1,1750,3333,9999,10000]){
 const q=quote(menu,menu.map((p,i)=>({product_id:p.id,quantity:i+1})),bps);assert.equal(q.net_minor+q.tax_minor,q.gross_minor);assert.equal(q.subtotal_minor-q.discount_minor,q.gross_minor);assert.equal(q.sale_lines.reduce((a,l)=>a+l.discount_minor,0),q.discount_minor);
}
const huge=quote([{...menu[0],price_minor:100000000}],[{product_id:menu[0].id,quantity:10000}],9999);assert.equal(huge.gross_minor,100000000);assert.equal(huge.net_minor+huge.tax_minor,huge.gross_minor);
const app={innerHTML:''};const locale={vi:'vi-VN',en:'en-GB',fr:'fr-FR',de:'de-DE'};
const sandbox={console,Intl,URL,Date,Map,BigInt,Math,JSON,Object,Array,String,Number,Boolean,Promise,structuredClone,crypto:require('node:crypto').webcrypto,WorkspaceLabels,PosMath:{quote},location:{href:'https://example.test/workspace/',hash:'',pathname:'/workspace/',search:''},history:{replaceState(){}},window:{addEventListener(){},scrollTo(){},print(){}},setInterval(){},setTimeout(){},document:{querySelector:s=>s==='#app'?app:null},I18n:{language:'en',get locale(){return locale[this.language]}}};
vm.createContext(sandbox);vm.runInContext(src.slice(0,src.lastIndexOf('(async()=>')),sandbox);sandbox.data=undefined;
vm.runInContext('bind=()=>{};',sandbox);
for(const lang of ['vi','en','fr','de']){
 sandbox.I18n.language=lang;sandbox.fixture=structuredClone(data);
 for(const r of ['cashier','manager','owner']){
  const views=r==='cashier'?['tables','menu','payment','handover']:r==='manager'?['overview','stock','staff','settings','promotion','accounts']:['overview','settings','forecast','accounts','branch','branchSettings','stock','staff'];
  for(const v of views){sandbox.R=r;sandbox.V=v;vm.runInContext(`demo=fixture;role=R;view=V;session=role==='cashier'?demo.cashier.session:{role,name:'Sample staff',branches:['q1'],currency:'GBP',timezone:'Europe/London'};data=role==='owner'&&!['branch','branchSettings','stock','staff','promotion'].includes(view)?demo.owner:demo.manager;summary=demo.cashier.summary;basket=[];render();`,sandbox);assert.ok(!app.innerHTML.includes('undefined'),lang+' '+r+' '+v);assert.ok(!/₫|VND|triệu/.test(app.innerHTML));assert.ok(app.innerHTML.includes(WorkspaceLabels.back[{vi:0,en:1,fr:2,de:3}[lang]]));}
 }
}
vm.runInContext("role='manager';view='settings';data=fixture.manager;editId='rice_chicken';render();",sandbox);assert.ok(app.innerHTML.includes('name-fr'));assert.ok(app.innerHTML.includes('menuPrice'));
console.log('PASS: four-language workspace rendering, role views, GBP/EUR fixtures, menu settings and exact VAT/discount arithmetic');
