/* 2027 university-major predictions are precomputed by Actions. No browser-side ML. */
'use strict';
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>typeof n==='number'&&Number.isFinite(n)?n.toLocaleString('ko-KR',{maximumFractionDigits:3}):'—';
const getJSON=async name=>{const r=await fetch('./data/'+name,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return r.json();};
const showMsg=(el,message)=>{el.replaceChildren();const x=document.createElement('div');x.className='empty slim';x.textContent=message;el.append(x);};
const shortName=name=>name.replace(/대학교$/,'대').replace(/여자대$/,'여대');
let outlook=[],targets=[],groupLabels={},cohort=[],distributions=[],selectedDistribution=null,officialStudent=null,ruleMap=new Map();
const isMedical=p=>Boolean(p.medical_field);
function matchSearch(p,term){if(!term)return true;const text=[p.university,shortName(p.university),p.department,p.campus].join(' ').toLocaleLowerCase();return text.includes(term);}
function matchCategory(p,category){if(category==='all')return true;if(category==='general')return !isMedical(p);if(category==='medical')return isMedical(p);return p.medical_field===category;}
function renderPrograms(){
 const text=$('#uni-search').value.trim().toLocaleLowerCase(),
 category=$('#uni-category').value,track=$('#uni-track').value;
 const rows=outlook.filter(p=>matchSearch(p,text)&&matchCategory(p,category)&&
  (track==='all'||p.track===track));
 const area=$('#university-results');
 if(!rows.length){
  showMsg(area,text||category!=='all'||track!=='all'?
   '검색조건에 등록된 2027학년도 모집단위가 없습니다. 지원 불가능이 아닌 공식 모집단위 자료 미등록일 수 있습니다.':
   '2027학년도 공식 반영식이 검증·등록된 대상 모집단위가 아직 없습니다. 아래 대상 대학 명단은 조사 범위이며 합격 추천이 아닙니다.');
  return;
 }
 if(!officialStudent){
  showMsg(area,'위의 2027학년도 9평 공식 표준점수와 탐구과목을 입력하고 결과 확인을 누르세요.');
  return;
 }
 const calculated=rows.map(p=>({...p,result:ruleMap.has(p.program_key)?
   ScoreEngine.score(officialStudent,ruleMap.get(p.program_key)):
   {status:'rule_missing',message:'2027학년도 공식 대학별 산식이 아직 등록되지 않았습니다.'}}));
 calculated.sort((a,b)=>(b.result.status==='calculated')-(a.result.status==='calculated')||
  a.university.localeCompare(b.university,'ko')||a.department.localeCompare(b.department,'ko'));
 const visible=calculated.slice(0,60);
 area.innerHTML='<p class="form-msg">2027학년도 공식 성적표를 기준으로 '+fmt(rows.length)+'개 모집단위 검토 · '+fmt(visible.length)+'개 표시 · 대학별 환산만 계산, 합격확률 ML은 사전검증 대기</p>'+
 visible.map(p=>{
  const s=p.result,hasScore=s.status==='calculated';
  const scoreLabel=hasScore?fmt(s.score)+' / '+fmt(s.scale):'미산출';
  const breakdown=hasScore?'<div class="card-data-note">영역별 반영: '+Object.entries(s.breakdown).map(([k,v])=>esc(k)+' '+fmt(v)).join(' · ')+'</div>':'';
  const w=hasScore?'<div class="card-data-note">반영비율: 국어 '+fmt(s.weights.korean*100)+'% · 수학 '+fmt(s.weights.math*100)+'% · 영어 '+fmt(s.weights.english*100)+'% · 탐구 '+fmt(s.weights.inquiry*100)+'%</div>':'';
  const hasCohort=typeof p.cohort_score_p50==='number';
  const cohortInfo=hasCohort?'<div class="card-data-note">9평 모의지원 중앙값 '+fmt(p.cohort_score_p50)+' · 가운데 50% 구간 '+fmt(p.cohort_score_p25)+'–'+fmt(p.cohort_score_p75)+'</div>':'';
  const why=hasScore?'2027학년도 검증 산식 기준 · 9평 원점수와 수능 환산 동일시 금지':esc(s.message);
  const source=p.formula_source_url?'<a class="score-source" href="'+esc(p.formula_source_url)+'" target="_blank" rel="noopener noreferrer">대학 산식 원문 ↗</a>':'<span class="muted-xs">공식 산식 미등록</span>';
  const odds='분석 준비 중'; // No score-dependent calibrated probability curve has been published.
  return '<article class="admission-card"><div class="admission-card-top"><div><strong class="admission-card-title">'+esc(p.university)+' · '+esc(p.department)+'</strong><div class="muted-xs">'+esc(p.campus||'')+' · '+esc(p.admission_round||'모집군 확인 전')+'군 · '+(isMedical(p)?'매디컬':'일반대학')+'</div></div><span class="admission-status">'+(hasScore?'공식 환산점수 계산':'산식·자료 준비 중')+'</span></div><div class="admission-card-data"><div><span>나의 9평 대학별 환산점수</span><strong>'+esc(scoreLabel)+'</strong><small>'+why+'</small></div><div><span>합격 가능성</span><strong class="placeholder-text">'+odds+'</strong><small>0%가 아닌 검증된 모델 미등록</small></div></div>'+w+breakdown+cohortInfo+'<div class="admission-card-footer">'+source+'</div></article>';
 }).join('');
}
function renderTargets(){
 const el=$('#university-targets');
 const term=$('#uni-search').value.trim().toLocaleLowerCase();
 const selected=$('#uni-category').value;
 const registered=new Set(outlook.map(p=>p.university));
 let uni=targets.filter(u=>!term||[u,shortName(u)].some(v=>v.toLocaleLowerCase().includes(term)));
 if(selected==='medical'||!['all','general'].includes(selected))uni=[];
 if(!uni.length){el.innerHTML='<p class="muted-xs">현재 검색에서 표시할 일반대학 조사 대상이 없습니다. 전국 매디컬은 실제 확인된 모집단위만 상단 결과에 포함됩니다.</p>';return;}
 el.innerHTML='<p class="muted-xs">아래 목록은 연구 대상 20개교입니다. 예측 완료 대학 목록이 아닙니다.</p><div class="target-grid">'+uni.map(u=>'<button type="button" class="target-pill '+(registered.has(u)?'registered':'')+'" data-university="'+esc(u)+'">'+esc(u)+'<small>'+(registered.has(u)?'모집단위 일부 등록':'자료 수집 중')+'</small></button>').join('')+'</div>';
 el.querySelectorAll('button[data-university]').forEach(b=>b.addEventListener('click',()=>{
  $('#uni-search').value=b.dataset.university;$('#uni-category').value='all';$('#uni-track').value='all';
  renderPrograms();renderTargets();$('#university-results').scrollIntoView({behavior:'smooth',block:'nearest'});
 }));
}
async function loadAdmissions(){
 try{
  const [d,t,rulebook]=await Promise.all([getJSON('admissions-outlook-2027.json'),getJSON('targets-2027.json'),getJSON('scoring-rules-2027.json')]);
  outlook=d.programs||[];targets=t.universities||[];groupLabels=t.medical_fields||{};
  ruleMap=new Map((rulebook.rules||[]).map(r=>[r.program_key,r]));
  $('#metric-programs').textContent=fmt(d.program_count);
  $('#metric-ready').textContent=fmt(d.score_ready_count);
  $('#metric-probability').textContent=fmt(d.probability_ready_count);
  renderPrograms();renderTargets();
 }catch(e){showMsg($('#university-results'),'대학별 사전 계산 데이터를 불러오지 못했습니다: '+e.message);}
}
for(const id of ['#uni-search','#uni-category','#uni-track']){
 const el=$(id);el.addEventListener(id==='#uni-search'?'input':'change',()=>{renderPrograms();renderTargets();});
}
async function loadCohort(){
 const el=$('#cohort-results');
 try{
  const d=await getJSON('cohort-snapshot.json');
  const arr=d.predictions||[];
  if(!arr.length){showMsg(el,'2027학년도 대학별 모의지원 집계가 아직 없습니다. 검증된 환산식과 동의받은 9평 모의지원 표본이 충분히 쌓인 뒤 Actions 일괄 집계 결과가 게시됩니다.');return;}
  el.innerHTML=arr.map(p=>'<article class="admission-card"><strong>'+esc(p.university)+' · '+esc(p.department)+'</strong><div class="card-data-note">표본 '+esc(p.participant_count_band)+'명 · 점수 중앙값 '+fmt(p.score_p50)+' / '+fmt(p.score_scale)+' · 가운데 50% 구간 '+fmt(p.score_p25)+'–'+fmt(p.score_p75)+'</div><p class="muted-xs">자발적 모의지원 표본으로 실제 합격을 의미하지 않습니다.</p></article>').join('');
 }catch(e){showMsg(el,'모의지원 집계를 불러올 수 없습니다: '+e.message);}
}
async function loadForecast(){
 const el=$('#forecast-results');
 try{
  const d=await getJSON('score-adjustment.json');
  const ready=(d.subjects||[]).filter(x=>x.status==='ready');
  if(!ready.length){showMsg(el,'현재 과거 9평·수능 간 동일 분위 비교 데이터가 충분하지 않아 수능 점수 보정이 보류돼 있습니다.');return;}
  el.innerHTML=ready.map(r=>'<div class="card-data-note"><strong>'+esc(r.subject)+'</strong> · 과거 시험 분포 기반 보정 준비 완료</div>').join('');
 }catch(e){showMsg(el,'예측 근거 로딩 오류: '+e.message);}
}
const subjectKey=s=>s.subject+(s.option_name==='all'?'':' · '+s.option_name);
function drawDistribution(){
 const d=selectedDistribution,stage=$('#distribution-chart');if(!d)return;
 $('#subject-total').textContent=fmt(d.total);$('#subject-highest').textContent=fmt(d.max_score);$('#subject-high-count').textContent=fmt(d.max_score_count);
 $('#official-score-link').href=d.source_url;
 const bins=[...d.bins].sort((a,b)=>a.score-b.score),mode=$('#distribution-mode').value;
 let total=0;const points=[...bins].reverse().map(p=>{total+=p.count;return {...p,cumulative:total}}).reverse();
 if(!points.length){showMsg(stage,'해당 과목 도수분포가 없습니다.');return;}
 const W=900,H=245,L=60,R=12,T=18,B=33,dx=(W-L-R)/points.length,plotH=H-T-B;
 const max=Math.max(1,...points.map(p=>mode==='count'?p.count:p.cumulative));
 const y=v=>T+plotH*(1-v/max);
 let svg='<svg class="frequency-svg" viewBox="0 0 900 245" aria-label="'+esc(subjectKey(d))+' 표준점수 분포">';
 for(let i=0;i<=4;i++){const v=max*i/4;svg+='<line x1="'+L+'" y1="'+y(v)+'" x2="'+(W-R)+'" y2="'+y(v)+'" stroke="#e7ecf0"/><text x="'+(L-7)+'" y="'+(y(v)+4)+'" text-anchor="end" font-size="10" fill="#8594a4">'+fmt(Math.round(v))+'</text>';}
 points.forEach((p,i)=>{const val=mode==='count'?p.count:p.cumulative,yy=y(val);svg+='<rect class="chart-bar" data-score="'+p.score+'" x="'+(L+i*dx+0.2).toFixed(2)+'" y="'+yy.toFixed(2)+'" width="'+Math.max(.9,dx-.8).toFixed(2)+'" height="'+Math.max(.8,T+plotH-yy).toFixed(2)+'"><title>'+p.score+'점: '+fmt(val)+'명</title></rect>';});
 [0,.25,.5,.75,1].forEach(p=>{const i=Math.round((points.length-1)*p);svg+='<text x="'+(L+i*dx)+'" y="'+(H-7)+'" text-anchor="middle" font-size="11" fill="#71889d">'+points[i].score+'</text>';});
 stage.innerHTML=svg+'</svg>';
 stage.querySelector('svg').addEventListener('click',e=>{const bar=e.target.closest('[data-score]');if(!bar)return;const p=points.find(x=>x.score===Number(bar.dataset.score));$('#selected-score').textContent=p.score+'점 · 해당 인원 '+fmt(p.count)+'명 · 해당 점수 이상 누적 '+fmt(p.cumulative)+'명 ('+(p.cumulative/d.total*100).toFixed(2)+'%)';stage.querySelectorAll('.chart-bar').forEach(x=>x.classList.toggle('picked',bar===x));});
 $('#score-frequency-table').innerHTML='<table><thead><tr><th>표준점수</th><th>해당 인원</th><th>해당 점수 이상 누적</th></tr></thead><tbody>'+[...points].reverse().map(p=>'<tr><td>'+p.score+'</td><td>'+fmt(p.count)+'명</td><td>'+fmt(p.cumulative)+'명</td></tr>').join('')+'</tbody></table>';
}

const getVal=(form,name)=>form.elements.namedItem(name).value;
const numOrNull=s=>s===''?null:Number(s);
const SCIENCE=/^(물리학|화학|생명과학|지구과학)[ⅠⅡ12]$/;
const SOCIAL=new Set(['생활과 윤리','윤리와 사상','한국지리','세계지리','동아시아사','세계사','경제','정치와 법','사회·문화','사회문화']);
const kindOf=s=>SCIENCE.test(s)?'science':SOCIAL.has(s)?'social':'vocational';
function buildReport(form){
 const inquiries=[1,2].map(i=>{
  const name=getVal(form,'inquiry'+i+'_name');
  return {name,kind:kindOf(name),std:Number(getVal(form,'inquiry'+i+'_std')),
   pct:numOrNull(getVal(form,'inquiry'+i+'_pct'))};
 });
 return {year:2027,exam_type:'september',
  korean_track:getVal(form,'korean_track'),korean_std:Number(getVal(form,'korean_std')),
  korean_pct:numOrNull(getVal(form,'korean_pct')),
  math_track:getVal(form,'math_track'),math_std:Number(getVal(form,'math_std')),
  math_pct:numOrNull(getVal(form,'math_pct')),
  english_grade:Number(getVal(form,'english_grade')),
  history_grade:Number(getVal(form,'history_grade')),inquiries};
}
$('#official-score-form').addEventListener('submit',event=>{
 event.preventDefault();
 const student=buildReport(event.currentTarget);
 const verdict=ScoreEngine.validateOfficial(student,distributions);
 const message=$('#score-input-message');
 if(!verdict.ok){message.classList.add('input-error');message.textContent=verdict.message;officialStudent=null;renderPrograms();return;}
 officialStudent=student;
 message.classList.remove('input-error');
 message.textContent='표준점수 공식 분포 대조 완료. 성적은 서버에 전송하거나 저장하지 않습니다. 검증된 대학별 산식만 계산합니다.';
 renderPrograms();
 $('#university-results').scrollIntoView({behavior:'smooth',block:'nearest'});
});
function populateInquirySubjects(){
 const inquiry=distributions.filter(s=>!['국어','수학'].includes(s.subject));
 const options='<option value="">과목 선택</option>'+inquiry.map(s=>
  '<option value="'+esc(s.subject)+'">'+esc(s.subject)+'</option>').join('');
 for(const id of ['#inquiry1-name','#inquiry2-name']){
  const sel=$(id),previous=sel.value;
  sel.innerHTML=options;
  if(inquiry.some(s=>s.subject===previous))sel.value=previous;
 }
}

async function loadDistribution(){
 try{
  const d=await getJSON('score-distribution-2027.json');distributions=d.subjects||[];
  if(!distributions.length){showMsg($('#distribution-chart'),'확정된 과목별 도수분포를 아직 등록하지 않았습니다.');return;}
  const select=$('#subject-select');
  select.innerHTML=distributions.map((s,i)=>'<option value="'+i+'">'+esc(subjectKey(s))+'</option>').join('');
  populateInquirySubjects();
  selectedDistribution=distributions.find(s=>s.subject==='국어')||distributions[0];select.value=String(distributions.indexOf(selectedDistribution));drawDistribution();
 }catch(e){showMsg($('#distribution-chart'),'확정 점수 분포 로딩 오류: '+e.message);}
}
$('#subject-select').addEventListener('change',e=>{selectedDistribution=distributions[Number(e.target.value)];drawDistribution();});
$('#distribution-mode').addEventListener('change',drawDistribution);
Promise.all([loadAdmissions(),loadCohort(),loadForecast(),loadDistribution()]);
