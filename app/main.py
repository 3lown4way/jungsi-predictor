from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional
import csv
import io
import os
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from .database import connect, init_database
from .scoring import compute
from .ml import as_rows, backtest, predict_probability
from .scope import in_scope, scope_payload, medical_field

STATIC = Path(__file__).parent / 'static'

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield

app = FastAPI(title='수능 정시 합격 예측 연구실', version='0.3.0', lifespan=lifespan)
# GitHub Pages가 별도 호스팅한 FastAPI에 접속할 때만 허용할 출처를 명시합니다.
allowed_origins=[x.strip() for x in os.environ.get('ADMISSION_ALLOWED_ORIGINS','').split(',') if x.strip()]
if allowed_origins:
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins,
                       allow_methods=['GET','POST'], allow_headers=['Content-Type'],
                       allow_credentials=False)
app.mount('/static', StaticFiles(directory=str(STATIC)), name='static')

@app.get('/', include_in_schema=False)
def home():
    return FileResponse(STATIC / 'index.html')

class Inquiry(BaseModel):
    name: str = ''
    kind: Literal['social','science','vocational']
    pct: float = Field(ge=0, le=100)

class Student(BaseModel):
    year: int = Field(ge=2022,le=2027)
    exam_type: Literal['june','september','csat']
    korean_pct: float = Field(ge=0,le=100)
    korean_std: Optional[float] = Field(default=None,ge=0,le=250)
    math_pct: float = Field(ge=0,le=100)
    math_std: Optional[float] = Field(default=None,ge=0,le=250)
    math_track: Literal['probability','calculus','geometry']
    english_grade: int = Field(ge=1,le=9)
    history_grade: int = Field(ge=1,le=9)
    inquiries: list[Inquiry] = Field(min_length=1,max_length=2)

def scope_programs(connection, year=None):
    """공식 산식이 없더라도 모집단위 메타데이터는 유지, 범위 밖은 사용자 결과에서 제외."""
    if year is None:
        records = connection.execute('SELECT * FROM programs').fetchall()
    else:
        records = connection.execute('SELECT * FROM programs WHERE year=?', (year,)).fetchall()
    return [dict(r) for r in records if in_scope(dict(r))]


def scope_outcomes(connection):
    """분석 범위에 포함되는 모집단위에 실제 지원한 관측치만 사용."""
    pairs={(p['year'], p['program_key']) for p in scope_programs(connection)}
    return [r for r in as_rows(connection) if (r['year'], r['program_key']) in pairs]


@app.get('/api/scope')
def scope():
    with connect() as c:
        records=scope_programs(c)
    return {**scope_payload(), 'registered_program_years':len(records),
            'registered_universities':sorted({p['university'] for p in records}),
            'medical_fields_registered':sorted({medical_field(p) for p in records if medical_field(p)})}


@app.get('/api/meta')
def meta():
    with connect() as c:
        records=scope_programs(c)
        coverage=[]
        for year in range(2022,2028):
            rows=[p for p in records if p['year']==year]
            coverage.append({'year':year, 'program_count':sum(bool(p['formula_id']) for p in rows),
                             'registered_programs':len(rows),
                             'cutoff_count':sum(p['cutoff_70'] is not None for p in rows)})
        n=len(scope_outcomes(c))
        legacy=c.execute('SELECT count(*) FROM programs').fetchone()[0]-len(records)
    return {'supported_years':list(range(2022,2028)), 'program_coverage':coverage,
            'application_outcomes':n, 'ml_ready':False if n==0 else None,
            'scope':scope_payload(), 'outside_scope_legacy_examples':legacy,
            'notice':'의치한약수 + 주요 일반대학 20곳만 표시합니다. 기존 범위 밖 검증용 기록은 보존하되 예측 결과에서 제외합니다.',
            'sources':[
            {'label':'교육부 2026학년도 수능 채점', 'url':'https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=294&boardSeq=104758&lev=0&m=020402'},
            {'label':'교육부 2027학년도 9월 모평 채점','url':'https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=294&boardSeq=107307&lev=0&m=020402'},
            {'label':'어디가 2025학년도 상명대 정시 산식 [범위 밖 계산기 검증]', 'url':'https://www.adiga.kr/ucp/uvt/uni/univDetailSelection.do?menuId=PCUVTINF2000&searchSyr=2025&unvCd=0000117'},
            {'label':'어디가 2026학년도 상명대 산식·2025학년도 70%컷 [범위 밖]', 'url':'https://www.adiga.kr/ucp/uvt/uni/univDetailSelection.do?menuId=PCUVTINF2000&searchSyr=2026&unvCd=0000117'}]}


@app.get('/api/programs')
def programs(year: Optional[int] = Query(default=None,ge=2022,le=2027)):
    with connect() as c:
        rs=scope_programs(c,year)
    return sorted(rs, key=lambda r:(r['year'],r['university'],r['department']))


@app.get('/api/examples/programs', summary='범위 밖의 과거 산식 검증용 예제; 실제 추천 결과 아님')
def examples():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM programs WHERE university='상명대학교' ORDER BY year, department")]


@app.post('/api/calculate')
def calculate(s: Student):
    raw=s.model_dump()
    with connect() as c:
        candidates = scope_programs(c, s.year)
        outcomes=scope_outcomes(c)
    rows=[]
    for p in candidates:
        scored=compute(raw,p)
        if scored is None:
            rows.append({**p,'status':'rule_missing','message':'공식 연도별 반영식 미등록','score':None})
            continue
        # 학년도 같은 70%컷만 비교. 이전 학년도 점수는 섞지 않는다.
        margin = (round(scored.total-p['cutoff_70'],3)
                  if p['cutoff_70'] is not None and
                     p['cutoff_kind']=='final_enrollee_70pct_univ_total' and
                     s.exam_type == 'csat' else None)
        ref_status=('same_year_hindsight_reference' if margin is not None else 'no_same_year_cutoff')
        ml_input = dict(korean_pct=s.korean_pct,math_pct=s.math_pct,
            inquiry1_pct=s.inquiries[0].pct,
            inquiry2_pct=s.inquiries[1].pct if len(s.inquiries)>1 else s.inquiries[0].pct,
            english_grade=s.english_grade, math_track=s.math_track,
            quota=p['quota'], admission_round=p['round'],
            math_weight=0.35 if p['track']=='natural' else 0.25)
        # 모의평가는 같은 학년도 수능의 확정 합격 여부가 아니다.
        # 개별 지원 모델에도 정원 및 공식 반영 비율이 필요하다.
        probability, reason = (predict_probability(outcomes,s.year,p['program_key'],ml_input)
              if s.exam_type=='csat' else (None,'모평 점수의 수능 변환 모델이 미검증되어 합격 확률 제공 불가'))
        rows.append({**p,'status':ref_status,'message':reason, 'score':scored.total,
                     'breakdown':scored.breakdown,'score_scale':scored.score_scale,
                     'margin':margin, 'probability':probability})
    rows.sort(key=lambda r:(r.get('score') is None, r['university'], r['department']))
    return {'year':s.year,'exam_type':s.exam_type,'count':len(rows),'results':rows,
        'warning':'70% 컷 이상도 합격 보장 아님. 모의고사 점수를 수능 결과와 동일하게 해석할 수 없음.'}

@app.get('/api/backtest')
def bt():
    with connect() as c:
        records=scope_outcomes(c)
    return {'count':len(records),'method':'연도 순행 검증: 과거 학년도로 학습하고 해당 연도는 미리 보지 않고 평가',
            'evaluations':backtest(records),
            'disclaimer':'0개인 경우 검증 불가. 70%컷은 개별 지원자 합불 라벨이 아니다.'}

REQUIRED = ['year','program_key','applicant_hash','korean_pct','math_pct',
            'inquiry1_pct','inquiry2_pct','english_grade','math_track','quota','admission_round','math_weight','admitted',
            'applied','consented','verified','source_url']

@app.post('/api/import/outcomes')
async def import_outcomes(file: UploadFile = File(...), admin_token: str=Form(...)):
    configured=os.environ.get('ADMISSION_ADMIN_TOKEN')
    if not configured or admin_token != configured:
        raise HTTPException(403,'환경변수 ADMISSION_ADMIN_TOKEN 설정과 일치하는 인증키가 필요합니다.')
    content=await file.read()
    if len(content)>3_000_000:
        raise HTTPException(413,'CSV 파일은 3MB 이하여야 합니다.')
    try:
        reader=csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
        if not reader.fieldnames or any(k not in reader.fieldnames for k in REQUIRED):
            raise ValueError('필수열 누락: '+', '.join(k for k in REQUIRED if k not in (reader.fieldnames or [])))
        entries=[]
        for idx,r in enumerate(reader, start=2):
            year=int(r['year'])
            if year<2022 or year>2026: raise ValueError(f'{idx}행: 2027년 미래 합격자료 허용하지 않음')
            if any(r[k] not in ('1','true','TRUE') for k in ('applied','consented','verified')):
                raise ValueError(f'{idx}행: 실제 지원·동의·확인이 모두 필요')
            if r['admitted'] not in ('0','1'): raise ValueError(f'{idx}행: 합격여부는 0 또는 1')
            values=[float(r[k]) for k in ('korean_pct','math_pct','inquiry1_pct','inquiry2_pct')]
            if not all(0<=v<=100 for v in values):raise ValueError(f'{idx}행: 백분위 범위')
            eg=int(r['english_grade'])
            if eg<1 or eg>9:raise ValueError(f'{idx}행: 영어등급 범위')
            if r['math_track'] not in ('probability','calculus','geometry'):raise ValueError(f'{idx}행: 수학 선택과목 오류')
            quota=int(r['quota']); math_weight=float(r['math_weight'])
            if not (quota>0 and 0<=math_weight<=1):raise ValueError(f'{idx}행: 정원 또는 수학 반영 비율 오류')
            if r['admission_round'] not in ('가','나','다'):raise ValueError(f'{idx}행: 모집군 오류')
            if len(r['applicant_hash'])<16 or not r['source_url'].strip():raise ValueError(f'{idx}행: 비식별화 키 또는 출처 없음')
            entries.append((year,r['program_key'],r['applicant_hash'],*values,eg,r['math_track'],
                            quota,r['admission_round'],math_weight,int(r['admitted']),1,1,1,r['source_url']))
            if len(entries)>15000:raise ValueError('단일 업로드 15,000건 제한')
        if not entries:raise ValueError('입력 행이 없습니다')
    except (ValueError,TypeError,UnicodeDecodeError) as e:
        raise HTTPException(422,str(e))
    with connect() as c:
        allowed={(p['year'],p['program_key']) for p in scope_programs(c)}
        rejected=[(e[0],e[1]) for e in entries if (e[0],e[1]) not in allowed]
        if rejected:
            raise HTTPException(422, f'분석 범위에 등록된 정시 일반전형 모집단위만 입력할 수 있습니다: {rejected[:3]}')
        # 트랜잭션 단위로 모두 저장하거나 모두 취소.
        c.executemany('''INSERT INTO actual_applications
          (year,program_key,applicant_hash,korean_pct,math_pct,inquiry1_pct,inquiry2_pct,
           english_grade,math_track,quota,admission_round,math_weight,admitted,applied,consented,verified,source_url)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',entries)
        c.execute('INSERT INTO import_log(imported_at,category,row_count,source) VALUES(?,?,?,?)',
                  (datetime.now(timezone.utc).isoformat(),'outcomes',len(entries),file.filename or 'upload'))
    return {'imported':len(entries),'note':'제출자가 확인했다고 표시한 데이터입니다. 원본 증빙의 별도 검증이 필요합니다.'}
