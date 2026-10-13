import os
import tempfile
from pathlib import Path

from app.scoring import compute
from app.ml import backtest, predict_probability

P={'year':2025,'formula_id':'sangmyung_pct_2025_2026','track':'natural'}
S={'korean_pct':88,'math_pct':90,'math_track':'calculus','english_grade':1,'history_grade':1,
   'inquiries':[{'pct':86,'kind':'science','name':'물리학Ⅰ'},{'pct':80,'kind':'social','name':'사회문화'}]}

def test_official_9571():
    r=compute(S,P)
    assert r.total==957.1
    assert r.breakdown['수학']==346.5
    assert r.breakdown['탐구']==180.6

def test_humanities_no_bonus():
    r=compute(S,{**P,'track':'humanities'})
    assert r.breakdown['수학']==225.0
    assert r.breakdown['탐구']==172.0

def test_year_isolation():
    assert compute(S,{**P,'year':2027}) is None
    assert compute(S,{**P,'formula_id':'unverified'}) is None

def test_no_actual_outcomes_means_no_probabilities():
    assert all(r['status']=='insufficient_data' for r in backtest([]))
    probability,message=predict_probability([],2025,'smu-seoul-cs',{
        'korean_pct':90,'math_pct':90,'inquiry1_pct':90,'inquiry2_pct':90,
        'english_grade':1,'math_track':'calculus'})
    assert probability is None


def test_2025_2026_official_score_rule_agreement():
    r1=compute(S,P)
    r2=compute(S,{**P,'year':2026})
    assert r1.total == r2.total  # 서로 다른 연도 공식표에서 산식 동일함을 확인한 경우만
