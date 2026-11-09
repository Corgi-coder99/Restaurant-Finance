/* Friendly presentation and first-use walkthrough. Financial model stays in model.js. */
const uiIcon=name=>`<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
titles.overview=['Hôm nay, quán mình thế nào?','Nhìn rõ tiền thu, tiền chi và phần lợi nhuận còn lại.'];
titles.costs=['Tiền của quán đang đi đâu?','Xem từng khoản chi, từ nguyên liệu đến tiền thuê mặt bằng.'];
titles.simulate=['Thử thay đổi, rồi hãy quyết định','Kéo thanh điều chỉnh để xem lợi nhuận có thể thay đổi thế nào.'];
titles.forecast=['Cùng chuẩn bị cho tháng tới','Khám phá các kịch bản để chủ động hơn trong kinh doanh.'];
titles.invoices=['Ghi lại khoản thu, khoản chi','Thử ghi một giao dịch. Dữ liệu được lưu trên thiết bị này.'];
titles.market=['Theo dõi giá nguyên liệu','Chọn khu vực để khám phá giá tham khảo bằng dữ liệu mẫu.'];
const metricDetails={
 revenue:'Tiền bán hàng sau giảm giá, chưa gồm VAT. Đây là doanh thu, không nhất thiết là tiền đã thu về tài khoản.',
 costs:'Gồm nguyên liệu đã sử dụng, nhân sự, thuê mặt bằng và vận hành khác. Tiền mua hàng tồn kho chưa dùng không tự trở thành giá vốn.',
 profit:'Doanh thu trừ các chi phí vận hành đang hiển thị. Chưa trừ khấu hao, lãi vay và thuế; không phải số tiền mặt có thể rút ra.',
 margin:'Cứ 100 đồng doanh thu, quán giữ lại bao nhiêu đồng lợi nhuận vận hành. Tỷ lệ cao hơn chỉ có ý nghĩa khi chất lượng dữ liệu và phạm vi chi phí giống nhau.'
};
kpis=function(b){const r=Finance.calc(b);const cards=[
 ['revenue','Doanh thu bán hàng',r.revenue,'triệu ₫','Sau giảm giá · chưa gồm VAT','wallet'],
 ['costs','Chi phí vận hành',r.cost,'triệu ₫',`Trong đó tiền thuê: ${fmt(b.rent)} triệu`,'receipt'],
 ['profit','Lợi nhuận vận hành',r.profit,'triệu ₫','Chưa trừ khấu hao, lãi vay & thuế','chart'],
 ['margin','Tỷ lệ lợi nhuận',r.margin,'%',`100₫ doanh thu giữ lại ${fmt(r.margin,1)}₫`,'leaf']
 ];return `<div class="kpis" data-tour="kpis">${cards.map(([id,label,value,unit,detail,icon])=>`<div class="card"><div class="kpi-title"><span>${label}</span><button class="metric-help" data-metric="${id}" aria-label="Giải thích ${label}">${uiIcon('help')}</button></div><div class="kpi-number">${fmt(value,id==='margin'?1:0)}<small>${unit}</small></div><div class="kpi-foot">${detail}</div><div class="money-explain">${uiIcon(icon)}<span>${id==='margin'?'Hiểu hiệu quả từng đồng doanh thu':'Số liệu của chi nhánh đang chọn'}</span></div></div>`).join('')}</div>`};
// Mobile branch cards avoid squeezing financial tables into narrow screens.
branchesTable=function(){return `<div class="card" data-tour="branches"><div class="card-head"><div><h2>Mỗi chi nhánh đang ra sao?</h2><p>So sánh để biết nơi nào cần quan tâm hơn</p></div><span class="pill">Triệu đồng</span></div><div class="table-wrap branch-table-desktop"><table><thead><tr><th>Chi nhánh</th><th>Doanh thu</th><th>Tiền thuê</th><th>Lợi nhuận</th><th>Tỷ lệ LN</th></tr></thead><tbody>${Finance.branches.map(b=>{const r=Finance.calc(b);return `<tr><td><strong>${b.name}</strong><small>${b.city}</small></td><td>${fmt(b.revenue)}</td><td>${fmt(b.rent)}</td><td><strong>${fmt(r.profit)}</strong></td><td><span class="status ${r.margin<16?'amber':''}">${fmt(r.margin,1)}%</span></td></tr>`}).join('')}</tbody></table></div><div class="branch-mini">${Finance.branches.map(b=>{const r=Finance.calc(b);return `<div class="branch-mini-item"><div class="branch-mini-top"><strong>${b.name}</strong><span class="status ${r.margin<16?'amber':''}">${fmt(r.margin,1)}% lợi nhuận</span></div><div class="branch-mini-stats"><span>Doanh thu<b>${fmt(b.revenue)} triệu</b></span><span>Tiền thuê<b>${fmt(b.rent)} triệu</b></span><span>Lợi nhuận<b>${fmt(r.profit)} triệu</b></span></div></div>`}).join('')}</div></div>`};
overview=function(){const b=base(),r=results(),seasonal=[.79,.72,.88,.85,.93,.94,.98,1.01,.96,1.04,1];return `
<section class="welcome-hero" data-tour="welcome" aria-label="Bếp Nhỏ đồng hành"><div class="hero-copy"><span class="hero-label">QUẢN LÝ QUÁN, NHẸ NHÀNG HƠN</span><h2>Hiểu từng đồng.<br>Vững từng quyết định.</h2><p>Mình là Bếp Nhỏ. Cùng mình xem quán đang thu bao nhiêu, chi thế nào và còn lại bao nhiêu nhé!</p><div class="hero-actions"><button class="primary" data-start-tour>Làm quen cùng Bếp Nhỏ ${uiIcon('arrow')}</button><button class="text-button" data-go="simulate">Thử điều chỉnh giá bán →</button></div></div><div class="hero-art"><span class="hero-note">Có mình ở đây rồi!</span><img src="assets/bep-nho.webp" alt="Bếp Nhỏ: chú nồi đầu bếp cầm bảng biểu đồ và vẫy tay" width="226" height="226" fetchpriority="high"></div></section>
<a href="workspace/" class="ops-entry"><span><b>Thu ngân · Quản lý · Chủ</b><small>Chấm công, bàn giao, kho và lương theo đúng vai trò</small></span><span aria-hidden="true">→</span></a><a href="erp/" class="ops-entry"><span><b>Mới · Tự vận hành từ bán hàng đến sổ kế toán</b><small>Xem quy trình mẫu có kho, công nợ, bàn ghế và dự phòng · GBP</small></span><span aria-hidden="true">→</span></a><div class="section-label"><h2>Những con số cần biết</h2><span>Tháng 11 · Dữ liệu mẫu</span></div>${kpis(b)}
<div class="quick-actions" aria-label="Thao tác nhanh"><button class="quick-action" data-go="invoices"><span>${uiIcon('plus')}</span><span><b>Ghi khoản thu, chi</b><small>Bắt đầu từ một giao dịch</small></span>${uiIcon('arrow')}</button><button class="quick-action" data-go="simulate"><span>${uiIcon('sliders')}</span><span><b>Thử điều chỉnh giá</b><small>Xem tác động lên lợi nhuận</small></span>${uiIcon('arrow')}</button><button class="quick-action" data-go="forecast"><span>${uiIcon('chart')}</span><span><b>Lên kế hoạch tháng tới</b><small>Chuẩn bị nhiều kịch bản</small></span>${uiIcon('arrow')}</button></div>
<div class="grid"><div class="card"><div class="card-head"><div><h2>Quán đang phát triển thế nào?</h2><p>Doanh thu và lợi nhuận từ tháng 1 đến tháng 11</p></div><span class="pill">Năm 2026</span></div>${lineChart(seasonal.map(v=>v*b.revenue),seasonal.map(v=>Finance.calc(b,{volume:(v-1)*100}).profit))}</div>${costCard(b)}</div>
<div class="grid">${branchesTable()}<div class="card"><div class="card-head"><div><h2>Bắt đầu từ việc nhỏ</h2><p>Một vài điều đáng dành thời gian xem</p></div>${uiIcon('leaf')}</div><div class="recommend"><div class="rec"><span>${uiIcon('wallet')}</span><div><b>Hiểu rõ tiền thuê mặt bằng</b><p>Tiền thuê chiếm ${fmt(b.rent/b.revenue*100,1)}% doanh thu đang xem. Cùng kiểm tra khoản chi cố định này nhé.</p><button class="btn-link" data-go="costs">Xem cơ cấu chi phí →</button></div></div><div class="rec"><span>${uiIcon('sliders')}</span><div><b>Nếu giá bán thay đổi thì sao?</b><p>Hãy thử cả trường hợp số đơn giảm khi tăng giá để có góc nhìn thực tế hơn.</p><button class="btn-link" data-go="simulate">Thử một kịch bản →</button></div></div><div class="rec"><span>${uiIcon('chart')}</span><div><b>Biết mức doanh thu cần đạt</b><p>Theo giả định hiện tại, doanh thu hòa vốn khoảng ${fmt(r.breakeven)} triệu/tháng.</p><button class="btn-link" data-go="simulate">Xem cách tính và giả định →</button></div></div></div></div></div>`};
const originalRender=render;
let tourActive=false,tourIndex=0,returnFocus=null,autoTourTimer=null;
const tourSteps=[
 {tab:'overview',target:'[data-tour="welcome"]',title:'Chào bạn, mình là Bếp Nhỏ!',text:'Mình giúp bạn làm quen với Bếp Finance qua 7 bước ngắn. Bạn có thể dừng bất cứ lúc nào và mở lại từ nút có hình mình.'},
 {tab:'overview',target:'[data-tour="branch"]',title:'Xem đúng nhà hàng bạn cần',text:'Bộ chọn chi nhánh giúp bạn xem từng quán hoặc toàn chuỗi. Số liệu và biểu đồ sẽ đổi theo lựa chọn của bạn.'},
 {tab:'overview',target:'[data-tour="kpis"]',title:'Hiểu 4 con số quan trọng',text:'Bắt đầu với doanh thu, chi phí, lợi nhuận và tỷ lệ lợi nhuận. Bấm dấu hỏi cạnh từng chỉ số để đọc giải thích. Lợi nhuận không đồng nghĩa với tiền mặt còn lại.'},
 {tab:'costs',target:'#app .two',title:'Biết tiền đang đi đâu',text:'Nguyên liệu, nhân sự, tiền thuê mặt bằng và chi phí khác được tách riêng. Biểu đồ cho bạn biết mỗi khoản chiếm bao nhiêu.'},
 {tab:'simulate',target:'#app .two',title:'Thử trước khi thay đổi giá',text:'Kéo thanh giá bán, lượng bán hoặc tiền thuê để xem lợi nhuận thay đổi. Hãy thử giảm lượng bán khi tăng giá: đây là giả định để tham khảo, chưa tự áp dụng vào quán.'},
 {tab:'invoices',target:'#invoiceForm',title:'Thử ghi một khoản thu, chi',text:'Nhập mã, số tiền, chi nhánh và ngày giao dịch. Bản demo chỉ lưu tại trình duyệt này; giao dịch thử chưa cộng vào báo cáo tổng quan.'},
 {tab:'overview',target:'[data-tour="welcome"]',title:'Bạn đã sẵn sàng rồi!',text:'Hãy thử chọn một chi nhánh, xem chi phí rồi mô phỏng giá. Bếp Nhỏ luôn ở nút hướng dẫn khi bạn cần xem lại. Chúc bạn quản lý quán thật nhẹ nhàng!'}
];
function navigateTo(next,scroll=true){tab=next;render();if(scroll)window.scrollTo({top:0,behavior:'instant'})}
render=function(){
 originalRender();
 const names={overview:'Tổng quan',costs:'Chi phí & mặt bằng',simulate:'Thử điều chỉnh giá',forecast:'Kế hoạch sắp tới',market:'Giá nguyên liệu',invoices:'Sổ thu chi',research:'Thông tin & phương pháp'};
 $('#crumb').textContent=names[tab];
 document.querySelectorAll('aside nav [data-tab]').forEach(button=>{button.setAttribute('aria-current',button.dataset.tab===tab?'page':'false')});
 document.querySelectorAll('[data-mobile-tab]').forEach(button=>{const active=button.dataset.mobileTab===tab;button.classList.toggle('active',active);button.setAttribute('aria-current',active?'page':'false')});
 const moreActive=['forecast','market','research'].includes(tab);$('#moreButton').classList.toggle('active',moreActive);$('#moreButton').setAttribute('aria-current',moreActive?'page':'false');
 document.querySelectorAll('[data-go]').forEach(button=>button.onclick=()=>navigateTo(button.dataset.go));
 document.querySelectorAll('[data-start-tour]').forEach(button=>button.onclick=()=>startTour());
 document.querySelectorAll('[data-metric]').forEach(button=>button.onclick=()=>showMetric(button.dataset.metric,button));
 if(tab==='costs')$('#app .two')?.setAttribute('data-tour','costs');
};
// Financial explanations use a modal instead of a short-lived toast.
const metricDialog=document.createElement('dialog');metricDialog.id='metricDialog';metricDialog.setAttribute('aria-labelledby','metricTitle');metricDialog.innerHTML=`<div class="more-heading"><h2 id="metricTitle">Hiểu con số này</h2><button class="icon-button" id="closeMetric" aria-label="Đóng giải thích">${uiIcon('close')}</button></div><p id="metricText"></p><button class="primary" id="understoodMetric">Mình hiểu rồi</button>`;document.body.append(metricDialog);
function showMetric(id,button){$('#metricTitle').textContent={revenue:'Doanh thu là gì?',costs:'Chi phí gồm những gì?',profit:'Lợi nhuận có phải tiền mặt?',margin:'Tỷ lệ lợi nhuận là gì?'}[id];$('#metricText').textContent=metricDetails[id];returnFocus=button;metricDialog.showModal()}
function closeMetric(){metricDialog.close();returnFocus?.focus()}
$('#closeMetric').onclick=closeMetric;$('#understoodMetric').onclick=closeMetric;
function clearHighlight(){document.querySelectorAll('.tour-focus').forEach(el=>el.classList.remove('tour-focus'))}
function displayStep(){
 const step=tourSteps[tourIndex];navigateTo(step.tab,false);clearHighlight();
 const target=$(step.target);if(target){target.classList.add('tour-focus');target.scrollIntoView({block:'start',behavior:'instant'})}
 $('#tourProgressLabel').textContent=`Làm quen với Bếp Finance · ${tourIndex+1}/${tourSteps.length}`;
 $('#tourTitle').textContent=step.title;$('#tourText').textContent=step.text;
 $('#tourDots').innerHTML=tourSteps.map((_,i)=>`<i class="${i===tourIndex?'active':''}"></i>`).join('');
 $('#tourBack').hidden=tourIndex===0;$('#tourBack').style.display=tourIndex===0?'none':'';
 $('#tourNext').textContent=tourIndex===0?'Bắt đầu →':tourIndex===tourSteps.length-1?'Khám phá thôi!':'Tiếp theo →';
 $('#tourSkip').textContent=tourIndex===tourSteps.length-1?'Đóng hướng dẫn':'Để sau, mình tự khám phá';
}
function startTour(){if(autoTourTimer){clearTimeout(autoTourTimer);autoTourTimer=null}if(tourActive)return;tourActive=true;tourIndex=0;returnFocus=document.activeElement;document.body.classList.add('tour-open');displayStep();$('#tourDialog').showModal();$('#tourNext').focus()}
function finishTour(state){
 if(!tourActive)return;
 tourActive=false;$('#tourDialog').close();clearHighlight();document.body.classList.remove('tour-open');
 try{localStorage.setItem('bep-tour-v2',JSON.stringify({state,step:tourIndex,at:new Date().toISOString()}))}catch{}
 navigateTo('overview');
 if(returnFocus?.isConnected)returnFocus.focus();else $('#mascotLauncher').focus();
}
$('#tourNext').onclick=()=>{if(tourIndex===tourSteps.length-1){finishTour('completed');toast('Bạn có thể mở lại hướng dẫn cùng Bếp Nhỏ bất cứ lúc nào.');return}tourIndex++;displayStep();$('#tourNext').focus()};
$('#tourBack').onclick=()=>{if(tourIndex>0){tourIndex--;displayStep();$('#tourNext').focus()}};
$('#tourSkip').onclick=()=>finishTour('skipped');$('#closeTour').onclick=()=>finishTour('skipped');
$('#tourDialog').addEventListener('cancel',e=>{e.preventDefault();finishTour('skipped')});
$('#mascotLauncher').onclick=()=>startTour();
document.querySelectorAll('aside nav [data-tab]').forEach(button=>button.onclick=()=>navigateTo(button.dataset.tab));
document.querySelectorAll('[data-mobile-tab]').forEach(button=>button.onclick=()=>navigateTo(button.dataset.mobileTab));
$('.brand').onclick=e=>{e.preventDefault();navigateTo('overview')};
$('#moreButton').onclick=()=>$('#moreDialog').showModal();$('#closeMore').onclick=()=>$('#moreDialog').close();
document.querySelectorAll('[data-more-tab]').forEach(button=>button.onclick=()=>{$('#moreDialog').close();navigateTo(button.dataset.moreTab)});
$('#moreTutorial').onclick=()=>{$('#moreDialog').close();startTour()};
render();
let seenTour=false;try{seenTour=Boolean(localStorage.getItem('bep-tour-v2'))}catch{}
if(!seenTour)autoTourTimer=setTimeout(()=>{if(!document.querySelector('dialog[open]'))startTour()},650);
// Reformat the view without losing entered values or the walkthrough step.
window.addEventListener('bep:languagechange',()=>{
 const currentFocus=document.activeElement?.id;
 const values=[...document.querySelectorAll('#app input,#app select')].map(el=>({id:el.id,value:el.value}));
 const scrollY=window.scrollY;
 if(tourActive)displayStep();else render();
 for(const field of values){const el=document.getElementById(field.id);if(el)el.value=field.value}
 if(tab==='forecast')updateForecast();
 if(currentFocus)document.getElementById(currentFocus)?.focus({preventScroll:true});
 window.scrollTo({top:scrollY,behavior:'instant'});
});

// Historical, synthetic evidence is shown separately from editable planning scenarios.
let forecastEvidencePromise=null;
const planningView=forecast;
forecast=function(){return `<div class="card" id="forecastEvidence" style="margin-bottom:20px"><h2>Kiểm định dự báo bằng dữ liệu mẫu</h2><p>Đang tải kết quả kiểm định…</p></div>`+planningView()};
async function showForecastEvidence(){
 const target=document.getElementById('forecastEvidence');if(!target)return;
 if($('#branch').value==='all'){target.innerHTML='<h2>Kiểm định dự báo bằng dữ liệu mẫu</h2><p>Chọn một chi nhánh để xem sai số kiểm định riêng.</p><div class="insight">Các biểu đồ bên dưới vẫn là mô phỏng giả định, không phải dự báo đã huấn luyện trên dữ liệu thật của quán.</div>';return}
 try{
  if(!forecastEvidencePromise)forecastEvidencePromise=fetch('forecast-validation.json').then(r=>{if(!r.ok)throw Error();return r.json()});
  const data=await forecastEvidencePromise;
  if(!target.isConnected||tab!=='forecast')return;
  const branch=['q1','td','dn'][+$('#branch').value],result=data.branches[branch];
  target.innerHTML=`<h2>Kiểm định dự báo bằng dữ liệu mẫu</h2><p>Minh họa lịch sử: 2024–2025 · Mốc dự báo: 01/01/2026 · Không phải dự báo hiện tại.</p><div class="table-wrap"><table><tbody><tr><td>Số tháng đã xác nhận</td><td>${result.reviewed_months}</td></tr><tr><td>Số tháng kiểm tra riêng</td><td>${result.backtest.test_months}</td></tr><tr><td>Sai số tuyệt đối doanh thu (triệu VND)</td><td>${fmt(result.backtest.revenue_mae_vnd/1000000,2)}</td></tr><tr><td>Sai số doanh thu WAPE</td><td>${result.backtest.revenue_wape_pct===null?'Không xác định':fmt(result.backtest.revenue_wape_pct,2)+'%'}</td></tr><tr><td>Sai số tuyệt đối lợi nhuận (triệu VND)</td><td>${fmt(result.backtest.profit_mae_vnd/1000000,2)}</td></tr></tbody></table></div><div class="insight">So sánh mô hình tháng gần nhất, trung bình 3 tháng và cùng kỳ năm trước. Tập kiểm tra cuối không dùng để chọn mô hình. Sai số quá khứ không bảo đảm kết quả tương lai.</div>`;
  I18n.apply(target);
 }catch{if(target.isConnected)target.innerHTML='<h2>Kiểm định dự báo bằng dữ liệu mẫu</h2><p>Chưa tải được bằng chứng kiểm định. Không sử dụng kết quả chưa xác nhận.</p>'}
}
const renderWithLocale=render;
render=function(){renderWithLocale();if(tab==='forecast')showForecastEvidence()};
