import os
import tempfile

# 테스트는 독립적인 빈 경로에만 DB를 생성합니다.
os.environ['ADMISSION_DB']=os.path.join(tempfile.gettempdir(),'admission_starter_api_test.sqlite3')
from fastapi.testclient import TestClient
from app.main import app

STUDENT={
    'year':2025,'exam_type':'csat','korean_pct':88,'math_pct':90,
    'math_track':'calculus','english_grade':1,'history_grade':1,
    'inquiries':[{'name':'물리학Ⅰ','kind':'science','pct':86},{'name':'화학Ⅰ','kind':'science','pct':81}]
}

def test_api_only_in_scope_and_preserves_reference_example():
    with TestClient(app) as c:
        scope=c.get('/api/scope').json()
        assert len(scope['universities'])==20
        assert len(scope['medical_categories'])==5
        assert scope['registered_program_years']==0
        resp=c.post('/api/calculate',json=STUDENT)
        assert resp.status_code==200
        assert resp.json()['results']==[]
        assert c.get('/api/programs?year=2025').json()==[]
        refs=c.get('/api/examples/programs').json()
        cs=next(r for r in refs if r['program_key']=='smu-seoul-cs' and r['year']==2025)
        assert cs['cutoff_70']==903.4
        assert c.get('/api/backtest').json()['count']==0
        meta=c.get('/api/meta').json()
        assert meta['outside_scope_legacy_examples']>=12
        assert all(x['program_count']==0 for x in meta['program_coverage'])


def test_2027_has_no_synthetic_forecast():
    with TestClient(app) as c:
        response=c.post('/api/calculate',json={**STUDENT,'year':2027,'exam_type':'september'})
        assert response.status_code==200
        assert response.json()['results']==[]

def test_no_malformatted_scores():
    with TestClient(app) as c:
        assert c.post('/api/calculate',json={**STUDENT,'math_pct':110}).status_code==422


def test_eligible_medical_row_visible_without_invented_scoring(tmp_path, monkeypatch):
    from app import database
    monkeypatch.setattr(database,'DB',tmp_path / 'scope-test.sqlite3')
    with TestClient(app) as c:
        with database.connect() as db:
            db.execute('''INSERT INTO programs
            (year, program_key, university, campus, department, track, round,
             quota, formula_id, formula_source_url, cutoff_70, cutoff_source_url,
             cutoff_kind, last_verified, medical_field)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
             (2025,'test-med-univ-2025','범위대학','본교','의예과','natural','가',
              28,None,None,None,None,None,'2026-10-14','medicine'))
        programs=c.get('/api/programs?year=2025').json()
        assert len(programs)==1
        assert programs[0]['department']=='의예과'
        result=c.post('/api/calculate',json=STUDENT).json()['results']
        assert len(result)==1
        assert result[0]['status']=='rule_missing'
        assert result[0]['score'] is None
        assert result[0]['probability'] is None if 'probability' in result[0] else True
