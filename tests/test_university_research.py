"""Academic-year-specific university metadata cannot be mistaken for complete scoring formulas."""
import json
from pathlib import Path
from app.scope import in_scope,medical_field

ROOT=Path(__file__).resolve().parents[1]

def test_first_2027_official_metadata_records_are_not_complete_predictions():
    from scripts.build_pages import run
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as t:
        site=run(Path(t)/'pages')
        rows=json.loads((site/'data'/'admissions-outlook-2027.json').read_text())['programs']
        assert len(rows)==8
        assert all(row['status']=='formula_unavailable' for row in rows)
        assert all(row['probability_curve'] is None for row in rows)
        assert sum(bool(row['verified_partial_rule']) for row in rows)==5
        for row in rows:
            if row['verified_partial_rule']:
                assert sum(row['verified_partial_rule']['weights'].values())==1
            assert row['formula_source_url'].startswith('https://')
        candidates={r['program_key']:r for r in rows}
        assert candidates['snu-materials']['quota']==36
        assert candidates['snu-chem-bio']['quota']==31
        assert candidates['snu-biosystems']['quota']==18

def test_scoring_formula_is_required_before_arithmetic():
    from app.scoring import compute
    row={'year':2027,'program_key':'khu-medicine','university':'경희대학교',
         'department':'의예과','track':'natural','formula_id':None}
    assert in_scope(row)
    assert medical_field(row)=='medicine'
    assert compute({},row) is None
