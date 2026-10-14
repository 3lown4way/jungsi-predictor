"""학년도-모집단위별 버전형 정시 환산 엔진.

현재 'sangmyung_pct_2025_2026'은 대입정보포털에 공개된
상명대학교 서울캠퍼스 수능전형 2025/2026 산출식을 구현합니다.
새로운 학교의 산식은 연도별 별도 플러그인과 검증 테스트가 필수입니다.
"""
from dataclasses import dataclass
from typing import Optional

ENGLISH = {1: 100, 2: 98, 3: 96, 4: 94, 5: 90, 6: 80, 7: 60, 8: 40, 9: 0}
HISTORY = {1: 10.0, 2: 9.8, 3: 9.6, 4: 9.4, 5: 9.2, 6: 9.0, 7: 9.0, 8: 9.0, 9: 9.0}

@dataclass
class ScoreResult:
    total: float
    breakdown: dict
    score_scale: float = 1000.0


def compute(student: dict, program: dict) -> Optional[ScoreResult]:
    if program.get('formula_id') == 'weighted_official_v1':
        from app.weighted_rules import compute_weighted
        return compute_weighted(student,program)
    if program.get('formula_id') != 'sangmyung_pct_2025_2026':
        return None
    y = program['year']
    if y not in (2025, 2026):
        return None
    kind = program['track']
    if kind not in ('humanities', 'natural'):
        return None
    k, m = student.get('korean_pct'), student.get('math_pct')
    eg, hg = student.get('english_grade'), student.get('history_grade')
    if k is None or m is None or eg not in ENGLISH or hg not in HISTORY:
        return None
    inquiries = [t for t in student.get('inquiries', [])
                 if t.get('kind') in ('social', 'science') and t.get('pct') is not None]
    if not inquiries:
        return None
    w_k, w_m = (0.35, 0.25) if kind == 'humanities' else (0.25, 0.35)
    # 자연계: 선택과목이 미적분/기하이면 수학 해당 반영점수 10% 가산.
    math_bonus = 0.10 if kind == 'natural' and student.get('math_track') in ('calculus', 'geometry') else 0.0
    # 탐구 상위 1과목: 가산점을 포함한 환산점수가 가장 큰 과목 반영.
    options = [(float(t['pct']) * (1.05 if kind == 'natural' and t['kind'] == 'science' else 1), t)
               for t in inquiries]
    inquiry_weighted, selected = max(options, key=lambda x: x[0])
    breakdown = {
        '국어': round(k * w_k * 10, 3),
        '수학': round(m * w_m * 10 * (1 + math_bonus), 3),
        '영어': round(ENGLISH[eg] * 0.20 * 10, 3),
        '탐구': round(inquiry_weighted * 0.20 * 10, 3),
        '한국사': HISTORY[hg],
        '반영 탐구': selected.get('name', '상위 과목'),
    }
    total = round(sum(v for v in breakdown.values() if isinstance(v, (int, float))), 3)
    return ScoreResult(total=total, breakdown=breakdown)
