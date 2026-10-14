"""연도·대학·모집단위별 공식 변환표준점수/반영비율 엔진.

규칙과 변표는 공식 출처 검증 후 데이터에서만 공급합니다.
이 모듈은 타 대학의 반영비율을 추정하거나 이전 학년도를 대체 사용하지 않습니다.
"""
from __future__ import annotations
import csv
import json
from functools import lru_cache
from pathlib import Path

CONVERSION_DIR = Path(__file__).resolve().parents[1] / 'data' / 'public' / 'conversion_tables'
TABLE_COLUMNS = {'year', 'university', 'table_id', 'subject', 'std_score',
                 'converted_score', 'source_url', 'last_verified'}
COMPONENTS = ('korean', 'math', 'english', 'inquiry')
METRICS = ('pct', 'std', 'grade', 'converted_std', 'converted_pct')
PCT_TABLE_COLUMNS = {'year','university','table_id','subject','percentile','converted_score','source_url','last_verified'}


def validate_spec(spec, program):
    if not isinstance(spec, dict) or spec.get('version') != 1:
        raise ValueError('공식 환산 규칙 버전 1 필요')
    if spec.get('year') != program.get('year') or spec.get('university') != program.get('university'):
        raise ValueError('환산 규칙 학년도·대학 불일치')
    if spec.get('program_key') != program.get('program_key'):
        raise ValueError('환산 규칙 모집단위 식별자 불일치')
    weights = spec.get('weights')
    parts = spec.get('components')
    if not isinstance(weights, dict) or not isinstance(parts, dict):
        raise ValueError('반영비율/영역별 규칙 필수')
    if set(weights) != set(COMPONENTS) or set(parts) != set(COMPONENTS):
        raise ValueError('국어·수학·영어·탐구 네 영역을 명시')
    if any(type(v) not in (int,float) or v < 0 or v > 1 for v in weights.values()):
        raise ValueError('반영비율은 0~1 사이')
    if abs(sum(weights.values()) - 1) > 1e-8:
        raise ValueError('반영비율의 합은 반드시 1')
    score_scale=spec.get('score_scale')
    if type(score_scale) not in (int,float) or not 0 < score_scale <= 10000:
        raise ValueError('환산 총점 만점 명시')
    for area in COMPONENTS:
        part = parts[area]
        mode=part.get('metric') if isinstance(part,dict) else None
        if mode not in METRICS:
            raise ValueError(f'{area} 반영 방식 없음')
        if mode == 'grade' and not isinstance(part.get('grades'),dict):
            raise ValueError(f'{area} 등급별 환산표 누락')
        if mode in ('std', 'converted_std', 'converted_pct'):
            mx=part.get('max_value')
            if type(mx) not in (int,float) or mx<=0:
                raise ValueError(f'{area} 표준점수 기준 만점 누락')
        if mode in ('converted_std', 'converted_pct') and not part.get('table_id'):
            raise ValueError(f'{area} 변환표준점수표 식별자 누락')
        if area == 'inquiry' and part.get('aggregation','mean2') not in ('mean2','best1','sum2'):
            raise ValueError('탐구 반영 과목수 설정 오류')
        if 'kind_bonus_points' in part and (not isinstance(part['kind_bonus_points'],dict) or
            any(type(v) not in (int,float) or v<0 or v>25 for v in part['kind_bonus_points'].values())):
            raise ValueError('가산점 점수 설정 오류')
        for k in ('track_bonus_pct','kind_bonus_pct'):
            if k in part and (not isinstance(part[k],dict) or
                any(type(v) not in (int,float) or not -1<=v<=1 for v in part[k].values())):
                raise ValueError('가산점 비율 설정 오류')
    if spec.get('history_bonus') is not None and not isinstance(spec['history_bonus'],dict):
        raise ValueError('한국사 등급 가산점 규칙 오류')
    adjustment=spec.get('grade_point_adjustments',{})
    if not isinstance(adjustment,dict) or any(key not in ('english','history') for key in adjustment):
        raise ValueError('영어·한국사 감점표 구조 오류')
    if spec.get('history_bonus') is not None and 'history' in adjustment:
        raise ValueError('한국사 가산표와 별도 감점표 동시 사용 불가')
    for key,values in adjustment.items():
        if not isinstance(values,dict) or set(values)!={str(i) for i in range(1,10)} or not all(type(v) in (int,float) for v in values.values()):
            raise ValueError(f'{key} 등급별 점수표는 1~9등급 필수')
    allowed=spec.get('eligibility',{})
    if not isinstance(allowed,dict):
        raise ValueError('지원 자격 규칙 형식 오류')
    return spec


def read_conversion_tables(directory=CONVERSION_DIR):
    table={}
    for file in sorted(Path(directory).glob('*.csv')):
        if file.name.startswith('pct-'):
            continue
        with file.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if not reader.fieldnames or not TABLE_COLUMNS.issubset(reader.fieldnames):
                raise ValueError(f'{file.name}: 변표 필수열 누락')
            for lineno,row in enumerate(reader,2):
                try:
                    key=(int(row['year']),row['university'].strip(),row['table_id'].strip(),
                         row['subject'].strip(),int(row['std_score']))
                    value=float(row['converted_score'])
                    if not 2022<=key[0]<=2027 or not all(key[1:4]) or not 0<=key[4]<=250 or value < 0:
                        raise ValueError('변표 범위 오류')
                    if not row['source_url'].startswith('https://') or not row['last_verified']:
                        raise ValueError('공식 출처/검수 날짜 누락')
                    if key in table:
                        raise ValueError('동일 학년도·대학·표·과목·표준점수 중복')
                    table[key]=value
                except (TypeError,ValueError) as error:
                    raise ValueError(f'{file.name}:{lineno}: {error}') from error
    return table


def read_percentile_conversion_tables(directory=CONVERSION_DIR):
    """2027 university-specific inquiry conversion indexed by OFFICIAL percentile."""
    table={}
    for file in sorted(Path(directory).glob('pct-*.csv')):
        with file.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if not reader.fieldnames or not PCT_TABLE_COLUMNS.issubset(reader.fieldnames):
                raise ValueError(f'{file.name}: 백분위 변표 필수 열 누락')
            for lineno,row in enumerate(reader,2):
                try:
                    key=(int(row['year']),row['university'].strip(),row['table_id'].strip(),
                         row['subject'].strip(),int(row['percentile']))
                    value=float(row['converted_score'])
                    if not 2022<=key[0]<=2027 or not all(key[1:4]) or not 0<=key[4]<=100 or value<0:
                        raise ValueError('백분위 변표 점수 범위 오류')
                    if not row['source_url'].startswith('https://') or not row['last_verified']:
                        raise ValueError('공식 출처 및 검수 날짜 누락')
                    if key in table:
                        raise ValueError('동일 대학·과목·백분위 변표 중복')
                    table[key]=value
                except (TypeError,ValueError) as e:
                    raise ValueError(f'{file.name}:{lineno}: {e}') from e
    return table


@lru_cache(maxsize=1)
def public_percentile_conversion_tables():
    return read_percentile_conversion_tables(CONVERSION_DIR)

@lru_cache(maxsize=1)
def public_conversion_tables():
    return read_conversion_tables(CONVERSION_DIR)


def compute_weighted(student, program, *, tables=None, percentile_tables=None):
    from app.scoring import ScoreResult
    spec_raw=program.get('formula_config_json')
    if not spec_raw or not program.get('formula_source_url', '').startswith('https://'):
        return None
    try:
        spec=validate_spec(json.loads(spec_raw) if isinstance(spec_raw,str) else spec_raw,program)
    except (TypeError,ValueError,json.JSONDecodeError):
        return None
    tables=public_conversion_tables() if tables is None else tables
    percentile_tables=public_percentile_conversion_tables() if percentile_tables is None else percentile_tables
    available_inquiries=student.get('inquiries',[])
    if not available_inquiries:
        return None
    eligibility=spec.get('eligibility',{})
    if eligibility.get('math_tracks') and student.get('math_track') not in eligibility['math_tracks']:
        return None
    if eligibility.get('inquiry_kinds') and any(x.get('kind') not in eligibility['inquiry_kinds'] for x in available_inquiries):
        return None
    if len(available_inquiries) < eligibility.get('required_inquiries',2):
        return None
    comps=spec['components']
    def raw_value(area, part, inquiry=None):
        mode=part['metric']
        if mode=='grade':
            g=student.get('english_grade') if area=='english' else student.get(area+'_grade')
            return part['grades'].get(str(g))
        source=inquiry if inquiry is not None else student
        key=('pct' if inquiry is not None else area+'_pct') if mode in ('pct','converted_pct') else ('std' if inquiry is not None else area+'_std')
        val=source.get(key)
        if val is None:
            return None
        if mode=='pct':
            return float(val)
        if mode=='std':
            return 100*float(val)/part['max_value']
        subject=(inquiry or {}).get('name') if inquiry is not None else area
        selected=percentile_tables if mode=='converted_pct' else tables
        key=(program['year'],program['university'],part['table_id'],subject,int(val))
        value=selected.get(key)
        if value is None and inquiry is not None and inquiry.get('kind') in ('social','science'):
            # Official combined social/science conversion curve only; not vocational.
            value=selected.get((program['year'],program['university'],part['table_id'],'*',int(val)))
        if value is None:
            return None
        points=part.get('kind_bonus_points',{}).get((inquiry or {}).get('kind'),0)
        return 100*(value+points)/part['max_value']
    breakdown={}
    for area in COMPONENTS:
        part=comps[area]
        if area=='inquiry':
            vals=[]
            for i in available_inquiries:
                base=raw_value(area,part,i)
                if base is None:
                    return None
                base *= 1+part.get('kind_bonus_pct',{}).get(i.get('kind'),0)
                vals.append(base)
            aggregation=part.get('aggregation','mean2')
            if aggregation=='best1':
                value=max(vals)
            else:
                if len(vals)<2:return None
                value=sum(sorted(vals,reverse=True)[:2])/(2 if aggregation=='mean2' else 1)
        else:
            value=raw_value(area,part)
            if value is None:return None
            if area=='math':
                value*=1+part.get('track_bonus_pct',{}).get(student.get('math_track'),0)
        breakdown[{'korean':'국어','math':'수학','english':'영어','inquiry':'탐구'}[area]]=round(
            value*spec['weights'][area]*spec['score_scale']/100, 3)
    h=spec.get('history_bonus')
    if h is not None:
        bonus=h.get(str(student.get('history_grade')))
        if bonus is None:return None
        breakdown['한국사']=float(bonus)
    for area, adjustment in spec.get('grade_point_adjustments',{}).items():
        grade=student.get('english_grade') if area=='english' else student.get('history_grade')
        delta=adjustment.get(str(grade))
        if delta is None:
            return None
        breakdown['영어 감점' if area=='english' else '한국사 감점']=float(delta)
    return ScoreResult(total=round(sum(breakdown.values()),3),
                       breakdown=breakdown,score_scale=float(spec['score_scale']))