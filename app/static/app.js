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

// Read the GitHub Actions privacy-gated snapshot. Never run online ML inference.
async function loadCohortSnapshot(){
 const el=$('#cohort-snapshot-results');
 try {
  const res=await fetch('./data/cohort-snapshot.json');
  if(!res.ok)throw Error('HTTP '+res.status);
  const data=await res.json();
  const groups=data.predictions||[];
  if(!groups.length){el.innerHTML='<div class="empty slim">아직 공개 가능한 모의지원 배치 결과가 없습니다. 비공개 성적 수집 서비스와 2027학년도 공식 환산식 검증이 필요합니다.</div>';return;}
  const date=data.generated_at_utc?new Date(data.generated_at_utc).toLocaleString('ko-KR'):'날짜 미상';
  let html='<p class="form-msg">생성일: '+esc(date)+' · 공개 가능 모집단위 '+num(groups.length)+'개 · 9평 모의지원자의 환산점수 분위값</p>';
  for(const p of groups){
    html+='<div class="result-row"><div class="result-top"><strong>'+esc(p.university)+' '+esc(p.department)+'</strong><small>표본 '+esc(p.participant_count_band)+'명</small></div>';
    html+='<div class="formula-bits">환산점수 하위25% '+num(p.score_p25)+' · 중앙값 '+num(p.score_p50)+' · 상위25% '+num(p.score_p75)+' / '+num(p.score_scale)+'</div>';
    html+='<div class="result-meta"><span class="chip">자발적 모의지원 표본</span><span class="chip warn">검증된 합격 확률 미산출</span></div></div>';
  }
  el.innerHTML=html;
 }catch(err){el.textContent='배치 결과 조회 실패: '+err.message;}
}
loadCohortSnapshot();


// Offline score-frequency adjustment: no individual records.
async function loadScoreAdjustment() {
  const el = document.querySelector('#score-adjustment-results');
  if (!el) return;
  try {
    const r = await fetch('./data/score-adjustment.json');
    if (!r.ok) throw Error('HTTP ' + r.status);
    const d = await r.json();
    if (!d.ready_subject_count) {
      el.textContent = '공식 표준점수별 인원 분포가 등록되지 않았거나 동일 과목의 과거 9평·수능 자료가 3개 학년도 미만입니다. 임의 보정값을 표시하지 않습니다.';
      return;
    }
    el.replaceChildren();
    const header = document.createElement('p');
    header.className = 'form-msg';
    header.textContent = '2027학년도 보정 가능 과목 ' + d.ready_subject_count + '개 · 과거 동일 분위 표준점수 분포 변화에 기반';
    el.append(header);
    for (const group of d.subjects || []) {
      const detail = document.createElement('details');
      detail.className = 'result-row';
      detail.open = group.status === 'ready';
      const summary = document.createElement('summary');
      summary.textContent = group.subject + (group.option_name === 'all' ? ' (전체)' : ' · ' + group.option_name)
        + ' · ' + (group.status === 'ready' ? group.historical_pairs.length + '개 학년도 비교' : '과거 자료 쌍 부족');
      detail.append(summary);
      if (group.status === 'ready') {
        const wrapper = document.createElement('div');
        wrapper.style.overflowX = 'auto';
        const table = document.createElement('table');
        table.style.cssText = 'width:100%;margin-top:12px;text-align:right;font-size:12px;border-collapse:collapse';
        const headerRow = document.createElement('tr');
        for (const label of ['전국 누적위치', '9평 표준점수', '예상 수능 표준점수', '과거 이동폭 최소~최대']) {
          const th = document.createElement('th');
          th.textContent = label;
          headerRow.append(th);
        }
        table.append(headerRow);
        for (const q of group.quantiles || []) {
          if (![50, 80, 90, 95, 99].includes(q.cumulative_percentile)) continue;
          const tr = document.createElement('tr');
          for (const value of [q.cumulative_percentile + '%', q.september_std_score,
            q.projected_csat_std_score, q.historical_shift_min + ' ~ ' + q.historical_shift_max]) {
            const td = document.createElement('td');
            td.style.padding = '7px 4px';
            td.textContent = String(value);
            tr.append(td);
          }
          table.append(tr);
        }
        wrapper.append(table);
        detail.append(wrapper);
      }
      if (group.reference_sources && group.reference_sources.length) {
        const anchor = document.createElement('a');
        anchor.className = 'score-source';
        anchor.href = group.reference_sources[0];
        anchor.target = '_blank';
        anchor.rel = 'noopener noreferrer';
        anchor.textContent = '공식 도수분포 출처 ↗';
        detail.append(anchor);
      }
      el.append(detail);
    }
  } catch (error) {
    el.textContent = '표준점수 보정자료를 불러오지 못했습니다: ' + error.message;
  }
}
loadScoreAdjustment();
