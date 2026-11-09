(function(root){
function quote(menu,items,bps=0){
 if(!Array.isArray(items)||items.length>50||!Number.isInteger(bps)||bps<0||bps>10000)throw Error('Invalid order');
 const lines=items.map(i=>{const p=menu.find(p=>p.id===i.product_id);if(!p||!p.active||!Number.isSafeInteger(i.quantity)||i.quantity<1||i.quantity>10000)throw Error('Invalid menu line');return {product_id:p.id,name:p.name,names:p.names,quantity:i.quantity,unit_price_minor:p.price_minor,vat_bps:p.vat_bps,subtotal_minor:p.price_minor*i.quantity}});
 const subtotal=lines.reduce((a,l)=>a+BigInt(l.subtotal_minor),0n),discount=subtotal*BigInt(bps)/10000n,cuts=lines.map(l=>subtotal?discount*BigInt(l.subtotal_minor)/subtotal:0n);const remain=Number(discount-cuts.reduce((a,b)=>a+b,0n));
 [...lines.keys()].sort((a,b)=>{const x=discount*BigInt(lines[a].subtotal_minor)%subtotal,y=discount*BigInt(lines[b].subtotal_minor)%subtotal;return x===y?0:x>y?-1:1}).slice(0,remain).forEach(i=>cuts[i]++);
 lines.forEach((l,i)=>{const gross=BigInt(l.subtotal_minor)-cuts[i],denom=BigInt(10000+l.vat_bps),net=(gross*10000n+denom/2n)/denom;l.discount_minor=Number(cuts[i]);l.gross_minor=Number(gross);l.net_minor=Number(net);l.tax_minor=Number(gross-net)});
 return {subtotal_minor:Number(subtotal),discount_minor:Number(discount),net_minor:lines.reduce((a,l)=>a+l.net_minor,0),tax_minor:lines.reduce((a,l)=>a+l.tax_minor,0),gross_minor:Number(subtotal-discount),sale_lines:lines};
}
root.PosMath={quote};if(typeof module!=='undefined')module.exports=root.PosMath;
})(globalThis);
