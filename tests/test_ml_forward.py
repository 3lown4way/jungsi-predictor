"""학습용 샘플이 아닌 '테스트 안에서만 생성'하는 합성 지원자 데이터."""
from app.ml import backtest, predict_probability


def synthetic_rows():
    rows=[]
    for y in (2022,2023,2024,2025):
        for i in range(60):
            high=i>=30
            base=88 if high else 70
            rows.append({
                'year':y,'program_key':'test-program','korean_pct':base+(i%7),
                'math_pct':base+(i%5),'inquiry1_pct':base+(i%4),
                'inquiry2_pct':base-(i%4),'english_grade':1 if high else 3,
                'math_track':'calculus' if i%3 else 'geometry',
                'admission_round':'나','quota':30+(y-2022)%3,
                'math_weight':0.35,'admitted':1 if high else 0,
            })
    return rows


def test_forward_chaining_and_no_future_leakage():
    rows=synthetic_rows()
    earlier=backtest([r for r in rows if r['year']<=2024])
    full=backtest(rows)
    old=next(t for t in earlier if t['test_year']==2024)
    new=next(t for t in full if t['test_year']==2024)
    assert old == new
    assert old['status']=='evaluated'
    assert old['train_n']==120 and old['test_n']==60
    assert old['auc'] > .7
    assert old['brier'] < old['brier_baseline']
    assert next(t for t in full if t['test_year']==2023)['status']=='insufficient_data'


def test_model_only_after_two_years_heldout_validation():
    rows=synthetic_rows()
    features={**rows[-1], 'math_track':'calculus'}
    prob_before,_=predict_probability(rows,2025,'test-program',features)
    prob_after,_=predict_probability(rows,2026,'test-program',features)
    assert prob_before is None
    assert prob_after is not None
    assert 0 <= prob_after <= 1
