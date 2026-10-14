from app.soongsil_2025 import (compute_soongsil_2025_csat, SOURCE_WEIGHTS,
                               KOREAN_MAX, MATH_MAX)
from app.scoring import compute
from app.weighted_rules import read_percentile_conversion_tables


def program(group):
    return {'year':2025,'university':'숭실대학교','track':group,
            'formula_id':'soongsil_2025_csat_v1',
            'formula_source_url':SOURCE_WEIGHTS}


def applicant_b():
    return {'exam_type':'csat','korean_std':116,'math_std':123,
            'math_track':'calculus','english_grade':3,'history_grade':4,
            'inquiries':[{'name':'물리학Ⅰ','kind':'science','pct':91},
                         {'name':'화학Ⅱ','kind':'science','pct':99}]}


def applicant_a():
    return {'exam_type':'csat','korean_std':134,'math_std':123,
            'math_track':'probability','english_grade':2,'history_grade':1,
            'inquiries':[{'name':'정치와 법','kind':'social','pct':83},
                         {'name':'사회·문화','kind':'social','pct':88}]}


def test_2025_actual_complete_101_bin_conversion_curve():
    d=read_percentile_conversion_tables()
    values=[d[(2025,'숭실대학교','soongsil_2025_social_science','*',i)] for i in range(101)]
    assert len(values)==101 and values[0]==30.71 and values[100]==70
    assert values[91]==64.18 and values[99]==69.08
    assert KOREAN_MAX==139 and MATH_MAX==140


def test_natural2_official_worked_example_uses_same_2025_2026_rule_911_77():
    # 2026 official Adiga worked example uses 2025 actual standard-score
    # max and conversion table; natural2 weights / bonuses identical to 2025.
    score=compute_soongsil_2025_csat(applicant_b(),program('natural2'))
    assert score is not None
    assert score.total==911.770
    assert score.breakdown['국어']==166.906
    assert score.breakdown['탐구 1']==114.607
    assert score.breakdown['탐구 2']==123.357
    assert score.breakdown['수학 가산점']==6.15
    assert score.breakdown['탐구 1 가산점']==2.275
    assert score.breakdown['탐구 2 가산점']==2.475
    assert compute(applicant_b(),program('natural2')).total==score.total


def test_natural1_official_example_914_23_and_2025_humanities_differ():
    assert compute_soongsil_2025_csat(applicant_b(),program('natural1')).total==914.230
    score=compute_soongsil_2025_csat(applicant_a(),program('humanities'))
    assert score.total==932.822
    assert '탐구 1 가산점' not in score.breakdown
    score2=compute_soongsil_2025_csat(applicant_a(),program('free_humanities'))
    assert '탐구 1 가산점' in score2.breakdown


def test_2025_actual_csat_formula_never_applied_to_september_scores():
    s=applicant_b()
    s['exam_type']='september'
    assert compute_soongsil_2025_csat(s,program('natural2')) is None
    assert compute(s,program('natural2')) is None
    s['exam_type']='csat'
    s['inquiries'][1]['pct']=200
    assert compute(s,program('natural2')) is None
    s=applicant_b()
    s['inquiries'][1]['kind']='vocational'
    assert compute(s,program('natural2')) is None


def test_2025_inquiry_missing_never_replaced_by_another_year():
    src=read_percentile_conversion_tables()
    bad={k:v for k,v in src.items() if k[-1]!=99}
    assert compute_soongsil_2025_csat(applicant_b(),program('natural2'),table=bad) is None
