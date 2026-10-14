"""Precomputation never fabricates admissions labels from official grade boundaries."""
import csv
import json
from pathlib import Path

import pytest

from scripts import precompute


def make_boundaries(directory, *, reversed_order=False):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'official.csv'
    with path.open('w', encoding='utf-8', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=sorted(precompute.COLUMNS))
        writer.writeheader()
        for area, name, kind, track in [('korean','언어와매체','',''),
                                        ('math','미적분','','calculus'),
                                        ('inquiry1','물리학Ⅰ','science',''),
                                        ('inquiry2','화학Ⅰ','science','')]:
            for grade in (1,2,3):
                floor = 96-8*(grade-1)
                if reversed_order and grade == 2 and area == 'korean':
                    floor = 100
                writer.writerow({'year':'2025','exam_type':'csat','bundle_id':'2025-demo-bundle',
                    'area':area,'subject':name,'grade':grade,'std_score_floor':140-10*grade,
                    'percentile_floor':floor,'kind':kind,'math_track':track,
                    'source_url':'https://example.org/verified-grade-cut'})
    return path


def sample_program():
    return {'year':2025, 'program_key':'smu-seoul-cs',
            'university':'상명대학교','department':'컴퓨터과학전공',
            'track':'natural','formula_id':'sangmyung_pct_2025_2026',
            'formula_source_url':'https://example.org/formula',
            'cutoff_70':903.4,'cutoff_source_url':'https://example.org/70pct'}


def test_boundary_lattice_and_no_fabricated_admission_outcomes(tmp_path, monkeypatch):
    make_boundaries(tmp_path)
    monkeypatch.setattr(precompute,'in_scope',lambda p: True)
    by_year, summary=precompute.build_dataset([sample_program()],tmp_path)
    assert len(by_year[2025]) == 3**5
    assert sum(map(len,by_year.values())) == 3**5
    assert summary['bundle_count'] == 1
    top=next(p for p in by_year[2025] if p['grade_profile']=='1-1-1-1-1')
    assert top['converted_score'] > 0
    assert top['track']=='natural'
    assert top['score_breakdown']['국어']>0
    assert top['retrospective_margin'] == round(top['converted_score']-903.4,3)
    assert top['assessment'] == 'retrospective_70pct_comparison'
    assert top['admitted'] is None and top['admission_probability'] is None
    assert top['reference']=='published_grade_lower_bound_not_typical_score'


def test_no_official_grade_cut_no_generated_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(precompute,'in_scope',lambda p: True)
    by_year,summary=precompute.build_dataset([sample_program()],tmp_path)
    assert summary['bundle_count']==0
    assert all(not rows for rows in by_year.values())


def test_reject_reversed_grade_cut(tmp_path):
    make_boundaries(tmp_path, reversed_order=True)
    with pytest.raises(ValueError,match='reversed'):
        precompute.load_boundaries(tmp_path)


def test_static_export_is_precomputed_reader_not_personal_form(tmp_path):
    from scripts.build_pages import run
    target=tmp_path/'site'
    run(target)
    html=(target/'index.html').read_text(encoding='utf-8')
    assert 'id="score-form"' not in html
    assert 'localStorage' not in (target/'static'/'app.js').read_text(encoding='utf-8')
    assert 'id="subject-select"' in html
    assert html.index('id="university"') < html.index('id="distribution"')
    assert 'id="uni-search"' in html
    assert 'id="uni-category"' in html
    assert 'href="#university"' in html
    assert 'id="filter-year"' not in html
    summary=json.loads((target/'data'/'precomputed-summary.json').read_text(encoding='utf-8'))
    assert summary['year']==2027
    assert (target/'data'/'precomputed-2027.json').is_file()
    for year in range(2022,2027):
        assert not (target/'data'/f'precomputed-{year}.json').exists()
