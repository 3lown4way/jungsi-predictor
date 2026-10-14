"""2025 Soongsil historical official enrolled cutoffs are not admission outcomes."""
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/public/historical_admissions/soongsil_2025_70pct_cuts.json"


def test_real_2025_soongsil_general_cutoff_values_from_adiga():
    entries=json.loads(P.read_text(encoding='utf-8'))
    assert len(entries)==42
    assert {r["admission_round"] for r in entries}=={'가','나','다'}
    assert sum(r['admission_round']=='가' for r in entries)==22
    assert sum(r['admission_round']=='나' for r in entries)==4
    assert sum(r['admission_round']=='다' for r in entries)==16
    assert len({r['department'] for r in entries})==42
    assert all(r['year']==2025 and r['university']=='숭실대학교'
      and r['selection_type']=='정시 일반전형' and r['score_scale']==1000
      and r['probability_label_eligible'] is False
      and r['reference_type']=='final_enrollee_70_percentile_university_total'
      and r['source_report_academic_year']==2026
      and r['source_result_academic_year']==2025 and r['source_url'].startswith('https://www.adiga.kr/')
      for r in entries)
    index={r['department']:r for r in entries}
    assert (index['정보보호학과']['final_enrollee_70pct_converted_score'],
      index['정보보호학과']['published_final_recruitment'])==(943.40,8)
    assert (index['자유전공학부(자연)']['final_enrollee_70pct_converted_score'],
      index['자유전공학부(자연)']['published_final_recruitment'])==(911.36,230)
    assert index['경영학부']['final_enrollee_70pct_converted_score']==898.89
