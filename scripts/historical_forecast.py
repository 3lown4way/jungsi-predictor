"""Offline historical 9평 -> eventual admission model using EACH YEAR'S official weights.

2022-26 verified September score reports paired with actual admission outcomes.
Historical CSAT-only outcomes are intentionally rejected as input for a 9평 prediction.
70%-enrollee cutoffs never become individual admission labels.
Public output contains ONLY program-level, min-sample-gated score/probability curves.
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from app.scoring import compute
from app.scope import in_scope

MIN_TRAIN=100
MIN_TEST=30
MIN_CLASS=10
MIN_HISTORICAL_YEARS=3
MIN_TEST_YEARS=2
MIN_SUPPORT=180
MAX_WEIGHT_DRIFT=.15
CURVE_POINTS=121
FEATURES=("weighted_normalized_score","log_quota")


def read_private_jsonl(path):
    """No private row, hash or student's score is ever logged or exported."""
    rows=[]
    seen=set()
    with Path(path).open(encoding="utf-8") as f:
        for line_no,line in enumerate(f,1):
            if not line.strip():continue
            row=json.loads(line)
            year=row.get("year")
            if type(year) is not int or not 2022<=year<=2026 or row.get("exam_type")!="september":
                raise ValueError(f"line {line_no}: requires verified 2022-26 September report")
            if any(row.get(k) is not True for k in ("applied","verified","consented")):
                raise ValueError(f"line {line_no}: verified actual application and consent required")
            if type(row.get("admitted")) is not int or row["admitted"] not in (0,1):
                raise ValueError(f"line {line_no}: actual admitted label must be 0 or 1")
            student=row.get("student")
            if not isinstance(student,dict) or not isinstance(student.get("inquiries"),list):
                raise ValueError(f"line {line_no}: individual report-card inputs missing")
            key=(year,row.get("program_key"),row.get("applicant_hash"))
            if not isinstance(key[1],str) or not key[1] or not isinstance(key[2],str) or len(key[2])<16:
                raise ValueError(f"line {line_no}: pseudonymous record and program required")
            if key in seen:raise ValueError(f"line {line_no}: duplicate applicant/program/year")
            seen.add(key)
            rows.append(row)
    return rows


def _official_weights(program):
    if program.get("formula_id")!="weighted_official_v1" or not program.get("formula_config_json"):
        return None
    try:
        s=json.loads(program["formula_config_json"]) if isinstance(program["formula_config_json"],str) else program["formula_config_json"]
        if s["year"]!=program["year"] or s["university"]!=program["university"] or s["program_key"]!=program["program_key"]:
            return None
        w=s["weights"]
        if set(w)!=set(("korean","math","english","inquiry")) or abs(sum(w.values())-1)>1e-8:
            return None
        return w
    except (KeyError,TypeError,ValueError):
        return None


def compile_history(raw_records, programs, *, scorer=compute):
    """Use 2022 rules on 2022 students, 2023 rules on 2023 students, etc."""
    index={(p["year"],p["program_key"]):p for p in programs if in_scope(p)}
    compiled=[]
    skipped=defaultdict(int)
    for entry in raw_records:
        key=(entry["year"],entry["program_key"])
        program=index.get(key)
        if not program or not program.get("formula_source_url") or not _official_weights(program):
            skipped["missing_year_specific_verified_formula"]+=1
            continue
        quota=program.get("quota")
        if type(quota) is not int or quota<=0:
            skipped["missing_historical_quota"]+=1
            continue
        result=scorer(entry["student"],program)
        if result is None or not math.isfinite(result.total) or result.score_scale<=0:
            skipped["historical_score_uncomputable"]+=1
            continue
        ratio=result.total/result.score_scale
        if not 0<=ratio<=1.5:
            skipped["out_of_range_weighted_score"]+=1
            continue
        compiled.append({"year":entry["year"],"program_key":entry["program_key"],
                         "university":program["university"],
                         "score_ratio":round(ratio,9),"quota":quota,
                         "admitted":entry["admitted"],
                         "weights":_official_weights(program),
                         "official_source_year":program["year"]})
    return compiled,dict(skipped)


def _enough(rows, minimum):
    if len(rows)<minimum:return False
    wins=sum(r["admitted"] for r in rows)
    return wins>=MIN_CLASS and len(rows)-wins>=MIN_CLASS


def _x(rows):
    return np.array([[r["score_ratio"],math.log1p(r["quota"])] for r in rows],dtype=float)


def _model(rows):
    model=make_pipeline(StandardScaler(),LogisticRegression(C=.5,max_iter=1000))
    model.fit(_x(rows),np.array([r["admitted"] for r in rows]))
    return model


def fit_2027_curves(compiled, programs, *, minimum_train=MIN_TRAIN):
    """Strict walk-forward by academic year and per-major coverage; never train on 2027."""
    if any(r["year"]>=2027 for r in compiled):
        raise ValueError("2027 labels must not be used as training data")
    current={p["program_key"]:p for p in programs if p["year"]==2027 and in_scope(p)}
    groups=defaultdict(list)
    for r in compiled:groups[r["program_key"]].append(r)
    results=[]
    coverage={"programs_considered":len(current),"trained_programs":0,
              "missing_year_specific_rules":0,"missing_verified_outcomes":0,
              "unvalidated_or_drifted":0}
    for key,program in sorted(current.items()):
        hist=groups.get(key,[])
        current_w=_official_weights(program)
        if current_w is None or not program.get("formula_source_url") or not program.get("quota"):
            coverage["missing_year_specific_rules"]+=1
            continue
        if not hist:
            coverage["missing_verified_outcomes"]+=1
            continue
        # A large change in official weights creates non-comparable pooled totals;
        # do not reuse old cohorts without a validated transfer model.
        usable=[r for r in hist
                if r["university"]==program["university"] and
                max(abs(current_w[c]-r["weights"][c]) for c in current_w)<=MAX_WEIGHT_DRIFT]
        if len(usable)<MIN_SUPPORT or len({r["year"] for r in usable})<4 or not _enough(usable,minimum_train):
            coverage["unvalidated_or_drifted"]+=1
            continue
        checks=[]
        for y in (2025,2026):
            train=[r for r in usable if r["year"]<y]
            test=[r for r in usable if r["year"]==y]
            if len({r["year"] for r in train})<MIN_HISTORICAL_YEARS or not _enough(train,minimum_train) or not _enough(test,MIN_TEST):
                continue
            ml=_model(train)
            prob=ml.predict_proba(_x(test))[:,1]
            true=np.array([r["admitted"] for r in test])
            baseline=np.full(len(test),np.mean([r["admitted"] for r in train]))
            checks.append({"test_year":y,"auc":float(roc_auc_score(true,prob)),
                           "brier":float(brier_score_loss(true,prob)),
                           "baseline_brier":float(brier_score_loss(true,baseline)),
                           "calibration_error":abs(float(np.mean(prob)-np.mean(true))),
                           "test_n":len(test)})
        if len(checks)<MIN_TEST_YEARS or any(
            r["auc"]<.60 or r["brier"]>=r["baseline_brier"] or r["calibration_error"]>.12
            for r in checks):
            coverage["unvalidated_or_drifted"]+=1
            continue
        ml=_model(usable)
        scores=np.array(sorted(r["score_ratio"] for r in usable),dtype=float)
        lo=float(np.quantile(scores,.05));hi=float(np.quantile(scores,.95))
        if hi-lo<.02:
            coverage["unvalidated_or_drifted"]+=1
            continue
        quota=program["quota"]
        x=np.column_stack((np.linspace(lo,hi,CURVE_POINTS),
                            np.full(CURVE_POINTS,math.log1p(quota))))
        values=ml.predict_proba(x)[:,1]
        curve=[{"score_fraction":round(float(s),6),"probability":round(float(p),4)}
               for s,p in zip(x[:,0],values)]
        results.append({
            "program_key":key,"university":program["university"],
            "year":2027,"exam_type":"september",
            "model_type":"annual_official_weighted_score_logistic",
            "curve":curve,"historical_sample_band":(
                "500+" if len(usable)>=500 else
                "300-499" if len(usable)>=300 else "180-299"),
            "training_years":sorted({r["year"] for r in usable}),
            "backtested_years":[r["test_year"] for r in checks],
            "holdout_auc_min":round(min(r["auc"] for r in checks),3),
            "holdout_brier_max":round(max(r["brier"] for r in checks),3),
            "score_scope":"same-year official admission weights applied to September individual score reports",
            "warning":"Self-selected historical support samples can bias conditional probabilities."
        })
        coverage["trained_programs"]+=1
    return {"schema_version":"1.0","target_year":2027,"reference_exam":"september",
            "trained_on":"2022-2026 verified September reports paired with actual admissions",
            "method":"year-specific official weights + strictly forward-calibrated, score-conditioned curves",
            "min_history":MIN_SUPPORT,"min_holdout_years":MIN_TEST_YEARS,
            "coverage":coverage,"curves":results,
            "warning":"No actual label from 70-percent enrollee cutoff. Only vetted applicant outcome observations."}


def run(input_file, output):
    from scripts.public_data import load
    from app.database import connect
    load()
    with connect() as con:
        programs=[dict(p) for p in con.execute("SELECT * FROM programs")]
    raw=read_private_jsonl(input_file)
    compiled, skipped=compile_history(raw,programs)
    snapshot=fit_2027_curves(compiled,programs)
    if skipped:
        snapshot["coverage"]["unusable_private_observations"]=sum(skipped.values())
    path=Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print("Historical matching and holdout validation completed; publishable programme curves:",
          snapshot["coverage"]["trained_programs"])


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--private-input",required=True,
                        help="PRIVATE, consented & verified 2022-26 September/outcome JSONL; never commit")
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    run(args.private_input,args.output)
