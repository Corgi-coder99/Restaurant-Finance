/* Shared locale layer. Translates UI text, never ledger objects or input values. */
(function(root){
 'use strict';
 const languages={vi:{name:'Tiếng Việt',locale:'vi-VN'},en:{name:'English',locale:'en-GB'},fr:{name:'Français',locale:'fr-FR'},de:{name:'Deutsch',locale:'de-DE'}};
 const catalog=root.BepTranslations||{};
 const normalize=s=>String(s).replace(/\s+/g,' ').trim();
 let lang='vi';
 function supported(value){return typeof value==='string'&&Object.hasOwn(languages,value.split('-')[0])?value.split('-')[0]:null}
 try{lang=supported(new URL(root.location.href).searchParams.get('lang'))||supported(root.localStorage.getItem('bep-language'))||supported(root.navigator.language)||'en'}catch{}
 const patterns=Object.keys(catalog).filter(key=>key.includes('{{')).sort((a,b)=>b.replace(/\{\{\w+\}\}/g,'').length-a.replace(/\{\{\w+\}\}/g,'').length).map(key=>{
  const keys=[];let parts=key.split(/(\{\{\w+\}\})/g).map(part=>{if(/^\{\{/.test(part)){keys.push(part.slice(2,-2));return '(.+?)'}return part.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')});
  return {key,keys,regex:new RegExp('^'+parts.join('')+'$')};
 });
 function monthLabel(month,year,short=false){const options={month:short?'short':'long',timeZone:'UTC'};if(year)options.year='numeric';return new Intl.DateTimeFormat(languages[lang].locale,options).format(new Date(Date.UTC(year||2026,month-1,1)))}
 function translate(source,depth=0){
  const value=normalize(source);if(lang==='vi'||!value||depth>4)return source;
  const entry=catalog[value];if(entry)return entry[lang]||entry.en||value;
  let m=value.match(/^Tháng (\d{1,2}), (\d{4})$/);if(m)return monthLabel(+m[1],+m[2]);
  m=value.match(/^Tháng (\d{1,2})$/);if(m)return monthLabel(+m[1]);
  for(const p of patterns){const match=p.regex.exec(value);if(match){let out=catalog[p.key][lang]||catalog[p.key].en;for(let i=0;i<p.keys.length;i++)out=out.replaceAll('{{'+p.keys[i]+'}}',translate(match[i+1],depth+1));return out}}
  // Translate composed UI labels without rewriting arbitrary user content.
  const symbol=value.match(/^([●↓↗⌂←]\s*)(.+)$/);if(symbol){const out=translate(symbol[2],depth+1);if(out!==symbol[2])return symbol[1]+out}
  const arrow=value.match(/^(.+?)(\s*→)$/);if(arrow){const out=translate(arrow[1],depth+1);if(out!==arrow[1])return out+arrow[2]}
  if(value.includes(' · '))return value.split(' · ').map(x=>translate(x,depth+1)).join(' · ');
  return value;
 }
 let observer=null;
 const originals=new WeakMap(),attributes=new WeakMap();
 const skip='script,style,textarea,input,code,pre,[data-i18n-skip],[data-language-select]';
 function textNode(node){if(node.parentElement?.closest(skip))return;const old=originals.get(node);const source=old&&node.nodeValue===old.output?old.source:node.nodeValue;const leading=source.match(/^\s*/)[0],trailing=source.match(/\s*$/)[0];const value=normalize(source);if(!value)return;const output=leading+translate(value)+trailing;originals.set(node,{source,output});if(node.nodeValue!==output)node.nodeValue=output}
 function apply(container=root.document?.body){
  if(!container)return;
  if(observer)observer.disconnect();
  const walker=root.document.createTreeWalker(container,4);let node;while((node=walker.nextNode()))textNode(node);
  const elements=[...(container.nodeType===1?[container]:[]),...container.querySelectorAll('[aria-label],[title],[alt],[placeholder]')];
  for(const element of elements){if(element.closest(skip))continue;let stored=attributes.get(element)||{};for(const name of ['aria-label','title','alt','placeholder']){if(!element.hasAttribute(name))continue;const old=stored[name],current=element.getAttribute(name),source=old&&current===old.output?old.source:current,output=translate(source);stored[name]={source,output};if(current!==output)element.setAttribute(name,output)}attributes.set(element,stored)}
  const description=root.document.querySelector('meta[name=description]');if(description){const old=attributes.get(description)?.content;const current=description.getAttribute('content');const source=old&&current===old.output?old.source:current;const output=translate(source);attributes.set(description,{content:{source,output}});if(current!==output)description.setAttribute('content',output)}
  if(observer)observer.observe(root.document.body,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:['aria-label','title','alt','placeholder']});
 }
 function setLanguage(value,persist=true){const next=supported(value);if(!next)return false;lang=next;if(persist)try{root.localStorage.setItem('bep-language',lang)}catch{};if(root.document){root.document.documentElement.lang=lang;root.document.querySelectorAll('[data-language-select]').forEach(el=>{el.value=lang;el.setAttribute('aria-label',{vi:'Ngôn ngữ',en:'Language',fr:'Langue',de:'Sprache'}[lang])});root.dispatchEvent(new CustomEvent('bep:languagechange',{detail:{language:lang}}));apply();const title=root.document.querySelector('title');if(title)textNode(title)}return true}
 function formatNumber(value,digits=0){return new Intl.NumberFormat(languages[lang].locale,{maximumFractionDigits:digits}).format(value)}
 function formatDate(value){const m=String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);if(!m)return value;return new Intl.DateTimeFormat(languages[lang].locale,{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'UTC'}).format(new Date(Date.UTC(+m[1],+m[2]-1,+m[3])))}
 root.I18n={get language(){return lang},get locale(){return languages[lang].locale},languages,t:translate,setLanguage,apply,number:formatNumber,date:formatDate,monthLabel};
 if(root.document){root.document.documentElement.lang=lang;root.document.addEventListener('DOMContentLoaded',()=>{root.document.querySelectorAll('[data-language-select]').forEach(el=>{el.value=lang;el.setAttribute('aria-label',{vi:'Ngôn ngữ',en:'Language',fr:'Langue',de:'Sprache'}[lang]);el.addEventListener('change',()=>setLanguage(el.value))});observer=new MutationObserver(()=>apply());apply();const title=root.document.querySelector('title');if(title)textNode(title)});root.addEventListener('storage',event=>{if(event.key==='bep-language'&&supported(event.newValue))setLanguage(event.newValue,false)})}
 if(typeof module!=='undefined')module.exports=root.I18n;
})(typeof window!=='undefined'?window:globalThis);
