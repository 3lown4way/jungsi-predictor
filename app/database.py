import sqlite3
import os
from pathlib import Path

DB = Path(os.environ.get('ADMISSION_DB', str(Path(__file__).resolve().parents[1] / 'data' / 'admission.sqlite3')))
SCHEMA = '''
CREATE TABLE IF NOT EXISTS programs (
 year INTEGER NOT NULL CHECK(year BETWEEN 2022 AND 2035),
 program_key TEXT NOT NULL,
 university TEXT NOT NULL,
 campus TEXT NOT NULL,
 department TEXT NOT NULL,
 track TEXT NOT NULL,
 round TEXT NOT NULL,
 quota INTEGER,
 formula_id TEXT,
 formula_source_url TEXT,
 formula_config_json TEXT,
 cutoff_70 REAL,
 cutoff_source_url TEXT,
 cutoff_kind TEXT,
 last_verified TEXT NOT NULL,
 medical_field TEXT NOT NULL DEFAULT '',
 selection_type TEXT NOT NULL DEFAULT '일반',
 PRIMARY KEY(year, program_key)
);
CREATE TABLE IF NOT EXISTS exams (
 year INTEGER NOT NULL,
 exam_type TEXT NOT NULL CHECK(exam_type IN ('june','september','csat')),
 subject TEXT NOT NULL,
 option_name TEXT NOT NULL DEFAULT '',
 std_score INTEGER NOT NULL,
 examinee_count INTEGER NOT NULL,
 source_url TEXT NOT NULL,
 PRIMARY KEY(year, exam_type, subject, option_name, std_score)
);
CREATE TABLE IF NOT EXISTS actual_applications (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 year INTEGER NOT NULL CHECK(year BETWEEN 2022 AND 2026),
 program_key TEXT NOT NULL,
 applicant_hash TEXT NOT NULL,
 korean_pct REAL NOT NULL,
 math_pct REAL NOT NULL,
 inquiry1_pct REAL NOT NULL,
 inquiry2_pct REAL NOT NULL,
 english_grade INTEGER NOT NULL,
 math_track TEXT NOT NULL,
 quota INTEGER NOT NULL CHECK(quota > 0),
 admission_round TEXT NOT NULL CHECK(admission_round IN ('가','나','다')),
 math_weight REAL NOT NULL CHECK(math_weight >= 0 AND math_weight <= 1),
 admitted INTEGER NOT NULL CHECK(admitted IN (0,1)),
 applied INTEGER NOT NULL CHECK(applied = 1),
 consented INTEGER NOT NULL CHECK(consented = 1),
 verified INTEGER NOT NULL CHECK(verified = 1),
 source_url TEXT NOT NULL,
 UNIQUE(year, program_key, applicant_hash)
);
CREATE TABLE IF NOT EXISTS import_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, imported_at TEXT NOT NULL,
 category TEXT NOT NULL, row_count INTEGER NOT NULL, source TEXT NOT NULL
);
'''


def connect():
    DB.parent.mkdir(exist_ok=True, parents=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con


def init_database():
    with connect() as con:
        con.executescript(SCHEMA)
        # 기존 파일을 사용한 사용자의 데이터를 보존하는 무손실 마이그레이션.
        # 과거 레코드에 모르는 규칙/정원 값을 임의로 채우지 않는다.
        columns={r['name'] for r in con.execute('PRAGMA table_info(actual_applications)')}
        for col,sqltype in [('quota','INTEGER'),('admission_round','TEXT'),('math_weight','REAL')]:
            if col not in columns:
                con.execute(f'ALTER TABLE actual_applications ADD COLUMN {col} {sqltype}')
        existing_program_columns = {r['name'] for r in con.execute('PRAGMA table_info(programs)')}
        if 'medical_field' not in existing_program_columns:
            con.execute("ALTER TABLE programs ADD COLUMN medical_field TEXT NOT NULL DEFAULT ''")
        if 'selection_type' not in existing_program_columns:
            con.execute("ALTER TABLE programs ADD COLUMN selection_type TEXT NOT NULL DEFAULT '일반'")
        if 'formula_config_json' not in existing_program_columns:
            con.execute('ALTER TABLE programs ADD COLUMN formula_config_json TEXT')
        count = con.execute('SELECT count(*) FROM programs').fetchone()[0]
        if count == 0:
            seed(con)


def seed(con):
    """공식 출처로 직접 대조한 예제만 적재. 2025컷과 2026식을 섞지 않음."""
    SOURCE_2025 = 'https://www.adiga.kr/ucp/uvt/uni/univDetailSelection.do?menuId=PCUVTINF2000&searchSyr=2025&unvCd=0000117'
    SOURCE_2026 = 'https://www.adiga.kr/ucp/uvt/uni/univDetailSelection.do?menuId=PCUVTINF2000&searchSyr=2026&unvCd=0000117'
    # 2025학년도 최종등록자 70% 컷: 2026학년도 포털의 '2025학년도 전형 결과'에서 확인.
    records = [
        ('smu-seoul-business', '경영학부', 'humanities','나',19,852.00),
        ('smu-seoul-economics', '경제금융학부','humanities','나',21,848.50),
        ('smu-seoul-education', '교육학과','humanities','나',13,846.80),
        ('smu-seoul-math-education', '수학교육과','natural','나',15,913.90),
        ('smu-seoul-cs', '컴퓨터과학전공','natural','나',32,903.40),
        ('smu-seoul-chem', '화공신소재전공','natural','나',10,878.75),
    ]
    for year in (2025, 2026):
        for key, name, track, group, quota_2025, cutoff_2025 in records:
            con.execute('''INSERT INTO programs
             (year,program_key,university,campus,department,track,round,quota,formula_id,
              formula_source_url,cutoff_70,cutoff_source_url,cutoff_kind,last_verified)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
             (year,key,'상명대학교','서울',name,track,group,
              quota_2025 if year == 2025 else None,
              'sangmyung_pct_2025_2026',
              SOURCE_2025 if year==2025 else SOURCE_2026,
              cutoff_2025 if year==2025 else None,
              SOURCE_2026 if year==2025 else None,
              'final_enrollee_70pct_univ_total' if year==2025 else None,
              '2026-10-14'))
