import json
import pytest
from pathlib import Path
from scripts.historical_sources import read_historical_catalog,read_historical_cuts,summary

def test_2022_2026_official_sources_are_specific_to_year_and_university():
    rows=read_historical_catalog()
    assert len(rows)==10
    assert {(r['year'],r['university']) for r in rows}=={
        (y,uni) for y in range(2022,2027) for uni in ('서울대학교','경희대학교')}
    assert all(not r['complete_formula_approved'] for r in rows)
    assert next(r for r in rows if r['year']==2022 and r['university']=='서울대학교')['relative_weights'] is None
    assert sum(r.get('relative_weights') is not None for r in rows)==4

def test_verified_medical_70pct_cuts_not_confused_with_labeled_admissions():
    cuts=read_historical_cuts()
    assert len(cuts)==15
    assert {row['year'] for row in cuts}=={2022,2024,2025}
    assert all(row['score_scale']==800 and not row['probability_label_eligible'] for row in cuts)
    def score(y,d):return next(r['final_enrollee_70pct_converted_score'] for r in cuts if r['year']==y and r['department']==d)
    assert score(2022,'의예과')==609.74
    assert score(2024,'의예과')==600.80
    assert score(2025,'의예과')==595.35
    assert summary()['cutoffs_usable_as_individual_outcomes']==0

def test_missing_year_does_not_get_filled_in(tmp_path):
    sources=read_historical_catalog()
    p=tmp_path/'incomplete.json'
    p.write_text(json.dumps(sources[:-1],ensure_ascii=False),encoding='utf-8')
    with pytest.raises(ValueError,match='missing historical source'):
        read_historical_catalog(p)

def test_cannot_reinterpret_70_cut_as_admitted_person(tmp_path):
    cuts=read_historical_cuts()
    cuts[0]['probability_label_eligible']=True
    p=tmp_path/'spoofed.json';p.write_text(json.dumps(cuts,ensure_ascii=False),encoding='utf-8')
    with pytest.raises(ValueError,match='cutoff is not'):
        read_historical_cuts(p)
