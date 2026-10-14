"""공개 자료 출처/범위와 민감정보 혼입을 CI에서 검사하고 JSON 리포트 작성."""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS={'data/private', 'data/raw'}
FORBIDDEN_SUFFIXES={'.sqlite3','.db','.pkl','.joblib'}


def assert_no_sensitive_files():
    # 현재 git tracked 파일을 검사 (작업 디렉터리에는 무시된 로컬 DB가 있을 수 있음)
    if (ROOT / '.git').exists():
        result=subprocess.run(['git','ls-files','-z'],cwd=ROOT,check=True,capture_output=True)
        paths=[Path(x.decode()) for x in result.stdout.split(b'\0') if x]
    else:
        paths=[p.relative_to(ROOT) for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts]
    bad=[]
    for path in paths:
        rel=path.as_posix()
        if any(rel.startswith(part+'/') for part in FORBIDDEN_PARTS) or path.suffix in FORBIDDEN_SUFFIXES:
            bad.append(rel)
        if rel.endswith('outcomes_template.csv'):
            continue
        if rel.endswith('actual_applications.csv'):
            bad.append(rel)
    if bad:
        raise ValueError('공개 Git 저장소에 개인자료/DB 파일이 포함됐습니다: '+', '.join(sorted(set(bad))))


def run():
    assert_no_sensitive_files()
    with tempfile.TemporaryDirectory() as d:
        os.environ['ADMISSION_DB']=str(Path(d)/'audit.sqlite3')
        from app import database
        database.DB=Path(os.environ['ADMISSION_DB'])
        from scripts.public_data import load
        from app.main import meta
        files=load(); coverage=meta()
    total=sum(x['program_count'] for x in coverage['program_coverage'])
    from scripts.source_inventory import build_report
    inventory=build_report()
    report={'official_source_release_pages':inventory['release_pages_found'],
            'official_imported_distributions':inventory['imported_distribution_groups'],
            'status':'ok','public_csv_files':[x.name for x in files],
            'verified_formula_count':total,
            'yearly_coverage':coverage['program_coverage'],
            'actual_outcomes_in_public_snapshot':0,
            'note':'입시 자료의 최신화 여부를 네트워크에서 검증한 것은 아닙니다.'}
    # Report 2022-26 yearly university-formula coverage separately from current-year forecast.
    report['historical_formula_coverage']={
        str(record['year']):record['program_count']
        for record in report['yearly_coverage'] if 2022<=record['year']<=2026}
    report['2027_verified_formula_count']=next(
        record['program_count'] for record in report['yearly_coverage'] if record['year']==2027)
    model_path=ROOT/'data'/'public'/'models'/'historical-2027.json'
    report['verified_historical_model_published']=model_path.is_file()
    if model_path.is_file():
        model=json.loads(model_path.read_text(encoding='utf-8'))
        report['verified_historical_model_major_count']=model.get('coverage',{}).get('trained_programs',0)
    else:
        report['verified_historical_model_major_count']=0
    from pathlib import Path as _Path
    verified_partial=_Path(__file__).resolve().parents[1]/'data/public/university_research/2026_verified_partial_formulas.json'
    if verified_partial.exists():
        partial=json.loads(verified_partial.read_text(encoding='utf-8'))
        if any(row.get('complete_formula_approved') is not False or not row.get('source_url') for row in partial):
            raise ValueError('Partial ratio list must never masquerade as complete scoring formula')
        report['verified_2026_partial_weight_groups']=len(partial)
    from scripts.national_research_scope import summary as national_research_summary
    report['national_research_scope']=national_research_summary()
    # Aggregate research counts are private-training coverage, never public 2027 outcomes.
    from pathlib import Path as _P
    rroot=_P(__file__).resolve().parents[1]
    weights=[
      'data/public/university_research/khu_2024_2025_weights.json',
      'data/public/university_research/2026_verified_partial_formulas.json',
      'data/public/university_research/2026_konkuk_sejong_partial.json',
      'data/public/university_research/2026_sogang_inha_hufs_partial.json',
      'data/public/university_research/2026_six_more_universities.json'
    ]
    group_count=0
    for relative in weights:
        entry=json.loads((rroot/relative).read_text(encoding='utf-8'))
        items=entry if isinstance(entry,list) else entry['records'] if 'records' in entry else entry['groups']
        if not all(x.get('year') in range(2022,2027) and x.get('source_url','').startswith('https://') for x in items):
            raise ValueError('unreviewed historical partial weight row')
        group_count+=len(items)
    with (rroot/'data/public/historical_admissions/konkuk_2025_70pct_cuts.json').open(encoding='utf-8') as f:
        ku=json.load(f)
    if not all(x.get('probability_label_eligible') is False for x in ku):
        raise ValueError('final enrollee 70% cuts are NOT training labels')
    report['historical_research_verified_partial_weight_groups']=group_count
    report['historical_research_non_KHU_70pct_cut_count']=len(ku)
    from scripts.historical_sources import summary as historical_source_summary
    report['historical_official_research']=historical_source_summary()
    from scripts.precompute import load_boundaries
    bundles, boundary_files = load_boundaries()
    report['grade_cut_bundle_count'] = len(bundles)
    report['grade_cut_csv_files'] = boundary_files
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='audit-report.json')
    args=parser.parse_args()
    report=run()
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
