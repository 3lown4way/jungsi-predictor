"""Keep Konkuk/Sejong annual official percentage rules separate from full ML scores."""
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'data/public/university_research/2026_konkuk_sejong_partial.json'

def test_konkuk_sejong_2026_weights_and_missing_conversion():
    d=json.loads(P.read_text(encoding='utf-8'))
    assert d['year']==2026
    assert len(d['records'])==5
    groups={(r['university'],r['group']):r for r in d['records']}
    assert groups[('건국대학교','KU일반학생 언어중심(A)')]['weights']=={
     'korean':.4,'math':.3,'inquiry':.2,'english':.1}
    assert groups[('건국대학교','KU일반학생 수리중심(B)')]['weights']=={
     'korean':.3,'math':.4,'inquiry':.2,'english':.1}
    assert groups[('세종대학교','수능 일반 자연')]['weights']=={
     'korean':.2,'math':.35,'inquiry':.25,'english':.2}
    assert all(abs(sum(r['weights'].values())-1)<1e-8 for r in d['records'])
    assert all(r['status']=='official_partial_rule_only_not_final_conversion'
        and r['source_url'].startswith('https://www.adiga.kr/')
        and r['missing'] for r in d['records'])
