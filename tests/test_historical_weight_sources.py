import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_official_historical_weight_ratios_change_by_year_without_becoming_scores():
    rows=json.loads((ROOT/'data/public/university_research/khu_2024_2025_weights.json').read_text(encoding='utf-8'))
    assert len(rows)==4
    for r in rows:
        assert r['university']=='경희대학교'
        assert sum(r['weights'].values())==1
        assert r['source_url'].startswith('https://iphak.khu.ac.kr/')
        assert r['status']=='official_weight_ratio_only_not_complete_scoring_formula'
        assert r['missing_for_full_score']
    mapping={(r['year'],r['group']):r['weights'] for r in rows}
    former=mapping[(2024,'oriental_medicine_humanities')]
    latter=mapping[(2025,'oriental_medicine_humanities')]
    assert former=={'korean':.25,'math':.35,'english':.15,'inquiry':.25}
    assert latter=={'korean':.35,'math':.20,'english':.15,'inquiry':.30}
    assert former!=latter
    assert mapping[(2024,'natural')]==mapping[(2025,'natural')]
