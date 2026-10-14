"""Verified 2026 official weight methods, separated from full final admissions score."""
from pathlib import Path
import json

P=Path(__file__).resolve().parents[1]/'data/public/university_research/2026_verified_partial_formulas.json'


def test_2026_verified_university_weight_component_catalog():
    entries=json.loads(P.read_text(encoding='utf-8'))
    assert len(entries)==7
    assert set(row['university'] for row in entries)=={'동국대학교','연세대학교','고려대학교'}
    assert all(row['year']==2026 and row['complete_formula_approved'] is False for row in entries)
    assert all(row['missing'] and row['source_url'].startswith('https://') for row in entries)
    dong=[r for r in entries if r['university']=='동국대학교']
    assert {r['group']:r['weights'] for r in dong}=={
        '인문계열':{'korean':.35,'math':.25,'english':.15,'inquiry':.25},
        '자연계열(일반)':{'korean':.25,'math':.35,'english':.15,'inquiry':.25}}
    yonsei=next(r for r in entries if r['university']=='연세대학교' and r['group']=='유형Ⅱ 의예과')
    assert (yonsei['csat_reflected_points'],yonsei['interview_component'])==(900,50)
    korea=next(r for r in entries if r['university']=='고려대학교' and r['group']=='인문계열')
    assert sum(korea['component_points'].values())==560
