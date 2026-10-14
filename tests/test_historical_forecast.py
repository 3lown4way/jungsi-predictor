"""Synthetic fixtures are for logic tests ONLY, never shipped as real admissions data."""
import json
from pathlib import Path
import pytest
from scripts.historical_forecast import (compile_history,fit_2027_curves,read_private_jsonl)


def rule(y,key="test-medicine"):
    w={"korean":.2+(y-2022)*.01,"math":.4-(y-2022)*.01,
       "english":.1,"inquiry":.3}
    return {"version":1,"year":y,"university":"서울대학교","program_key":key,
     "score_scale":1000,"weights":w,
     "components":{"korean":{"metric":"pct"},"math":{"metric":"pct"},
       "english":{"metric":"grade","grades":{str(i):100-5*(i-1) for i in range(1,10)}},
       "inquiry":{"metric":"pct","aggregation":"mean2"}},
     "history_bonus":{str(i):0 for i in range(1,10)}}


def programme(y,key="test-medicine"):
    return {"year":y,"program_key":key,"university":"서울대학교","department":"의예과",
        "track":"natural","quota":40,"round":"나",
        "formula_id":"weighted_official_v1",
        "formula_source_url":f"https://example.org/verified/{y}",
        "formula_config_json":json.dumps(rule(y,key),ensure_ascii=False)}


def example(y,i):
    pct=59+(i%60)
    if pct>100:pct=100
    # Both classes occur in every 80-person synthetic year
    pct=65+(i%48)
    pct=min(100,pct)
    score=72+(i%50)*.5
    p=min(100,round(score,1))
    return {
        "year":y,"exam_type":"september","program_key":"test-medicine",
        "applicant_hash":f"opaque_verified_hash_{y}_{i:04}",
        "admitted":int(i%80>=40),"applied":True,"verified":True,"consented":True,
        "student":{"korean_pct":p,"math_pct":p,"english_grade":1 if i>=40 else 3,
          "history_grade":1,"math_track":"calculus",
          "inquiries":[{"name":"사회·문화","kind":"social","pct":p},
                       {"name":"생활과 윤리","kind":"social","pct":p}]}
    }


def sample():
    return [example(y,i) for y in range(2022,2027) for i in range(80)]


def test_each_historical_year_uses_its_own_weights_not_2027_rule():
    programs=[programme(y) for y in range(2022,2028)]
    rows, skipped=compile_history(sample(),programs)
    assert len(rows)==400 and skipped=={}
    assert {r["official_source_year"] for r in rows}==set(range(2022,2027))
    first=next(r for r in rows if r["year"]==2022)
    last=next(r for r in rows if r["year"]==2026)
    assert first["weights"]["math"]==.4
    assert last["weights"]["math"]==pytest.approx(.36)
    assert first["score_ratio"]!=last["score_ratio"]


def test_incomplete_or_wrong_year_formula_does_not_contribute():
    rows, skipped=compile_history(sample(),[programme(y) for y in (2025,2026,2027)])
    assert len(rows)==160
    assert skipped["missing_year_specific_verified_formula"]==240


def test_unverified_or_csat_only_private_data_is_rejected(tmp_path):
    p=tmp_path/"private.jsonl"
    rec=example(2025,0)
    rec["exam_type"]="csat"
    p.write_text(json.dumps(rec,ensure_ascii=False)+"\n")
    with pytest.raises(ValueError,match="September"):
        read_private_jsonl(p)
    rec["exam_type"]="september"
    rec["verified"]=False
    p.write_text(json.dumps(rec,ensure_ascii=False)+"\n")
    with pytest.raises(ValueError,match="consent"):
        read_private_jsonl(p)


def test_missing_holdout_or_drifting_weights_never_generate_probability():
    programs=[programme(y) for y in range(2022,2028)]
    rows,_=compile_history([r for r in sample() if r["year"]<=2024],programs)
    s=fit_2027_curves(rows,programs)
    assert s["curves"]==[]
    bad=programs[:-1]+[programme(2027)]
    new=json.loads(bad[-1]["formula_config_json"])
    new["weights"]={"korean":.5,"math":.1,"english":.1,"inquiry":.3}
    bad[-1]["formula_config_json"]=json.dumps(new,ensure_ascii=False)
    allrows,_=compile_history(sample(),bad)
    assert fit_2027_curves(allrows,bad)["curves"]==[]


def test_future_year_labels_cannot_train():
    with pytest.raises(ValueError,match="2027"):
        fit_2027_curves([{"year":2027}], [programme(2027)])


def test_only_aggregate_calibrated_curves_no_applicant_identifiers():
    programs=[programme(y) for y in range(2022,2028)]
    rows,_=compile_history(sample(),programs)
    result=fit_2027_curves(rows,programs)
    assert result["coverage"]["programs_considered"]==1
    assert result["coverage"]["trained_programs"]==1
    curve=result["curves"][0]
    assert curve["backtested_years"]==[2025,2026]
    assert len(curve["curve"])==121
    assert all(0<=v["probability"]<=1 for v in curve["curve"])
    assert all(2022<=y<=2026 for y in curve["training_years"])
    serial=json.dumps(result)
    assert "applicant_hash" not in serial and "student" not in serial
    assert "opaque_verified_hash" not in serial
