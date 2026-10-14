"""공식 자료를 직접 검수해 정리한 학년도/모집단위별 CSV 적재.

usage:
  python -m tools.import_programs data/programs_template.csv

산식이 없으면 계산하지 않음. 출처와 학년도가 검수되지 않은 데이터를 넣지 않음.
"""
import argparse
import csv
import json
from app.weighted_rules import validate_spec
from datetime import date
from app.database import connect, init_database

FIELDS=['year','program_key','university','campus','department','track','round',
        'quota','formula_id','formula_source_url','cutoff_70','cutoff_source_url',
        'cutoff_kind','last_verified']
SUPPORTED_FORMULA={'sangmyung_pct_2025_2026','weighted_official_v1','soongsil_2025_csat_v1'}


def run(path):
    init_database()
    prepared=[]
    with open(path,'r',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or set(FIELDS)-set(reader.fieldnames):
            raise ValueError('프로그램 CSV의 필수 열이 없습니다.')
        for lineno,row in enumerate(reader,2):
            year=int(row['year'])
            if year not in range(2022,2028):raise ValueError(f'{lineno}행 학년도 오류')
            if row['track'] not in ('natural','humanities'):raise ValueError(f'{lineno}행 지원하지 않는 계열')
            if row['round'] not in ('가','나','다',''):raise ValueError(f'{lineno}행 모집군 오류')
            formula=row['formula_id'] or None
            if formula and not row['round']:
                raise ValueError(f'{lineno}행 산식 등록 때에는 모집군 검증 필요')
            if not formula and not (row['formula_source_url'] or '').startswith('https://'):
                raise ValueError(f'{lineno}행 공식 모집단위 자료 출처 필요')
            if formula is not None:
                if formula not in SUPPORTED_FORMULA or (formula=='sangmyung_pct_2025_2026' and year not in (2025,2026)) or (formula=='soongsil_2025_csat_v1' and (year!=2025 or row['university']!='숭실대학교')):
                    raise ValueError(f'{lineno}행: 아직 미검증 반영식을 사용하려는 시도')
                if not row['formula_source_url'].startswith('https://'):
                    raise ValueError(f'{lineno}행: 산식의 공식 출처 주소 필요')
            spec_raw = (row.get('formula_config_json') or '').strip()
            if formula == 'weighted_official_v1':
                if not spec_raw:raise ValueError(f'{lineno}행: 해당 학년도·모집단위 환산 규칙 누락')
                validate_spec(json.loads(spec_raw), dict(year=year,university=row['university'],program_key=row['program_key']))
            elif spec_raw:
                raise ValueError(f'{lineno}행: 해당 산식에는 별도 설정 허용하지 않음')
            cutoff=float(row['cutoff_70']) if row['cutoff_70'] else None
            if cutoff is not None:
                if row['cutoff_kind'] != 'final_enrollee_70pct_univ_total':
                    raise ValueError(f'{lineno}행: 현재는 대학환산 총점 70%컷만 지원')
                if not row['cutoff_source_url'].startswith('https://'):
                    raise ValueError(f'{lineno}행: 컷 공식 출처 주소 필요')
            if not row['program_key'] or not row['university'] or not row['department']:
                raise ValueError(f'{lineno}행: 대학/학과 정보 누락')
            date.fromisoformat(row['last_verified'])
            quota=int(row['quota']) if row['quota'] else None
            if quota is not None and quota<=0:raise ValueError(f'{lineno}행: 모집 정원 오류')
            prepared.append((year,row['program_key'],row['university'],row['campus'],
                            row['department'],row['track'],row['round'],quota,formula,
                            row['formula_source_url'] or None,cutoff,
                            row['cutoff_source_url'] or None,row['cutoff_kind'] or None,
                            row['last_verified'], spec_raw or None))
    if not prepared:
        print('적재할 행 없음');return
    with connect() as c:
        c.executemany('''INSERT INTO programs
         (year,program_key,university,campus,department,track,round,quota,formula_id,
          formula_source_url,cutoff_70,cutoff_source_url,cutoff_kind,last_verified,formula_config_json)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(year,program_key) DO UPDATE SET
          university=excluded.university,campus=excluded.campus,department=excluded.department,
          track=excluded.track,round=excluded.round,quota=excluded.quota,
          formula_id=excluded.formula_id,formula_source_url=excluded.formula_source_url,
          cutoff_70=excluded.cutoff_70,cutoff_source_url=excluded.cutoff_source_url,
          cutoff_kind=excluded.cutoff_kind,last_verified=excluded.last_verified,
          formula_config_json=excluded.formula_config_json''',prepared)
    print(f'공식 출처 검토 후 준비한 {len(prepared)}개 모집단위 데이터를 등록했습니다.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('path',help='사전 검수된 프로그램 CSV')
    args=parser.parse_args()
    run(args.path)
