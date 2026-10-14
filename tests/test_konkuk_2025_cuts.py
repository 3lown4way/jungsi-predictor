"""Historical Konkuk 2025 admission results are NOT application-level outcome labels."""
from pathlib import Path
import json
P=Path(__file__).resolve().parents[1]/'data/public/historical_admissions/konkuk_2025_70pct_cuts.json'

def test_konkuk_historical_actual_2025_final_70pct_cutoff_records():
    rows=json.loads(P.read_text(encoding='utf-8'))
    assert len(rows)==10
    assert {(r['year'],r['university']) for r in rows}=={(2025,'건국대학교')}
    assert all(r['reference_type']=='final_enrollee_70_percentile_university_total'
      and not r['probability_label_eligible']
      and r['score_scale']==1000
      and r['source_report_academic_year']==r['year']+1 for r in rows)
    vet=next(x for x in rows if x['department']=='수의예과')
    assert (vet['final_enrollee_70pct_converted_score'],vet['published_final_recruitment'],vet['admission_round'])==(703.82,39,'가')
    for r in rows:
       assert 0<=r['final_enrollee_70pct_converted_score']<=r['score_scale']
       assert r['published_final_recruitment']>0
