/* 2027 only: GitHub Actions precomputes, browser renders vetted public snapshots. */
'use strict';
const $=s=>document.querySelector(s);
const escapeHTML=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=x=>typeof x==='number'?x.toLocaleString('ko-KR',{maximumFractionDigits:3}):'—';
const dataUrl=name=>'./data/'+name;
async function getJSON(name){const r=await fetch(dataUrl(name),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return r.json();}
let distributions=[],selectedDistribution=null,predictions=[],targets=[];
function showMsg(el,text){el.replaceChildren();const n=document.createElement('div');n.className='empty slim';n.textContent=text;el.append(n);}
function subjectKey(s){return s.subject+(s.option_name==='all'?'':' · '+s.option_name);}
function setMetric(id,value){const e=$(id);if(e)e.textContent=fmt(value);}
function drawDistribution(){
 const d=selectedDistribution,stage=$('#distribution-chart');if(!d)return;
 setMetric('#subject-total',d.total);setMetric('#subject-highest',d.max_score);setMetric('#subject-high-count',d.max_score_count);
 $('#official-score-link').href=d.source_url;
 const mode=$('#distribution-mode').value;
 const bins=[...d.bins].sort((a,b)=>a.score-b.score);
 if(!bins.length){showMsg(stage,'도수분포가 등록되지 않았습니다.');return;}
 let cumulative=0;
 const points=[...bins].reverse().map(b=>{cumulative+=b.count;return {...b,cumulative}}).reverse();
 const maximum=Math.max(...points.map(p=>mode==='count'?p.count:p.cumulative),1);
 const width=960,height=264,left=57,right=14,top=20,bottom=38;
 const plotW=width-left-right,plotH=height-top-bottom,spacing=plotW/points.length;
 const minScore=points[0].score,maxScore=points.at(-1).score;
 const yValue=v=>top+plotH*(1-v/maximum);
 let markup='<svg viewBox="0 0 960 264" class="frequency-svg" role="img" aria-label="'+escapeHTML(subjectKey(d))+' 표준점수 도수분포">';
 for(let i=0;i<=4;i++){const v=maximum*i/4;const y=yValue(v);markup+='<line x1="'+left+'" y1="'+y+'" x2="'+(width-right)+'" y2="'+y+'" stroke="#e6eef2"/><text x="'+(left-10)+'" y="'+(y+4)+'" text-anchor="end" font-size="11" fill="#80909f">'+escapeHTML(Math.round(v).toLocaleString('ko-KR'))+'</text>';}
 for(const p of points){const index=p.score===undefined?0:points.indexOf(p);const val=mode==='count'?p.count:p.cumulative,x=left+index*spacing+0.4,yy=yValue(val);
   markup+='<rect class="chart-bar" data-score="'+p.score+'" x="'+x.toFixed(2)+'" y="'+yy.toFixed(2)+'" width="'+Math.max(.9,spacing-1).toFixed(2)+'" height="'+Math.max(.8,top+plotH-yy).toFixed(2)+'" rx="1"><title>표준점수 '+p.score+' · '+fmt(val)+'명</title></rect>';
 }
 for(let i=0;i<5;i++){const v=minScore+(maxScore-minScore)*i/4,ix=Math.round(i*(points.length-1));markup+='<text x="'+(left+ix*spacing+spacing/2)+'" y="'+(height-11)+'" text-anchor="middle" font-size="12" fill="#66798a">'+Math.round(v)+'</text>';}
 markup+='</svg>';
 stage.innerHTML=markup;
 stage.querySelector('svg').addEventListener('click',e=>{const bar=e.target.closest('[data-score]');if(!bar)return;
  const score=Number(bar.dataset.score),point=points.find(p=>p.score===score);if(!point)return;
  const atOrAbove=point.cumulative,share=100*atOrAbove/d.total;
  $('#selected-score').textContent='표준점수 '+score+'점 · 해당 점수 '+fmt(point.count)+'명 · '+score+'점 이상 '+fmt(atOrAbove)+'명 ('+share.toFixed(2)+'%)';
  stage.querySelectorAll('.chart-bar').forEach(x=>x.classList.toggle('picked',x===bar));
 });
 const table=$('#score-frequency-table');
 table.innerHTML='<table><thead><tr><th>표준점수</th><th>해당 인원</th><th>해당 점수 이상 누적</th></tr></thead><tbody>'+[...points].reverse().map(x=>'<tr><td>'+x.score+'</td><td>'+fmt(x.count)+'명</td><td>'+fmt(x.cumulative)+'명</td></tr>').join('')+'</tbody></table>';
 $('#selected-score').textContent='그래프 막대를 선택하면 점수별 인원과 누적 비율을 표시합니다.';
}
async function loadDistributions(){
 const stage=$('#distribution-chart');
 try{
  const data=await getJSON('score-distribution-2027.json');
  distributions=data.subjects||[];if(!distributions.length){showMsg(stage,'2027학년도 공식 도수분포 검증 대기 중입니다.');return;}
  setMetric('#metric-subjects',distributions.length);
  setMetric('#metric-korean',distributions.find(s=>s.subject==='국어')?.total);
  setMetric('#metric-math',distributions.find(s=>s.subject==='수학')?.total);
  $('#subject-select').innerHTML=distributions.map((s,i)=>'<option value="'+i+'">'+escapeHTML(subjectKey(s))+'</option>').join('');
  selectedDistribution=distributions.find(s=>s.subject==='국어')||distributions[0];
  $('#subject-select').value=String(distributions.indexOf(selectedDistribution));
  drawDistribution();
 }catch(e){showMsg(stage,'점수 분포를 불러오지 못했습니다: '+e.message);}
}
$('#subject-select').addEventListener('change',e=>{selectedDistribution=distributions[Number(e.target.value)];drawDistribution();});
$('#distribution-mode').addEventListener('change',drawDistribution);
async function loadForecast(){
 const el=$('#forecast-results');
 try{
  const data=await getJSON('score-adjustment.json');
  const ready=(data.subjects||[]).filter(x=>x.status==='ready');
  if(!ready.length){showMsg(el,'2027학년도 9평의 확정 분포는 등록됐습니다. 다만 과거 9평·수능의 대응 분포가 아직 충분하지 않아 보정 점수는 계산하지 않습니다.');return;}
  el.innerHTML='<p class="form-msg">전국 누적 분위 기준 예상 수능 표준점수입니다. 합격확률이 아닙니다.</p>'+ready.map(s=>{
    const qs=(s.quantiles||[]).filter(q=>[90,95,99].includes(q.cumulative_percentile));
    return '<details class="forecast-details"><summary>'+escapeHTML(s.subject)+' · '+fmt(qs.length)+'개 대표 분위 확인</summary><div class="frequency-table"><table><thead><tr><th>누적 분위</th><th>9평 점수</th><th>예상 수능 점수</th></tr></thead><tbody>'+qs.map(q=>'<tr><td>'+q.cumulative_percentile+'%</td><td>'+fmt(q.september_std_score)+'</td><td>'+fmt(q.projected_csat_std_score)+'</td></tr>').join('')+'</tbody></table></div></details>';
  }).join('');
 }catch(e){showMsg(el,'수능 점수 전망을 불러오지 못했습니다: '+e.message);}
}
function renderPredictions(){
 const container=$('#university-results');
 const term=$('#uni-search').value.trim().toLocaleLowerCase(),track=$('#uni-track').value,
       profile=$('#grade-search').value.trim();
 const filtered=predictions.filter(r=>(!term||(r.university+' '+r.department).toLocaleLowerCase().includes(term))&&(track==='all'||r.track===track)&&(!profile||r.grade_profile.includes(profile)));
 if(!filtered.length){showMsg(container,'조건에 맞는 대학별 계산 결과가 없습니다. 2027학년도 해당 모집단위의 공식 반영비율·변환표준점수 및 확정 성적 경계값이 검증되어야 결과가 생성됩니다.');return;}
 container.innerHTML='<p class="form-msg">2027학년도 검증된 사전 계산 시나리오 '+fmt(filtered.length)+'건 · 처음 40건 표시</p>'+filtered.slice(0,40).map(r=>{
 const p=(r.admission_probability!==null && Number.isFinite(r.admission_probability))?(100*r.admission_probability).toFixed(1)+'%':'검증 전';
 return '<div class="university-result"><div><strong>'+escapeHTML(r.university)+' · '+escapeHTML(r.department)+'</strong><div class="muted-xs">등급 경계 '+escapeHTML(r.grade_profile)+' · '+escapeHTML(r.exam_type==='september'?'9월 모의평가':'시험')+'</div></div><div><strong class="result-score">'+fmt(r.converted_score)+' <small>/ '+fmt(r.score_scale)+'</small></strong><div class="muted-xs">합격확률 '+p+'</div></div><a href="'+escapeHTML(r.formula_source_url)+'" target="_blank" rel="noopener noreferrer">산식 원문 ↗</a></div>';
 }).join('');
}
async function loadUniversities(){
 try{
  const d=await Promise.all([getJSON('precomputed-2027.json'),getJSON('targets-2027.json')]);
  predictions=d[0];targets=d[1].universities||[];
  $('#university-targets').innerHTML='<p class="muted-xs">분석 대상 주요 20개 대학 (매디컬은 전국)</p><div class="target-grid">'+targets.map(s=>'<span class="target-pill">'+escapeHTML(s)+'</span>').join('')+'</div>';
  renderPredictions();
 }catch(e){showMsg($('#university-results'),'대학별 자료를 불러오지 못했습니다: '+e.message);}
}
for(const id of ['#uni-search','#grade-search'])$(id).addEventListener('input',renderPredictions);
$('#uni-track').addEventListener('change',renderPredictions);
async function loadCohort(){
 const el=$('#cohort-results');
 try{
  const s=await getJSON('cohort-snapshot.json');
  const arr=s.predictions||[];
  if(!arr.length){showMsg(el,'비공개 9평 모의지원 표본 수집과 대학별 공식 환산식 검증이 완료되면 Actions에서 일괄 분석한 익명 결과를 제공합니다.');return;}
  el.className='';
  el.innerHTML=arr.map(r=>'<div class="university-result"><div><strong>'+escapeHTML(r.university)+' · '+escapeHTML(r.department)+'</strong><div class="muted-xs">모의지원 익명 집계 '+escapeHTML(r.participant_count_band)+'명</div></div><div class="muted-xs">점수 중앙값 '+fmt(r.score_p50)+' / '+fmt(r.score_scale)+'</div></div>').join('');
 }catch(e){showMsg(el,'모의지원 집계를 불러오지 못했습니다: '+e.message);}
}
Promise.all([loadDistributions(),loadForecast(),loadUniversities(),loadCohort()]);
