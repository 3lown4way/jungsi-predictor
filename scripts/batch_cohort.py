"""Offline 2027 September mock-support cohort aggregation.
Private individual scores never appear in the public snapshot.
"""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.scope import in_scope
from app.scoring import compute

FIELDS = {'submission_id', 'year', 'exam_type', 'program_key', 'korean_pct',
          'math_pct', 'math_track', 'english_grade', 'history_grade',
          'inquiry1_pct', 'inquiry1_kind', 'inquiry1_name',
          'inquiry2_pct', 'inquiry2_kind', 'inquiry2_name', 'consented'}
MIN_GROUP = 30
MAX_PER_USER = 3


def _integer(value, minimum, maximum, name):
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name}: invalid integer') from None
    if not minimum <= v <= maximum:
        raise ValueError(f'{name}: out of range')
    return v


def _percentile(value, name):
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name}: invalid percentile') from None
    if not math.isfinite(v) or not 0 <= v <= 100:
        raise ValueError(f'{name}: out of range')
    return v


def read_private_submissions(path):
    """Private file format; NEVER print its contents to Actions logs."""
    output = []
    per_user = Counter()
    seen = set()
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
            raise ValueError('Private submission CSV has missing required fields')
        for line, r in enumerate(reader, 2):
            if r['consented'] != '1':
                continue
            if r['year'] != '2027' or r['exam_type'] != 'september':
                raise ValueError(f'row {line}: expected 2027 September mock exam')
            uid, key = r['submission_id'].strip(), r['program_key'].strip()
            if len(uid) < 12 or not key:
                raise ValueError(f'row {line}: missing opaque submission identifier or program')
            if (uid, key) in seen:
                raise ValueError(f'row {line}: duplicate mock application')
            seen.add((uid, key))
            per_user[uid] += 1
            if per_user[uid] > MAX_PER_USER:
                raise ValueError(f'row {line}: at most three mock applications per person')
            track = r['math_track']
            if track not in ('calculus', 'probability', 'geometry'):
                raise ValueError(f'row {line}: invalid math track')
            if any(r[f'inquiry{i}_kind'] not in ('social', 'science') for i in (1, 2)):
                raise ValueError(f'row {line}: invalid inquiry kind')
            student = {
                'korean_pct': _percentile(r['korean_pct'], 'korean_pct'),
                'math_pct': _percentile(r['math_pct'], 'math_pct'),
                'math_track': track,
                'english_grade': _integer(r['english_grade'], 1, 9, 'english_grade'),
                'history_grade': _integer(r['history_grade'], 1, 9, 'history_grade'),
                'inquiries': [
                    {'name': r[f'inquiry{i}_name'][:100],
                     'kind': r[f'inquiry{i}_kind'],
                     'pct': _percentile(r[f'inquiry{i}_pct'], f'inquiry{i}_pct')}
                    for i in (1, 2)
                ],
            }
            output.append((key, student))
    return output


def _quantile(values, q):
    ordered = sorted(values)
    point = (len(ordered) - 1) * q
    low, high = math.floor(point), math.ceil(point)
    return round(ordered[low] * (1 - (point - low)) + ordered[high] * (point - low), 1)


def _size_band(n):
    if n < 50:
        return '30–49'
    if n < 100:
        return '50–99'
    if n < 250:
        return '100–249'
    return '250+'


def build_snapshot(submissions, programs, *, min_group=MIN_GROUP, scorer=compute):
    if min_group < MIN_GROUP:
        raise ValueError('public snapshot requires at least 30 people per programme')
    active = {p['program_key']: p for p in programs
              if p['year'] == 2027 and in_scope(p) and p.get('formula_id')
              and p.get('formula_source_url')}
    by_program = defaultdict(list)
    for key, student in submissions:
        p = active.get(key)
        if not p:
            continue
        score = scorer(student, p)
        if score is None or not math.isfinite(score.total):
            continue
        by_program[key].append(float(score.total))
    result = []
    for key, values in sorted(by_program.items()):
        if len(values) < min_group:
            continue
        p = active[key]
        result.append({
            'program_key': key, 'university': p['university'],
            'department': p['department'], 'admission_round': p['round'],
            'year': 2027, 'mock_exam': 'september',
            'participant_count_band': _size_band(len(values)),
            'score_p25': _quantile(values, 0.25),
            'score_p50': _quantile(values, 0.5),
            'score_p75': _quantile(values, 0.75),
            'score_scale': float(p.get('score_scale') or 1000),
            'formula_source_url': p['formula_source_url'],
            'admission_probability': None,
            'probability_status': 'historical_outcomes_and_calibration_not_yet_verified',
            'interpretation': 'self_reported_2027_september_mock_support_not_actual_csat_admission',
        })
    return {
        'schema_version': '1.0',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'year': 2027, 'exam_type': 'september',
        'snapshot_mode': 'offline_github_actions',
        'cohort_source': 'consented_self_reported_mock_applications',
        'privacy_threshold': min_group,
        'predictions': result,
        'published_programs': len(result),
        'unpublished_reason': ('insufficient_verified_programs_or_cohort' if not result else None),
        'warnings': [
            '9월 모의지원 표본은 실제 수능 지원자 모집단의 무작위 표본이 아닙니다.',
            '모의평가 환산점수 분포는 최종 합격선이나 합격확률이 아닙니다.',
            '개별 학생 성적과 제출 ID는 절대로 이 파일에 게시하지 않습니다.',
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--private-input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    from app.database import connect
    from scripts.public_data import load
    load()
    with connect() as con:
        programs = [dict(r) for r in con.execute('SELECT * FROM programs WHERE year=2027')]
    snapshot = build_snapshot(read_private_submissions(args.private_input), programs)
    if not snapshot['predictions']:
        raise SystemExit('No publishable aggregate: official 2027 formula or >=30 consented applications missing')
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print('Published aggregate programme count:', snapshot['published_programs'])


if __name__ == '__main__':
    main()
