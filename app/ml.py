"""정시 개별 지원자의 실측 합불만으로 연도 순행 평가.

공개 70% 컷을 불합격 라벨로 변환하지 않습니다. 2027 결괏값을 학습하지 않습니다.
한 학년도를 통째로 테스트하며 입력 백분위는 해당 시험 내 상대 위치를 뜻합니다.
"""
import math
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss, accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMS = ['korean_pct','math_pct','inquiry1_pct','inquiry2_pct','english_grade','quota','math_weight']
CATS = ['program_key','math_track','admission_round']
FEATURES = NUMS + CATS
MIN_TRAIN = 100
MIN_TEST = 30
MIN_PER_CLASS = 15
MIN_PROGRAM_SUPPORT = 10


def build_model():
    pre = ColumnTransformer([
        ('num', StandardScaler(), [FEATURES.index(k) for k in NUMS]),
        ('cat', OneHotEncoder(handle_unknown='ignore'), [FEATURES.index(k) for k in CATS]),
    ])
    return Pipeline([('features', pre), ('model', LogisticRegression(max_iter=1000, C=0.5))])


def as_rows(con):
    return [dict(r) for r in con.execute('''SELECT year,program_key,korean_pct,math_pct,
        inquiry1_pct,inquiry2_pct,english_grade,math_track,quota,math_weight,admission_round,admitted FROM actual_applications
        WHERE applied=1 AND consented=1 AND verified=1 AND year BETWEEN 2022 AND 2026
        AND quota IS NOT NULL AND admission_round IS NOT NULL AND math_weight IS NOT NULL''')]


def sufficient(rows, test=False):
    n = len(rows)
    minimum = MIN_TEST if test else MIN_TRAIN
    if n < minimum:
        return False
    pos = sum(int(row['admitted']) for row in rows)
    return pos >= MIN_PER_CLASS and (n-pos) >= MIN_PER_CLASS


def train(rows):
    if not sufficient(rows) or len({r['year'] for r in rows}) < 2:
        return None
    model = build_model()
    model.fit([[r[k] for k in FEATURES] for r in rows], [r['admitted'] for r in rows])
    return model


def backtest(rows):
    """2022~2026학년도 순행 백테스트. 같은 연도 결과를 해당 연도 훈련에 넣지 않는다."""
    results = []
    for test_year in range(2023, 2027):
        train_rows = [r for r in rows if r['year'] < test_year]
        test_rows = [r for r in rows if r['year'] == test_year]
        model = train(train_rows)
        if model is None or not sufficient(test_rows, test=True):
            results.append({'test_year':test_year, 'status':'insufficient_data',
                            'train_n':len(train_rows),'test_n':len(test_rows)})
            continue
        X = [[r[k] for k in FEATURES] for r in test_rows]
        y = np.array([r['admitted'] for r in test_rows])
        p = model.predict_proba(X)[:,1]
        results.append({'test_year':test_year,'status':'evaluated',
                        'train_n':len(train_rows),'test_n':len(test_rows),
                        'auc': round(float(roc_auc_score(y,p)),3),
                        'brier':round(float(brier_score_loss(y,p)),3),
                        'accuracy_at_50':round(float(accuracy_score(y,p>=0.5)),3),
                        'brier_baseline':round(float(brier_score_loss(y, np.full(len(y),np.mean([r['admitted'] for r in train_rows])))),3),
                        'observed_admit_rate':round(float(np.mean(y)),3),
                        'predicted_admit_rate':round(float(np.mean(p)),3)})
    return results


def predict_probability(rows, year, program_key, student):
    """예측 전 백테스트와 동일 모집단위 과거 지원자 충분성 확인."""
    prior = [r for r in rows if r['year'] < year]
    historical_program_rows = [r for r in prior if r['program_key']==program_key]
    if len(historical_program_rows) < MIN_PROGRAM_SUPPORT:
        return None, '해당 모집단위의 검증된 과거 개별 지원·합불 기록 부족'
    tests = [t for t in backtest(prior) if t['status']=='evaluated']
    if len(tests) < 2:
        return None, '서로 다른 2개 이상의 학년도에서 순행 외부검증 필요'
    if any(t['auc'] < 0.60 or t['brier'] >= t['brier_baseline'] or
           abs(t['predicted_admit_rate']-t['observed_admit_rate'])>0.10 for t in tests[-2:]):
        return None, '외부검증 구분 성능/확률오차 기준 미충족'
    if student.get('quota') is None or student.get('math_weight') is None:
        return None, '해당 학년도 모집인원/수능 반영비율 미등록'
    model = train(prior)
    if model is None:
        return None, '모델 학습 자료 부족'
    rec = {k:student[k] for k in NUMS}
    rec['program_key'] = program_key
    rec['math_track'] = student.get('math_track','calculus')
    rec['admission_round'] = student['admission_round']
    prob = float(model.predict_proba([[rec[k] for k in FEATURES]])[0,1])
    # 이것은 모의지원 응답 표본의 선택편의가 있는 조건부 확률이다.
    return round(prob,4), '실측 지원자 기반 시험연도 순행 검증; 모집단위별 표본 편향 주의'
