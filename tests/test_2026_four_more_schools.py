import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'data/public/university_research/2026_ewha_hongik_kookmin_ajou.json'
def test_2026_four_more_school_weight_types_and_admissions_constraints():
    x=json.loads(P.read_text(encoding='utf-8'))
    records=x['records']
    assert len(records)==12
    assert {r['university'] for r in records}=={
      '이화여자대학교','홍익대학교','국민대학교','아주대학교'}
    assert all(r['year']==2026 and abs(sum(r['weights'].values())-1)<1e-8
     and r['source_url'].startswith('https://www.adiga.kr/') and
     r['fully_verified_conversion_formula'] is False and r['missing'] for r in records)
    pharmacy=next(r for r in records if r['university']=='아주대학교' and r['group']=='자연Ⅰ(공대·약학)')
    assert pharmacy['weights']=={'korean':.20,'math':.35,'english':.15,'inquiry':.30}
    medicine=next(r for r in records if r['university']=='아주대학교' and r['group']=='자연Ⅱ(의학·국방디지털)')
    assert '면접 5%' in medicine['notes']
    free=[r for r in records if r['university']=='국민대학교' and r['group'].startswith('자유전공')]
    assert len(free)==2
