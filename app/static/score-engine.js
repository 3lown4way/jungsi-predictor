/* Pure deterministic OFFICIAL university scoring only, not machine learning.
 * Input values come from the user's official September score report.
 * Official formulas and per-university conversion tables are built in GitHub Actions.
 */
(function(root,factory){
 const api=factory();
 if(typeof module!=='undefined'&&module.exports) module.exports=api;
 else root.ScoreEngine=api;
})(typeof window!=='undefined'?window:this,function(){
 'use strict';
 const round3=x=>Math.round((x+Number.EPSILON)*1000)/1000;
 const validInteger=x=>typeof x==='number'&&Number.isInteger(x);
 const validGrade=x=>validInteger(x)&&x>=1&&x<=9;
 const pctValid=x=>x===null||x===undefined||(validInteger(x)&&x>=0&&x<=100);
 const intStd=x=>validInteger(x)&&x>=0&&x<=250;
 const isHttps=x=>typeof x==='string'&&x.startsWith('https://');
 function validateOfficial(student,subjects){
  if(!student||!Array.isArray(subjects)||!subjects.length)
   return {ok:false,message:'2027학년도 9평 공식 점수 분포를 먼저 불러와야 합니다.'};
  if(!['speech','language'].includes(student.korean_track)||!['probability','calculus','geometry'].includes(student.math_track))
   return {ok:false,message:'국어·수학 선택과목을 확인해 주세요.'};
  if(!validGrade(student.english_grade)||!validGrade(student.history_grade))
   return {ok:false,message:'영어·한국사 등급은 1~9등급만 입력할 수 있습니다.'};
  if(!Array.isArray(student.inquiries)||student.inquiries.length!==2||
     student.inquiries[0].name===student.inquiries[1].name)
   return {ok:false,message:'서로 다른 탐구 두 과목을 선택해 주세요.'};
  const fields=[['국어','국어',student.korean_std,student.korean_pct],
    ['수학','수학',student.math_std,student.math_pct],
    ...student.inquiries.map((s,i)=>['탐구 '+(i+1),s.name,s.std,s.pct])];
  for(const [area,subject,score,pct] of fields){
   if(!intStd(score))return {ok:false,message:area+' 표준점수를 정수로 입력해 주세요.'};
   if(!pctValid(pct))return {ok:false,message:area+' 공식 백분위는 0~100 정수여야 합니다.'};
   const distribution=subjects.find(s=>s.subject===subject);
   if(!distribution || !distribution.bins.some(b=>b.score===score))
    return {ok:false,message:area+'('+subject+')의 '+score+'점은 등록된 2027학년도 9평 공식 도수분포에 없습니다. 시험·과목·입력값을 다시 확인하세요.'};
  }
  return {ok:true,message:'공식 표준점수 분포 대조 완료. 국어·수학은 선택과목 통합 분포로만 대조됩니다.'};
 }
 function score(student,entry){
  if(!entry||!entry.spec||entry.spec.year!==2027||entry.spec.program_key!==entry.program_key||
     entry.spec.university!==entry.university||!isHttps(entry.source_url))
   return {status:'rule_missing',message:'해당 모집단위의 2027 공식 환산식이 검증되지 않았습니다.'};
  const spec=entry.spec,components=spec.components,weights=spec.weights;
  if(!components||!weights||!['korean','math','english','inquiry'].every(k=>components[k]&&Number.isFinite(weights[k])&&weights[k]>=0&&weights[k]<=1)||
      Math.abs(Object.values(weights).reduce((a,b)=>a+b,0)-1)>1e-8||!Number.isFinite(spec.score_scale))
   return {status:'rule_missing',message:'공식 환산식 구조 검증 실패'};
  const e=spec.eligibility||{};
  if(e.math_tracks&&!e.math_tracks.includes(student.math_track))
   return {status:'ineligible',message:'이 모집단위는 해당 수학 선택과목을 허용하지 않습니다.'};
  if(e.inquiry_kinds&&student.inquiries.some(i=>!e.inquiry_kinds.includes(i.kind)))
   return {status:'ineligible',message:'이 모집단위의 탐구 응시과목 요건과 다릅니다.'};
  if(student.inquiries.length<(e.required_inquiries===undefined?2:e.required_inquiries))
   return {status:'ineligible',message:'필수 탐구과목 수가 부족합니다.'};
  function raw(area,part,inq){
   const mode=part.metric,origin=inq||student;
   if(mode==='grade'){
    const grade=area==='english'?student.english_grade:student[area+'_grade'];
    const result=(part.grades||{})[String(grade)];
    return typeof result==='number'?{value:result}:{status:'rule_missing',message:area+' 등급 환산표 값 없음'};
   }
   const key=inq?(mode==='pct'||mode==='converted_pct'?'pct':'std'):area+'_'+(mode==='pct'||mode==='converted_pct'?'pct':'std');
   const value=origin[key];
   if(value===null||value===undefined)
    return {status:'needs_percentile',message:area==='inquiry'?'탐구 백분위 입력 필요':area+' 공식 백분위 입력 필요'};
   if(mode==='pct')return {value};
   if(mode==='std')return part.max_value>0?{value:100*value/part.max_value}:{status:'rule_missing',message:'표준점수 기준 만점 누락'};
   if(mode==='converted_std'||mode==='converted_pct'){
    const subject=inq?inq.name:area;
    const row=(entry.tables||[]).find(t=>t.table_id===part.table_id&&t.subject===subject&&(mode==='converted_pct'?t.percentile===value:t.std_score===value));
    if(!row)return {status:'missing_conversion',message:subject+' '+(mode==='converted_pct'?'백분위':'표준점수')+' '+value+'의 공식 대학별 변환표준점수가 미등록입니다.'};
    const bonus=((part.kind_bonus_points||{})[inq?.kind]||0);
    return part.max_value>0?{value:100*(row.converted_score+bonus)/part.max_value}:{status:'rule_missing',message:'변환표 만점 누락'};
   }
   return {status:'rule_missing',message:'지원하지 않는 공식 산식'};
  }
  const breakdown={};
  for(const area of ['korean','math','english','inquiry']){
   const part=components[area];let v;
   if(area==='inquiry'){
    const values=[];
    for(const inquiry of student.inquiries){
     const r=raw(area,part,inquiry);if(r.status)return r;
     values.push(r.value*(1+((part.kind_bonus_pct||{})[inquiry.kind]||0)));
    }
    const aggregation=part.aggregation||'mean2';
    if(aggregation==='best1')v=Math.max(...values);
    else if(values.length>=2&&aggregation==='mean2')v=(values[0]+values[1])/2;
    else if(values.length>=2&&aggregation==='sum2')v=values[0]+values[1];
    else return {status:'rule_missing',message:'탐구 반영 과목 수 확인 필요'};
   } else {
    const r=raw(area,part);if(r.status)return r;v=r.value;
    if(area==='math')v*=1+((part.track_bonus_pct||{})[student.math_track]||0);
   }
   if(!Number.isFinite(v))return {status:'rule_missing',message:'산출 규칙 계산 실패'};
   breakdown[({korean:'국어',math:'수학',english:'영어',inquiry:'탐구'})[area]]=round3(v*weights[area]*spec.score_scale/100);
  }
  if(spec.history_bonus){
   const bonus=spec.history_bonus[String(student.history_grade)];
   if(typeof bonus!=='number')return {status:'rule_missing',message:'한국사 등급별 가산표 값 없음'};
   breakdown['한국사']=bonus;
  }
  for(const area of ['english','history']){
   const table=(spec.grade_point_adjustments||{})[area];
   if(!table)continue;
   const grade=area==='english'?student.english_grade:student.history_grade;
   if(!Object.prototype.hasOwnProperty.call(table,String(grade)))
    return {status:'rule_missing',message:'영어·한국사 등급별 감점표 누락'};
   breakdown[area==='english'?'영어 감점':'한국사 감점']=table[String(grade)];
  }
  return {status:'calculated',score:round3(Object.values(breakdown).reduce((a,b)=>a+b,0)),
          scale:spec.score_scale,breakdown,weights};
 }
 return {validateOfficial,score};
});
