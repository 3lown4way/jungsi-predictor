from pathlib import Path
import json
P=Path(__file__).resolve().parents[1]/'data/public/university_research/sogang_2023_partially_verified.json'
def test_sogang_2023_original_official_year_specific_formula():
    r=json.loads(P.read_text(encoding='utf-8'))[0]
    assert r['year']==2023 and r['university']=='서강대학교'
    assert r['source_url'].startswith('https://admission.sogang.ac.kr/upload/file/')
    assert r['components']=={'korean_multiplier':1.1,'math_multiplier':1.3,'inquiry_multiplier_each':.6}
    e=r['official_worked_example']
    value=e['korean_std']*1.1+e['math_std']*1.3+sum(e['inquiry_converted_example'])*.6+e['english_bonus']+e['history_bonus']
    assert round(value,2)==490.52
    assert not r['final_converted_inquiry_table_verified']
    assert not r['applicant_outcomes_verified']
