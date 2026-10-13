const $ = (s)=>document.querySelector(s);
// Pages에서는 게시 가능한 공개 정보만 정적 스냅샷으로 표시합니다.
// 계산·실측 데이터 업로드는 FastAPI 서버가 연결되어야 동작합니다.
const siteConfig = window.ADMISSION_SITE_CONFIG || {staticMode:false, apiBaseUrl:""};
const pageMode = !!siteConfig.staticMode;
const externalApi = String(siteConfig.apiBaseUrl || '').replace(/\/$/, '');
const staticRoutes = {
  '/api/meta':'./data/meta.json',
  '/api/scope':'./data/scope.json',
  '/api/backtest':'./data/backtest.json'
};
const requestApi = (url, options={}) => {
  if (pageMode && !externalApi) {
    if (!staticRoutes[url] || (options.method && options.method.toUpperCase() !== 'GET')) {
      return Promise.reject(new Error('GitHub Pages는 정적 사이트입니다. 점수 계산·업로드에는 별도의 FastAPI 서버가 필요합니다.'));
    }
    return fetch(staticRoutes[url], options);
  }
  return fetch(externalApi ? `${externalApi}${url}` : url, options);
};
const $$ = (s)=>[...document.querySelectorAll(s)];
let lastResults = [];
let currentStudent = null;
let metaData = null;
const escapeHTML = (str) => String(str ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const yearTitle = (year) => `${year}학년도`;
const fmt = (x) => x === null || x === undefined ? '미등록' : Number(x).toLocaleString('ko-KR',{maximumFractionDigits:3});
const statusMessage = (text, error=false) => { $('#form-msg').textContent=text; $('#form-msg').style.color = error?'#b14c42':'#35796d'; };

$$('.nav').forEach(el=>el.addEventListener('click',()=>{
  $$('.nav').forEach(e=>e.classList.toggle('active',e===el));
  $$('.page').forEach(e=>e.classList.toggle('active',e.id===`page-${el.dataset.page}`));
  if (el.dataset.page==='backtest') loadBacktest();
  if (el.dataset.page==='data') loadMeta();
  if (el.dataset.page==='scope') loadScope();
}));

const getStudent = () => {
  const form = $('#score-form');
  const data = Object.fromEntries(new FormData(form).entries());
  return {
    year:Number(data.year), exam_type:data.exam_type,
    korean_pct:Number(data.korean_pct),math_pct:Number(data.math_pct),
    korean_std:data.korean_std!=='' ? Number(data.korean_std):null,
    math_std:data.math_std!=='' ? Number(data.math_std):null,
    math_track:data.math_track,english_grade:Number(data.english_grade),
    history_grade:Number(data.history_grade),
    inquiries:[{kind:data.inquiry1_kind,pct:Number(data.inquiry1_pct),name:data.inquiry1_name},
               {kind:data.inquiry2_kind,pct:Number(data.inquiry2_pct),name:data.inquiry2_name}]
  };
};

function renderResults(){
  const filter=$('#department-filter').value;
  const rows=lastResults.filter(x=>filter==='all'||x.track===filter);
  const target=$('#results');
  if (!currentStudent || lastResults.length===0) {
    if(!currentStudent){target.innerHTML='<div class="empty"><div class="empty-icon">⌕</div><b>성적을 입력하고 계산해 주세요</b><span>등록된 학년도·대학 반영식으로 계산됩니다.</span></div>';return;}
    target.innerHTML=`<div class="empty"><div class="empty-icon">▤</div><b>${currentStudent.year}학년도 대상 대학의 검증된 공식 산식 미등록</b><span>현재 대상은 주요20개 일반대학 + 전국 의치한약수입니다.<br>연도별 모집요강을 확보하기 전에는 점수나 합격률을 임의로 표시하지 않습니다.</span></div>`;
    return;
  }
  if(rows.length===0){target.innerHTML='<div class="empty slim">현재 선택한 계열에 등록된 학과가 없습니다.</div>';return;}
  target.innerHTML=rows.map(r=>{
    const missing=r.score===null || r.score===undefined;
    const hasCutoff=r.margin!==null&&r.margin!==undefined;
    const cutChip=hasCutoff?`<span class="chip ${r.margin>=0?'positive':'negative'}">동일 학년도 70%컷 사후 비교 ${r.margin>=0?'+':''}${fmt(r.margin)}점</span>`:`<span class="chip warn">${currentStudent.exam_type!=='csat'?'모평: 최종 입결 사후 비교 제외':'같은 해 70% 컷 미등록'}</span>`;
    const probChip=r.probability!==null&&r.probability!==undefined?`<span class="chip">검증 제한적 추정 ${(r.probability*100).toFixed(1)}%</span>`:`<span class="chip">합격 확률 산출 불가</span>`;
    const br=r.breakdown ? `<div class="formula-bits">국어 ${fmt(r.breakdown['국어'])} · 수학 ${fmt(r.breakdown['수학'])} · 영어 ${fmt(r.breakdown['영어'])} · 탐구 ${fmt(r.breakdown['탐구'])} · 한국사 ${fmt(r.breakdown['한국사'])}</div>`:'';
    return `<div class="result-row">
      <div class="result-top"><div><strong>${escapeHTML(r.university)} ${escapeHTML(r.department)}</strong><div><small>${escapeHTML(r.campus)}캠퍼스 · ${r.round}군 · ${r.track==='natural'?'자연':'인문'} · ${r.year}학년도</small></div></div><div class="result-score">${missing?'계산 불가':fmt(r.score)}<span>${missing?'':` / ${fmt(r.score_scale)}`}</span></div></div>
      <div class="result-meta">${missing?'<span class="chip warn">해당 연도 산식 검증 필요</span>':cutChip+probChip}</div>${br}
      ${hasCutoff?`<div class="formula-bits">${r.year}학년도 <b>최종등록자 70%컷 ${fmt(r.cutoff_70)}</b>점 (합격 보장선이 아님)</div>`:''}
      ${r.formula_source_url ? `<a href="${escapeHTML(r.formula_source_url)}" target="_blank" rel="noopener noreferrer" class="score-source">원문 산출 기준 확인 ↗</a>`:''}
      ${r.cutoff_source_url ? `<a href="${escapeHTML(r.cutoff_source_url)}" target="_blank" rel="noopener noreferrer" class="score-source" style="margin-left:11px">동일 연도 입결 출처 ↗</a>`:''}
    </div>`;
  }).join('');
}

$('#score-form').addEventListener('submit',async(event)=>{
  event.preventDefault();
  currentStudent=getStudent();
  $('#results').innerHTML='<div class="empty slim">학년도별 공식 반영식 확인 중...</div>';
  $('#result-intro').textContent=`${currentStudent.year}학년도 ${currentStudent.exam_type==='csat'?'실제 수능':currentStudent.exam_type==='june'?'6월 모의평가':'9월 모의평가'} 입력값 · 공식 반영식`;
  try {
    const r=await requestApi('/api/calculate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(currentStudent)});
    const data=await r.json();
    if(!r.ok)throw new Error(JSON.stringify(data.detail||data));
    lastResults=data.results;
    renderResults();
    statusMessage(`${data.count}개 모집단위 확인 · 아직 입결만으로 합격 가능성을 단정하지 않습니다.`);
  } catch(e){lastResults=[];$('#results').innerHTML='<div class="empty slim">계산 요청 실패</div>';statusMessage(`오류: ${e.message}`,true);}
});
$('#department-filter').addEventListener('change',renderResults);

const localKey='js-rens-score-journal-v1';
const savedRecords=()=>{try{return JSON.parse(localStorage.getItem(localKey)||'[]');}catch{return []}};
$('#save-record').addEventListener('click',()=>{
  if(!$('#score-form').reportValidity())return;
  const s=getStudent();
  const rows=savedRecords().filter(r=>!(r.year===s.year&&r.exam_type===s.exam_type));
  rows.push({year:s.year,exam_type:s.exam_type,korean_pct:s.korean_pct,
             math_pct:s.math_pct,inquiry_avg:(s.inquiries[0].pct+s.inquiries[1].pct)/2,
             english_grade:s.english_grade,created:new Date().toISOString()});
  rows.sort((a,b)=>(a.year-b.year)||({'june':0,'september':1,'csat':2}[a.exam_type]-{'june':0,'september':1,'csat':2}[b.exam_type]));
  localStorage.setItem(localKey,JSON.stringify(rows));
  renderTrend();statusMessage(`${yearTitle(s.year)} 성적 기록을 이 브라우저에 저장했습니다.`);
});
$('#clear-records').addEventListener('click',()=>{if(window.confirm('이 브라우저에 저장된 성적 기록을 지울까요?')){localStorage.removeItem(localKey);renderTrend();}});
function renderTrend(){
  const rows=savedRecords();
  if(!rows.length){$('#trend').innerHTML='<div class="empty slim">아직 기록된 모의평가/수능 점수가 없습니다.</div>';return;}
  const width=540,height=160, pad={l:31,r:16,t:10,b:32};
  const px=(i)=>pad.l+(width-pad.l-pad.r)*(rows.length===1?0.5:i/(rows.length-1));
  const py=(v)=>height-pad.b-v/100*(height-pad.t-pad.b);
  const datasets=[{key:'korean_pct',label:'국어',color:'#0c9b88'},{key:'math_pct',label:'수학',color:'#526aa8'},{key:'inquiry_avg',label:'탐구 평균',color:'#c99145'}];
  const lines=datasets.map(d=>{
    const path=rows.map((r,i)=>`${i?'L':'M'}${px(i).toFixed(1)},${py(r[d.key]).toFixed(1)}`).join(' ');
    const circles=rows.map((r,i)=>`<circle cx="${px(i)}" cy="${py(r[d.key])}" r="3.2" fill="${d.color}"/>`).join('');
    return `<path d="${path}" stroke="${d.color}" stroke-width="2.2" fill="none"/>${circles}`;
  }).join('');
  const grids=[0,50,100].map(v=>`<line x1="${pad.l}" y1="${py(v)}" x2="${width-pad.r}" y2="${py(v)}" stroke="#e6edf1"/><text x="${pad.l-9}" y="${py(v)+4}" fill="#96a4b4" text-anchor="end" font-size="10">${v}</text>`).join('');
  const xticks=rows.map((r,i)=>`<text x="${px(i)}" y="${height-11}" font-size="10" fill="#7992a0" text-anchor="middle">${String(r.year).slice(2)}${{june:'6',september:'9',csat:'수'}[r.exam_type]}</text>`).join('');
  $('#trend').innerHTML=`<svg class="svgtrend" viewBox="0 0 ${width} ${height}" role="img" aria-label="국어, 수학, 탐구 백분위 변화 그래프">${grids}${lines}${xticks}</svg><div class="formula-bits">${datasets.map(d=>`<span style="color:${d.color};margin-right:12px">● ${d.label}</span>`).join('')} · 기록 ${rows.length}건</div>`;
}

async function loadMeta(){
  try{
    const resp=await requestApi('/api/meta');metaData=await resp.json();
    const ruleCount=metaData.program_coverage.reduce((sum,x)=>sum+x.program_count,0);
    $('#metric-rules').textContent=String(ruleCount);
    $('#metric-outcomes').innerHTML=`${metaData.application_outcomes.toLocaleString()}<span>건</span>`;
    const byYear=Object.fromEntries(metaData.program_coverage.map(x=>[x.year,x]));
    $('#coverage').innerHTML=`<div class="coverage-grid">${metaData.supported_years.map(year=>{
      const v=byYear[year]||{program_count:0,cutoff_count:0};
      return `<div class="coverage-card"><strong>${year}</strong><small>학년도</small><span>환산식 ${v.program_count}</span><small>동년 컷 ${v.cutoff_count}</small></div>`;
    }).join('')}</div><p class="form-msg">현재 분석 범위 내의 검증 완료된 산식은 ${ruleCount}개입니다. 기존 범위 밖 예제 ${metaData.outside_scope_legacy_examples}개는 삭제하지 않고 보관 중이며 합격 예측 결과에 포함하지 않습니다.</p>`;
    $('#sources').innerHTML=metaData.sources.map(s=>`<div class="source"><a target="_blank" rel="noopener noreferrer" href="${escapeHTML(s.url)}">↗ ${escapeHTML(s.label)}</a><small>출처 원문 및 학년도 확인</small></div>`).join('');
  }catch(e){$('#coverage').textContent=`데이터 로딩 실패: ${e.message}`;}
}
async function loadScope(){
  try{
    const response=await requestApi('/api/scope');
    const d=await response.json();
    if(!response.ok)throw new Error('대상 목록 불러오기 실패');
    $('#target-universities').innerHTML=d.universities.map((name,i)=>`<div class="uni-tile"><span>${String(i+1).padStart(2,'0')}</span><b>${escapeHTML(name)}</b>${d.registered_universities.includes(name)?'<small>모집단위 일부 등록</small>':'<small>공식 자료 확인 필요</small>'}</div>`).join('');
    $('#target-medical').innerHTML=Object.entries(d.medical_categories).map(([key,value])=>`<div class="med-tile"><div class="medical-marker">${escapeHTML(value.slice(0,1))}</div><b>${escapeHTML(value)}</b><small>${d.medical_fields_registered.includes(key)?'일부 모집단위 등록':'원문 자료 미등록'}</small></div>`).join('');
    $('#target-registration').innerHTML=`범위: 일반대학 <b>${d.universities.length}개</b> + 전국 매디컬 <b>5개 계열</b> · 공식 모집단위/학년도 등록 <b>${d.registered_program_years}건</b><p>2022~2026학년도: 사후 연도별 검증, 2027학년도: 사전 예측만 가능. 미등록 산식 및 입결은 추정하지 않습니다.</p>`;
  }catch(e){$('#target-registration').textContent=e.message;}
}

async function loadBacktest(){
  const el=$('#backtest-results');el.innerHTML='<div class="empty slim">검증 지표 계산 중...</div>';
  try{
    const r=await requestApi('/api/backtest');const d=await r.json();
    el.innerHTML=`<p class="form-msg">개별 실측 합불 데이터: <b>${d.count}건</b>. 테스트 연도 성적은 훈련에 사용하지 않습니다.</p>`+
      d.evaluations.map(e=>`<div class="backtest-row"><b>${e.test_year}학년도</b><span>${e.status==='evaluated'?`<span class="results-ok">AUC ${fmt(e.auc)} / Brier ${fmt(e.brier)} (기준 ${fmt(e.brier_baseline)}) / 정확도 ${fmt(e.accuracy_at_50)}</span>`:'<span style="color:#a07838">실제 합불 데이터 부족 · 검증 불가</span>'}</span><small>학습 ${e.train_n}건 / 테스트 ${e.test_n}건</small></div>`).join('');
  }catch(e){el.textContent=`오류: ${e.message}`;}
}
$('#refresh-backtest').addEventListener('click',loadBacktest);
$('#upload-form').addEventListener('submit',async(e)=>{
  e.preventDefault();const el=$('#upload-msg');el.textContent='CSV 행별 입력값·증빙 상태 검사 중...';
  try{
    const res=await requestApi('/api/import/outcomes',{method:'POST',body:new FormData(e.target)});
    const d=await res.json();if(!res.ok)throw new Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));
    el.textContent=`${d.imported}건 적재 성공. 증빙 검증은 별도로 진행해야 합니다.`;loadMeta();
  }catch(err){el.textContent=`가져오기 실패: ${err.message}`;el.style.color='#ae4f45';}
});
if (pageMode) {
  // 정적 배포에서 개인 지원 결과 업로드 UI를 노출하지 않음.
  const panel = $('#upload-form')?.closest('.panel.upload');
  if(panel) panel.style.display='none';
  if (!externalApi) {
    const button=$('#score-form button[type="submit"]');
    button.disabled=true;
    button.textContent='계산 API 연결 대기';
    statusMessage('GitHub Pages 공개 자료 대시보드입니다. 성적 추이 기록은 사용 가능하며, 대학 환산점수는 백엔드 연결 후 이용합니다.');
  }
}
renderTrend();loadMeta();loadScope();
