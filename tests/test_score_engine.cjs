const test=require('node:test');
const assert=require('node:assert/strict');
const E=require('../app/static/score-engine.js');
const subject=(name,points)=>({subject:name,bins:points.map(score=>({score,count:1}))});
const subjects=[subject('국어',[130,140]),subject('수학',[135,140]),
subject('물리학Ⅰ',[65]),subject('화학Ⅰ',[66])];
function applicant(){
 return {korean_track:'language',korean_std:140,korean_pct:97,
 math_track:'calculus',math_std:140,math_pct:96,english_grade:1,history_grade:1,
 inquiries:[{name:'물리학Ⅰ',kind:'science',std:65,pct:97},{name:'화학Ⅰ',kind:'science',std:66,pct:96}]};
}
function entry(){
 return {program_key:'test-chem',university:'시험대학교',source_url:'https://example.org/rule',
 spec:{version:1,year:2027,program_key:'test-chem',university:'시험대학교',
 score_scale:1000,weights:{korean:.2,math:.35,english:.1,inquiry:.35},
 components:{korean:{metric:'std',max_value:200},
 math:{metric:'std',max_value:200,track_bonus_pct:{calculus:.05}},
 english:{metric:'grade',grades:{'1':100,'2':95}},
 inquiry:{metric:'converted_std',max_value:75,table_id:'science_2027',aggregation:'mean2'}},
 eligibility:{math_tracks:['calculus','geometry'],inquiry_kinds:['science'],required_inquiries:2},
 history_bonus:{'1':10}},tables:[
 {table_id:'science_2027',subject:'물리학Ⅰ',std_score:65,converted_score:68},
 {table_id:'science_2027',subject:'화학Ⅰ',std_score:66,converted_score:70}]};
}
test('official score bins and subject identity checked, not grade patterns',()=>{
 assert.equal(E.validateOfficial(applicant(),subjects).ok,true);
 const wrong=applicant();wrong.inquiries[1].std=77;
 assert.equal(E.validateOfficial(wrong,subjects).ok,false);
 const duplicate=applicant();duplicate.inquiries[1].name='물리학Ⅰ';
 assert.equal(E.validateOfficial(duplicate,subjects).ok,false);
});
test('2027 university-specific converted score matches official formula engine',()=>{
 const r=E.score(applicant(),entry());
 assert.equal(r.status,'calculated');assert.equal(r.score,829.25);
 assert.equal(r.breakdown['탐구'],322);
});
test('cannot fill missing conversion score with guess',()=>{
 const e=entry();e.tables.pop();
 const r=E.score(applicant(),e);
 assert.equal(r.status,'missing_conversion');assert.equal(r.score,undefined);
});
test('pct-required university cannot infer percentile from standard score',()=>{
 const e=entry();e.spec.components.korean={metric:'pct'};
 const s=applicant();s.korean_pct=null;
 assert.equal(E.score(s,e).status,'needs_percentile');
});
test('math-option restrictions and mismatch in academic year fail closed',()=>{
 const e=entry();const s=applicant();s.math_track='probability';
 assert.equal(E.score(s,e).status,'ineligible');
 e.spec.year=2026;
 assert.equal(E.score(applicant(),e).status,'rule_missing');
});


test('2027 separate grade penalties and percentile inquiry conversions are arithmetic, not admission probabilities',()=>{
 const s=applicant();s.english_grade=3;s.history_grade=5;
 const e=entry();
 e.spec.weights={korean:.25,math:.4,english:0,inquiry:.35};
 e.spec.components.math={metric:'std',max_value:200};
 e.spec.components.english={metric:'grade',grades:{'3':0}};
 e.spec.components.inquiry={metric:'converted_pct',max_value:75,table_id:'example_2027',
 aggregation:'mean2',kind_bonus_points:{science:4}};
 e.spec.history_bonus=undefined;
 e.spec.grade_point_adjustments={
  english:{'3':-2},history:{'5':-2}
 };
 e.tables=[{table_id:'example_2027',subject:'물리학Ⅰ',percentile:97,converted_score:68},
 {table_id:'example_2027',subject:'화학Ⅰ',percentile:96,converted_score:70}];
 const result=E.score(s,e);
 assert.equal(result.status,'calculated');assert.equal(result.score,791.667);
 assert.equal(result.breakdown['영어 감점'],-2);
 e.tables.pop();
 assert.equal(E.score(s,e).status,'missing_conversion');
});


test('precomputed historical prediction curve is consulted only within verified score support',()=>{
 const weighted={status:'calculated',score:800,scale:1000};
 const model={year:2027,exam_type:'september',program_key:'test-chem',
  backtested_years:[2025,2026],
  curve:Array.from({length:121},(_,i)=>({score_fraction:.7+i*.002,probability:.2+i*.005}))};
 const p=E.lookupProbability(weighted,model,'test-chem');
 assert.ok(p!==null&&p>.4&&p<.6);
 assert.equal(E.lookupProbability({...weighted,score:500},model,'test-chem'),null);
 assert.equal(E.lookupProbability(weighted,{...model,backtested_years:[2025]},'test-chem'),null);
 assert.equal(E.lookupProbability(weighted,model,'wrong-major'),null);
 assert.equal(E.lookupProbability({status:'rule_missing'},model,'test-chem'),null);
});
