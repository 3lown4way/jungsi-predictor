"""공개 정적 스냅샷 빌드. 사용: python -m scripts.build_pages --output site

GitHub Pages는 FastAPI를 실행하지 않는다. 공식 공개 모집단위 스냅샷만 배포하며
실측 지원자 자료와 모델 파일은 애초에 읽지 않는다.
"""
import argparse
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def run(output: Path, api_base_url: str = ''):
    if api_base_url and not re.fullmatch(r'https://[^/\s]+(?:/[^\s]*)?', api_base_url):
        raise ValueError('PUBLIC_API_BASE_URL은 공개 HTTPS URL이어야 합니다.')
    # 외부 환경변수/로컬 DB를 강제로 무시하여 고객 개인 DB 게시 위험 차단.
    with tempfile.TemporaryDirectory(prefix='admission-pages-') as working:
        os.environ['ADMISSION_DB'] = str(Path(working) / 'public.sqlite3')
        from app import database
        database.DB = Path(os.environ['ADMISSION_DB'])
        from scripts.public_data import load
        from fastapi.testclient import TestClient
        from app.main import app
        imported = load()
        output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / 'app' / 'static', output / 'static', dirs_exist_ok=True)
        (output / 'static' / 'outcomes_template.csv').unlink(missing_ok=True)
        page = (ROOT / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')
        page = page.replace('/static/', './static/')
        page = page.replace('RESEARCH BUILD · v0.4', 'GITHUB ACTIONS · v0.4')
        page = page.replace('href="./static/outcomes_template.csv"', 'href="./static/outcomes_template.csv"')
        (output / 'index.html').write_text(page, encoding='utf-8')
        (output / '.nojekyll').write_text('', encoding='utf-8')
        config = {'staticMode': True, 'apiBaseUrl': api_base_url.rstrip('/')}
        (output / 'static' / 'config.js').write_text('window.ADMISSION_SITE_CONFIG = '+json.dumps(config, ensure_ascii=False)+';\n', encoding='utf-8')
        data_dir = output / 'data'; data_dir.mkdir(exist_ok=True)
        with TestClient(app) as client:
            response = client.get('/api/programs', params={'year': 2027})
            response.raise_for_status()
            write_json(data_dir / 'programs-2027.json', response.json())
        from app.scope import TOP_20, MEDICAL_FIELDS
        write_json(data_dir / 'targets-2027.json', {'year':2027,
            'universities':list(TOP_20), 'medical_fields':MEDICAL_FIELDS,
            'status_note':'대상 대학 명단은 공식 반영식·합격확률 확보를 의미하지 않습니다.'})
        # No grade-boundary admission scenarios: individual report-card scores are the input.
        from app.database import connect
        from app.weighted_rules import read_conversion_tables, validate_spec
        with connect() as con:
            programs=[dict(p) for p in con.execute('SELECT * FROM programs WHERE year=2027')]
        verified_rules=[]
        lookups=read_conversion_tables()
        for p in programs:
            if p['formula_id']!='weighted_official_v1' or not p.get('formula_config_json'):
                continue
            if not (p.get('formula_source_url') or '').startswith('https://'):
                continue
            spec=validate_spec(json.loads(p['formula_config_json']),p)
            table_ids={v['table_id'] for v in spec['components'].values()
                       if v['metric']=='converted_std'}
            tables=[{'table_id':key[2], 'subject':key[3], 'std_score':key[4],
                     'converted_score':value}
                    for key,value in sorted(lookups.items())
                    if key[0]==2027 and key[1]==p['university'] and key[2] in table_ids]
            verified_rules.append({
                'program_key':p['program_key'], 'university':p['university'],
                'source_url':p['formula_source_url'],'spec':spec,'tables':tables
            })
        write_json(data_dir/'scoring-rules-2027.json',{
            'year':2027,'exam_type':'september','formula_count':len(verified_rules),
            'rules':verified_rules,'note':'공식 원문 검수한 대학별 환산식. 합격확률 ML 모델 아님.'
        })
        from scripts.score_adjustment import make_snapshot, read_frequencies
        snapshot=make_snapshot()
        # Publish 2027 reference curves only, not historical score distributions or backtests.
        write_json(data_dir / 'score-adjustment.json', {
            'reference_year':2027, 'ready_subject_count':snapshot['ready_subject_count'],
            'subjects':[{k:v for k,v in row.items() if k not in ('historical_pairs',)}
                        for row in snapshot['subjects']],
            'note':'2022~2026학년도 자료는 학습·검증에만 사용하며 별도 공개하지 않습니다.'
        })
        distributions,_=read_frequencies()
        subjects=[]
        for (year,exam,subject,option),dist in sorted(distributions.items()):
            if (year,exam)!=(2027,'september'):
                continue
            bins=[{'score':s,'count':n} for s,n in sorted(dist.frequencies.items())]
            subjects.append({'subject':subject,'option_name':option,'total':dist.total,
                'max_score':max(dist.frequencies),'max_score_count':dist.frequencies[max(dist.frequencies)],
                'bins':bins,'source_url':dist.source_urls[0]})
        write_json(data_dir / 'score-distribution-2027.json', {'year':2027,
            'exam_type':'september','subject_count':len(subjects),'subjects':subjects,
            'note':'2027학년도 9월 모의평가 표준점수별 응시 인원 공식 도수분포'})
        from scripts.source_inventory import build_report
        report=build_report()
        current=next(r for r in report['entries'] if r['year']==2027 and r['exam_type']=='september')
        write_json(data_dir / 'official-source-status.json', {
            'year':2027,'exam_type':'september','source_page':current['source_page'],
            'subject_count':len(subjects),'numeric_data_imported':current['numeric_data_imported'],
            'warning':'사용자 제공 엑셀의 누적·합계 검사 완료. 교육부 첨부 파일과 바이트 동일성 미확인.'
        })
        # Publish only already privacy-gated, non-identifying aggregate snapshots.
        snapshot_file = ROOT / 'data' / 'public' / 'snapshots' / '2027-september.json'
        if snapshot_file.is_file():
            snapshot = json.loads(snapshot_file.read_text(encoding='utf-8'))
            if snapshot.get('privacy_threshold', 0) < 30 or snapshot.get('year') != 2027:
                raise ValueError('invalid public cohort privacy gate')
            write_json(data_dir / 'cohort-snapshot.json', snapshot)
        else:
            write_json(data_dir / 'cohort-snapshot.json', {
                'schema_version': '1.0', 'year': 2027, 'exam_type': 'september',
                'snapshot_mode': 'offline_github_actions', 'published_programs': 0,
                'predictions': [], 'message': 'No published cohort snapshot yet'
            })
        # Partially verified rules are metadata, not complete score calculators.
        partial_path=ROOT/'data'/'public'/'university_research'/'2027.json'
        partial_registry=json.loads(partial_path.read_text(encoding='utf-8')) if partial_path.exists() else []
        partial_by_key={r['program_key']:r for r in partial_registry}
        # The individual inputs are entered locally by the user. No grade-level profiles.
        # Only trained and calibrated curves could provide a probability for that score,
        # and none is currently available. Never publish a single unconditional probability.
        from app.scope import in_scope, medical_field
        cohort_by_key={p['program_key']:p for p in snapshot.get('predictions',[])}
        approved_keys={r['program_key'] for r in verified_rules}
        overview=[]
        for p in programs:
            if not in_scope(p):
                continue
            cohort=cohort_by_key.get(p['program_key'],{})
            overview.append({
                'year':2027,'program_key':p['program_key'],
                'university':p['university'],'department':p['department'],
                'campus':p['campus'],'track':p['track'],'admission_round':p['round'],
                'quota':p['quota'],'medical_field':medical_field(p),
                'formula_source_url':p['formula_source_url'],
                'verified_partial_rule':partial_by_key.get(p['program_key']),
                'formula_verified':p['program_key'] in approved_keys,
                'cohort_count_band':cohort.get('participant_count_band'),
                'cohort_score_p25':cohort.get('score_p25'),
                'cohort_score_p50':cohort.get('score_p50'),
                'cohort_score_p75':cohort.get('score_p75'),
                'probability_curve':None,
                'status':'rule_registered' if p['program_key'] in approved_keys else 'formula_unavailable',
            })
        write_json(data_dir/'admissions-outlook-2027.json',{
            'schema_version':'2.0','year':2027,'exam_type':'september',
            'input_mode':'individual_official_report_card_scores',
            'program_count':len(overview),'score_ready_count':len(verified_rules),
            'probability_ready_count':0,'programs':overview,
            'warning':'공식 점수 기반 대학별 환산. 2027 예측확률 검증 전에는 퍼센트를 출력하지 않음.'
        })
        write_json(data_dir / 'build-info.json', {
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'imported_public_csv_count': len(imported),
            'note': '자동 모니터링이 공식 입시 자료의 갱신이나 실측 합불 학습을 의미하지 않습니다.',
            'live_api_configured': bool(api_base_url)
        })
    return output


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='site')
    parser.add_argument('--api-base-url',default=os.environ.get('PUBLIC_API_BASE_URL',''))
    args=parser.parse_args()
    print('정적 사이트 생성:',run(Path(args.output), args.api_base_url))
