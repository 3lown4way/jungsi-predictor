import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/public/university_research/2025_hanyang_uos_sookmyung_ewha.json"
def test_real_2025_weights_are_not_copied_from_2026():
    rows=json.loads(P.read_text(encoding='utf-8'))['records']
    assert len(rows)==19
    assert {r['university'] for r in rows}=={'한양대학교','서울시립대학교','숙명여자대학교','이화여자대학교'}
    assert all(r['year']==2025 and r['official_full_conversion_verified'] is False
       and r['source_url'].startswith('https://www.adiga.kr/') for r in rows)
    assert all(abs(sum(r['weights'].values())-1)<1e-8 for r in rows)
    u=next(r for r in rows if r['university']=='서울시립대학교' and r['group']=='인문Ⅱ')
    assert u['weights']=={'korean':.35,'math':.4,'english':.15,'inquiry':.1}
    s=next(r for r in rows if r['university']=='숙명여자대학교' and r['group']=='수학과')
    assert s['weights']['math']==.5
    h=next(r for r in rows if r['university']=='한양대학교' and r['group']=='자연계열')
    assert '100%' in h['notes']
