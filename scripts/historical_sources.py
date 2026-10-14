"""Source and cutoff registry for historical admissions research, not ML outcome labels."""
from __future__ import annotations
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"data/public/historical_admissions/official_2022_2026.json"
CUTS=ROOT/"data/public/historical_admissions/khu_medical_70pct_cuts.json"
YEARS=range(2022,2027)

def read_historical_catalog(path=REGISTRY):
    entries=json.loads(Path(path).read_text(encoding="utf-8"))
    keys=set()
    for row in entries:
        key=(row["year"],row["university"])
        if key in keys:raise ValueError(f"duplicate historical university/year: {key}")
        keys.add(key)
        if row["year"] not in YEARS or row["university"] not in ("서울대학교","경희대학교"):
            raise ValueError("unrecognized historical university/year")
        if not row["official_guide_url"].startswith("https://"):
            raise ValueError("historical official publication must be HTTPS")
        if row["complete_formula_approved"] is not False:
            raise ValueError("unverified metadata cannot become full score formulas")
        weights=row.get("relative_weights")
        if weights is not None and (not isinstance(weights,dict) or
           set(weights)!={"korean","math","inquiry"} or
           tuple(weights.values())!=(100,120,80)):
            raise ValueError("unverified SNU weight data")
    expected={(year,uni) for year in YEARS for uni in ("서울대학교","경희대학교")}
    if keys!=expected:raise ValueError("missing historical source row")
    return entries

def read_historical_cuts(path=CUTS):
    rows=json.loads(Path(path).read_text(encoding="utf-8"))
    ids=set()
    for row in rows:
        key=(row["year"],row["university"],row["department"])
        if key in ids:raise ValueError(f"duplicate official cutoff: {key}")
        ids.add(key)
        if row["year"] not in YEARS or row["university"]!="경희대학교":
            raise ValueError("unrecognized cutoff year/university")
        if row["source_report_academic_year"]!=row["year"]+1 or row["source_result_academic_year"]!=row["year"]:
            raise ValueError("publication year cannot be treated as outcome year")
        if not row["source_url"].startswith("https://www.adiga.kr/"):
            raise ValueError("not published on official admissions portal")
        if row["reference_type"]!="final_enrollee_70_percentile_university_total":
            raise ValueError("not final enrolled 70% cutoff")
        if row.get("probability_label_eligible") is not False:
            raise ValueError("enrollee cutoff is not one applicant's admission")
        score=row["final_enrollee_70pct_converted_score"];maximum=row["score_scale"]
        if not (type(score) in (float,int) and type(maximum) in (float,int)
                and math.isfinite(score) and 0<=score<=maximum):
            raise ValueError("cutoff score/scale invalid")
        if type(row["published_final_recruitment"]) is not int or row["published_final_recruitment"]<=0:
            raise ValueError("invalid final quota")
    return rows

def summary():
    sources=read_historical_catalog()
    cuts=read_historical_cuts()
    return {"source_pairs":len(sources),"historical_source_universities":2,
            "historical_admission_cut_rows":len(cuts),
            "historical_cut_years":sorted({r["year"] for r in cuts}),
            "complete_year_specific_formulas":sum(r["complete_formula_approved"] for r in sources),
            "cutoffs_usable_as_individual_outcomes":0,
            "warning":"이 장부는 문서와 공개 컷의 검증 목록이며 2027 합격확률 모델 자체는 아닙니다."}

if __name__=="__main__":
    print(json.dumps(summary(),ensure_ascii=False,indent=2))
