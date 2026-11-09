"""Price-inclusive POS quote. Discounts allocated in pennies before per-line VAT."""
from backend.erp.service import ERPError,number

def catalog(c,state,branch):
 base={r['id']:{'id':r['id'],'name':r['name'],'names':{'vi':r['name'],'en':'Chicken rice','fr':'Riz au poulet','de':'Hähnchen mit Reis'},'price_minor':r['price_minor'],'vat_bps':0,'category':'main','icon':'rice','active':True,'components':[],
   'recipe':[dict(x) for x in c.execute('SELECT item_id,quantity FROM erp_recipes WHERE product_id=?',(r['id'],))]} for r in c.execute('SELECT * FROM erp_products')}
 base.update({id:p for (b,id),p in state['menu'].items() if b==branch})
 return base

def quote(menu,items,discount_bps=0):
 if not isinstance(items,list) or not 1<=len(items)<=50:raise ERPError('Order requires 1..50 lines')
 lines=[]
 for item in items:
  if not isinstance(item,dict) or set(item)!={'product_id','quantity'} or not isinstance(item['product_id'],str):raise ERPError('Invalid order line')
  product=menu.get(item['product_id'])
  if not product or not product['active']:raise ERPError('Menu item is unavailable')
  qty=number(item['quantity'],1,10000);gross=qty*product['price_minor']
  lines.append({'product_id':product['id'],'name':product['name'],'names':product['names'],'quantity':qty,'unit_price_minor':product['price_minor'],'subtotal_minor':gross,'vat_bps':product['vat_bps']})
 subtotal=sum(l['subtotal_minor'] for l in lines);discount=subtotal*number(discount_bps,0,10000)//10000
 cuts=[discount*l['subtotal_minor']//subtotal for l in lines];remaining=discount-sum(cuts)
 for i in sorted(range(len(lines)),key=lambda i:discount*lines[i]['subtotal_minor']%subtotal,reverse=True)[:remaining]:cuts[i]+=1
 for i,line in enumerate(lines):
  gross=line['subtotal_minor']-cuts[i];denom=10000+line['vat_bps'];net=(gross*10000+denom//2)//denom
  line.update(discount_minor=cuts[i],net_minor=net,tax_minor=gross-net,gross_minor=gross)
 return {'subtotal_minor':subtotal,'discount_minor':discount,'discount_bps':discount_bps,'net_minor':sum(l['net_minor'] for l in lines),'tax_minor':sum(l['tax_minor'] for l in lines),'gross_minor':subtotal-discount,'sale_lines':lines,'tax_basis':'Configured price-inclusive VAT, rounded per line; not a certified statutory tax engine'}

def recipe(menu,product_id):
 p=menu[product_id]
 if not p.get('components'):return p.get('recipe',[])
 total={}
 for component in p['components']:
  other=menu.get(component['product_id'])
  if not other or not other['active'] or other.get('components'):raise ERPError('Combo component unavailable or nested combo')
  for x in other['recipe']:total[x['item_id']]=total.get(x['item_id'],0)+x['quantity']*component['quantity']
 return [{'item_id':id,'quantity':qty} for id,qty in total.items()]
