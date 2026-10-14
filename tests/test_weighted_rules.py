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
