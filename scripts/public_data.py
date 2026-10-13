"""GitHub Actions에서 공개 가능한 모집단위 자료만 일시 DB에 적재.

실제 지원자의 점수/합불 CSV는 *절대로* 공개 Pages 빌드에 포함하지 않는다.
"""
from pathlib import Path
from app.database import init_database, connect
from app.scope import in_scope
from tools.import_programs import run as import_programs

PUBLIC = Path(__file__).resolve().parents[1] / 'data' / 'public' / 'programs'


def load():
    init_database()  # 공개 검산 예제 자동 적재 (추천 대상에서 제외됨)
    paths = sorted(PUBLIC.glob('*.csv'))
    for path in paths:
        import_programs(str(path))
    with connect() as con:
        all_rows = [dict(r) for r in con.execute('SELECT * FROM programs')]
    for row in all_rows:
        if row['university'] == '상명대학교':
            continue  # 공개 산식 검산용 과거 자료는 처음부터 별도로 존재
        if not in_scope(row):
            raise ValueError(f'범위 밖 모집단위는 공개용 데이터에 적재할 수 없습니다: {row["year"]} {row["university"]} {row["department"]}')
        if row['formula_id'] and not row['formula_source_url']:
            raise ValueError('환산 산식은 공식 출처가 있어야 합니다')
        if row['cutoff_70'] is not None and not row['cutoff_source_url']:
            raise ValueError('입결은 공식 출처가 있어야 합니다')
    return paths
