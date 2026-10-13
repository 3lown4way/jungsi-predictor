/* Static-only reader for PRECOMPUTED public research snapshots. No personal score forms. */
'use strict';
const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=value=>typeof value==='number' ? value.toLocaleString('ko-KR',{maximumFractionDigits:3}) : '—';
let rows=[],shown=0,summary=null;
const YEARS=[2022,2023,2024,2025,2026,2027];
const gradePattern=record=>record.grade_profile;
function filtered(){const exam=$('#filter-exam').value,search=$('#filter-search').value.trim().toLocaleLowerCase(),grade=$('#filter-grade').value;
 return rows.filter(r=>(exam==='all'||r.exam_type===exam)&&(grade==='all'||r.grade_profile===grade)&&(`${r.university} ${r.department} ${r.bundle_id}`.toLocaleLowerCase().includes(search)));}
function results(reset=true){if(reset)shown=0;const filteredRows=filtered();const subset=filteredRows.slice(0,shown+100);shown=subset.length;
 const view=$('#dataset-results');$('#more-results').style.display=shown<filteredRows.length?'inline-flex':'none';
 if(!filteredRows.length){view.innerHTML='<div class="empty"><div class="empty-icon">▤</div><b>현재 조건에 계산된 결과가 없습니다.</b><span>해당 학년도·시험의 공식 등급 경계점수와 대학별 산식이 검증되어야 자동 생성됩니다. 빈 결과에 임의 합격선을 채우지 않습니다.</span></div>';return;}
 view.innerHTML=subset.map(r=>{
 const margin=r.retrospective_margin, tag=margin===null?'<span class="chip warn">입결 사후 비교 없음</span>':`<span class="chip ${margin>=0?'positive':'negative'}">70%컷과 사후 차이 ${margin>0?'+':''}${num(margin)}</span>`;
 return `<div class="result-row"><div class="result-top"><div><strong>${esc(r.university)} · ${esc(r.department)}</strong><div><small>${r.year}학년도 ${esc(r.exam_type)} · ${esc(r.bundle_id)} · 등급 경계 ${esc(gradePattern(r))}</small></div></div><div class="result-score">${num(r.converted_score)}<span> / ${num(r.score_scale)}</span></div></div><div class="result-meta"><span class="chip">등급 하한값 시나리오</span>${tag}<span class="chip">실제 합불 검증 전</span></div><div class="formula-bits">${Object.entries(r.subjects).map(([k,v])=>`${esc(k)}: ${esc(v)}`).join(' · ')}</div><a class="score-source" target="_blank" rel="noopener noreferrer" href="${esc(r.formula_source_url)}">환산식 출처 ↗</a>${r.cutoff_source_url?` <a class="score-source" target="_blank" rel="noopener noreferrer" href="${esc(r.cutoff_source_url)}">70%컷 출처 ↗</a>`:''}</div>`;}).join('');
}
function populateGradeFilter(){const current=$('#filter-grade').value;const opts=[...new Set(rows.map(gradePattern))].sort();$('#filter-grade').innerHTML='<option value="all">전체 패턴</option>'+opts.map(k=>`<option value="${esc(k)}">${esc(k)}</option>`).join('');if(opts.includes(current))$('#filter-grade').value=current;}
async function loadYear(){const y=$('#filter-year').value;const url=`./data/precomputed-${encodeURIComponent(y)}.json`;
 $('#dataset-download').href=url;$('#dataset-download').download=`precomputed-${y}.json`;$('#data-status').textContent=`${y}학년도 데이터를 읽는 중…`;
 try{const response=await fetch(url);if(!response.ok)throw new Error(`HTTP ${response.status}`);const data=await response.json();if(!Array.isArray(data))throw new Error('데이터셋 형식 오류');rows=data;populateGradeFilter();results();$('#data-status').textContent=`${y}학년도 사전 계산 ${num(rows.length)}행 · 현재 화면은 개인 성적 입력을 받지 않습니다.`;}
 catch(err){rows=[];populateGradeFilter();results();$('#data-status').textContent=`데이터셋을 읽지 못했습니다: ${err.message}`;}
}
async function init(){try{const r=await fetch('./data/precomputed-summary.json');if(!r.ok)throw Error(`HTTP ${r.status}`);summary=await r.json();
 const counts=summary.records_by_year||{};$('#metric-count').textContent=num(Object.values(counts).reduce((s,n)=>s+Number(n),0));$('#metric-bundles').textContent=num(summary.bundle_count);
 $('#coverage').innerHTML=YEARS.map(y=>`<div class="coverage-card"><strong>${y}</strong><small>학년도</small><span>사전 계산 ${num(counts[y]||0)}행</span></div>`).join('');
 }catch(err){$('#data-status').textContent=`데이터 현황 오류: ${err.message}`;}
 await loadYear();}
$('#filter-year').addEventListener('change',loadYear);
for(const id of ['filter-exam','filter-search','filter-grade'])$(id).addEventListener(id==='filter-search'?'input':'change',()=>results());
$('#more-results').addEventListener('click',()=>results(false));
init();
