/* Spreadsheet-safe CSV: keep numeric cells numeric, escape untrusted text formulas. */
(function(root){
 function cell(value){
  let text;
  if(typeof value==='number'){
   if(!Number.isFinite(value))throw new TypeError('Non-finite numeric CSV value');
   text=String(value);
  }else if(value==null)text='';
  else if(typeof value==='string')text=/^[\s]*[=+@-]/.test(value)?"'"+value:value;
  else if(typeof value==='boolean'||typeof value==='bigint')text=String(value);
  else throw new TypeError('Unsupported CSV cell type');
  return '"'+text.replace(/"/g,'""')+'"';
 }
 const api={cell,serialize:rows=>rows.map(row=>row.map(cell).join(',')).join('\r\n')};
 root.BepCSV=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
