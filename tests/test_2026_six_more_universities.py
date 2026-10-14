import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'data/public/university_research/2026_six_more_universities.json'
def test_2026_six_more_university_partial_components():
    x=json.loads(P.read_text(encoding='utf-8'))
    rows=x['records']
    assert x['year']==2026 and len(rows)==23
    assert {r['university'] for r in rows}=={'한양대학교','중앙대학교','서울시립대학교',
       '숙명여자대학교','숭실대학교','성균관대학교'}
    assert all(r['year']==2026 and r['fully_verified_conversion_formula'] is False
      and r['missing'] and r['source_url'].startswith('https://www.adiga.kr/') for r in rows)
    for row in rows:
        if row['weight_representation']=='official_subject_percentage':
            assert abs(sum(row['component'].values())-1)<1e-9
    hy=next(r for r in rows if r['university']=='한양대학교' and r['group']=='자연계열')
    assert hy['other_selection_component']=='final composite is CSAT 90% + school-record holistic 10%'
    ss=[r for r in rows if r['university']=='숭실대학교']
    assert len(ss)==4 and all(r['math_bonus_ambiguous'] for r in ss)
    skku=[r for r in rows if r['university']=='성균관대학교']
    assert len(skku)==6 and all(r['weight_representation']=='raw_multipliers_NOT_percentages' for r in skku)
