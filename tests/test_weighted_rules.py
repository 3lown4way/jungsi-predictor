import csv
import json
import pytest
from app.weighted_rules import validate_spec, read_conversion_tables, compute_weighted


def sample_rule():
    return {
        "version":1,"year":2027,"university":"시험대학교","program_key":"test-chem",
        "score_scale":1000,
        "weights":{"korean":0.2,"math":0.35,"english":0.1,"inquiry":0.35},
        "components":{
            "korean":{"metric":"std","max_value":200},
            "math":{"metric":"std","max_value":200,"track_bonus_pct":{"calculus":0.05}},
            "english":{"metric":"grade","grades":{"1":100,"2":95}},
            "inquiry":{"metric":"converted_std","max_value":75,"table_id":"science_2027","aggregation":"mean2"}
        },
        "history_bonus":{"1":10,"2":9},
        "eligibility":{"math_tracks":["calculus","geometry"],"inquiry_kinds":["science"],"required_inquiries":2}
    }


def student():
    return {"korean_std":140,"math_std":140,"math_track":"calculus",
            "english_grade":1,"history_grade":1,
            "inquiries":[{"name":"물리학Ⅰ","kind":"science","std":65},
                         {"name":"화학Ⅰ","kind":"science","std":66}]}


def program(rule=None,year=2027):
    return {"year":year,"university":"시험대학교","program_key":"test-chem",
            "formula_id":"weighted_official_v1",
            "formula_source_url":"https://example.org/official-mock-rule",
            "formula_config_json":json.dumps(rule or sample_rule(),ensure_ascii=False)}


def test_different_weights_and_subject_conversion():
    table={(2027,"시험대학교","science_2027","물리학Ⅰ",65):68.0,
           (2027,"시험대학교","science_2027","화학Ⅰ",66):70.0}
    score=compute_weighted(student(),program(),tables=table)
    assert score is not None
    # 140/200*200 + (140/200*1.05)*350 + 100 + ((68+70)/2)/75*350 + 10
    assert score.total==pytest.approx(140+257.25+100+322+10)
    assert score.breakdown['탐구']==322


def test_missing_converted_standard_score_is_never_interpolated():
    table={(2027,"시험대학교","science_2027","물리학Ⅰ",65):68.0}
    assert compute_weighted(student(),program(),tables=table) is None


def test_year_isolation_and_eligibility():
    assert compute_weighted(student(),program(year=2026),tables={}) is None
    invalid={**student(),"math_track":"probability"}
    assert compute_weighted(invalid,program(),tables={}) is None


def test_rule_weights_must_sum_to_one():
    rule=sample_rule()
    rule['weights']['math']=.5
    with pytest.raises(ValueError,match="합"):
        validate_spec(rule,program(rule))


def test_table_reject_duplicate_bins(tmp_path):
    path=tmp_path/"test.csv"
    row={"year":"2027","university":"시험대학교","table_id":"science_2027",
         "subject":"물리학Ⅰ","std_score":"65","converted_score":"68",
         "source_url":"https://example.org/official-mock-rule","last_verified":"2026-10-14"}
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(row))
        w.writeheader();w.writerow(row);w.writerow(row)
    with pytest.raises(ValueError,match="중복"):
        read_conversion_tables(tmp_path)



def test_percentile_converted_with_point_bonus_and_grade_deductions():
    r=sample_rule()
    r['weights']={'korean':.25,'math':.4,'english':0,'inquiry':.35}
    r['components']['math']={'metric':'std','max_value':200}
    r['components']['english']={'metric':'grade','grades':{str(i):0 for i in range(1,10)}}
    r['components']['inquiry']={'metric':'converted_pct','max_value':75,
                                 'table_id':'example_2027','aggregation':'mean2',
                                 'kind_bonus_points':{'science':4}}
    r['history_bonus']=None
    r['grade_point_adjustments']={
        'english':{str(i):(0 if i<=2 else -2 if i==3 else -30) for i in range(1,10)},
        'history':{str(i):(0 if i<=4 else -2 if i==5 else -20) for i in range(1,10)},
    }
    candidate=student()
    candidate['english_grade']=3
    candidate['history_grade']=5
    candidate['inquiries'][0]['pct']=97
    candidate['inquiries'][1]['pct']=96
    percentile={(2027,'시험대학교','example_2027','물리학Ⅰ',97):68,
                (2027,'시험대학교','example_2027','화학Ⅰ',96):70}
    result=compute_weighted(candidate,program(r),tables={},percentile_tables=percentile)
    assert result is not None
    assert result.total==pytest.approx(791.667)
    assert result.breakdown['영어 감점']==-2
    assert result.breakdown['한국사 감점']==-2
    del percentile[(2027,'시험대학교','example_2027','화학Ⅰ',96)]
    assert compute_weighted(candidate,program(r),tables={},percentile_tables=percentile) is None


def test_duplicate_pct_conversion_table_rejected(tmp_path):
    from app.weighted_rules import read_percentile_conversion_tables
    file=tmp_path/'pct-example.csv'
    row={'year':2027,'university':'시험대학교','table_id':'example_2027',
         'subject':'물리학Ⅰ','percentile':97,'converted_score':68,
         'source_url':'https://example.org/research','last_verified':'2026-10-14'}
    with file.open('w',encoding='utf-8',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=row.keys())
        writer.writeheader();writer.writerow(row);writer.writerow(row)
    with pytest.raises(ValueError,match='중복'):
        read_percentile_conversion_tables(tmp_path)


def test_shared_2025_soongsil_social_science_conversion_table_complete():
    from app.weighted_rules import read_percentile_conversion_tables
    d=read_percentile_conversion_tables()
    seq=[d[(2025,'숭실대학교','soongsil_2025_social_science','*',p)] for p in range(101)]
    assert len(seq)==101
    assert seq[100]==70
    assert seq[99]==69.08
    assert seq[91]==64.18
    assert seq[88]==63.10
    assert seq[83]==61.34
    assert seq[0]==30.71
    assert all(seq[p]<=seq[p+1] for p in range(100))
