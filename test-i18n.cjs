const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
require('./dist/i18n-catalog.js');const i18n=require('./dist/i18n.js');
const data=JSON.parse(fs.readFileSync('dist/erp/demo.json','utf8')),before=JSON.stringify(data);
for(const [key,entry] of Object.entries(globalThis.BepTranslations)){
 const source=[...key.matchAll(/\{\{(\w+)\}\}/g)].map(x=>x[1]).sort();
 for(const lang of ['en','fr','de']){
  assert.ok(entry[lang]?.trim(),`Missing ${lang}: ${key}`);
  assert.deepEqual([...entry[lang].matchAll(/\{\{(\w+)\}\}/g)].map(x=>x[1]).sort(),source,`Placeholder mismatch ${lang}: ${key}`);
 }
}
i18n.setLanguage('en');assert.equal(i18n.t('Tổng quan'),'Overview');assert.equal(i18n.number(1234.5,1),'1,234.5');assert.equal(i18n.t('2.500 triệu ₫'),'2.500 million VND');assert.equal(i18n.t('Giá trị thuần (GBP)'),'Net amount (GBP)');assert.equal(i18n.t('1. Góp vốn ban đầu vào ngân hàng'),'1. Initial capital paid into the bank');
i18n.setLanguage('fr');assert.equal(i18n.t('Tổng quan'),'Vue d’ensemble');assert.equal(i18n.t('Làm quen với Bếp Finance · 2/7'),'Découvrir Bếp Finance · 2/7');assert.ok(i18n.number(1234.5,1).includes(',5'));
i18n.setLanguage('de');assert.equal(i18n.number(1234.5,1),'1.234,5');assert.equal(i18n.t('Số thanh toán (EUR)'),'Zahlungsbetrag (EUR)');assert.equal(i18n.date('2026-11-08'),'08.11.2026');
assert.equal(i18n.setLanguage('unsupported'),false);assert.equal(i18n.language,'de');i18n.setLanguage('vi');assert.equal(i18n.t('Tổng quan'),'Tổng quan');assert.equal(JSON.stringify(data),before,'Ledger data must not change with locale');
// Small DOM contract test: repeated changes restore original UI text and skip data.
const label={nodeValue:'Tổng quan',parentElement:{closest:()=>null}},userData={nodeValue:'Chi phí',parentElement:{closest:()=>({})}};
const attribute={value:'Mở hướng dẫn sử dụng',closest:()=>null,hasAttribute:name=>name==='aria-label',getAttribute(){return this.value},setAttribute(name,value){this.value=value}};
const body={nodeType:1,closest:()=>null,hasAttribute:()=>false,querySelectorAll:()=>[attribute]};
const store=new Map();const listeners={};
const sandbox={console,Intl,URL,WeakMap,Map,JSON,Date,Object,Number,String,RegExp,CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail}},navigator:{language:'en-GB'},location:{href:'https://example.test/'},localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},dispatchEvent:()=>{},addEventListener:()=>{},MutationObserver:class{disconnect(){}observe(){}},document:{documentElement:{lang:'vi'},body,querySelector:()=>null,querySelectorAll:()=>[],addEventListener:(name,fn)=>listeners[name]=fn,createTreeWalker:()=>{let n=0;const nodes=[label,userData];return {nextNode:()=>nodes[n++]||null}}}};
sandbox.window=sandbox;vm.createContext(sandbox);vm.runInContext(fs.readFileSync('dist/i18n-catalog.js','utf8'),sandbox);vm.runInContext(fs.readFileSync('dist/i18n.js','utf8'),sandbox);listeners.DOMContentLoaded();assert.equal(label.nodeValue,'Overview');assert.equal(userData.nodeValue,'Chi phí');assert.equal(attribute.value,'Open the user guide');sandbox.I18n.setLanguage('fr');assert.equal(label.nodeValue,'Vue d’ensemble');sandbox.I18n.setLanguage('vi');assert.equal(label.nodeValue,'Tổng quan');assert.equal(attribute.value,'Mở hướng dẫn sử dụng');assert.equal(store.get('bep-language'),'vi');label.nodeValue='Doanh thu';sandbox.I18n.setLanguage('de');assert.equal(label.nodeValue,'Umsatz');assert.equal(userData.nodeValue,'Chi phí');
console.log('PASS: complete catalogues, placeholders, locale formats, ERP data integrity, saved preference and repeated DOM translation');
