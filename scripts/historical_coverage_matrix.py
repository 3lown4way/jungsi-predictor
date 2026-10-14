"""Historical cross-university, cross-year data readiness matrix (not a prediction).

One row per university x academic year, 2022--2026. Separate:
source landing page, quantified subject weights, complete percentile conversion,
computed past CSAT score, 70%-enrollee cutoff, and truly calibrated 9평 -> result.
Never infer formula completeness from a discoverable university archive URL.
"""
from __future__ import annotations
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
from app.scope import TOP_20
from scripts.national_research_scope import read_research

ROOT=Path(__file__).resolve().parents[1]
PARTIALS=(
    "data/public/university_research/khu_2024_2025_weights.json",
    "data/public/university_research/2026_verified_partial_formulas.json",
    "data/public/university_research/2026_konkuk_sejong_partial.json",
    "data/public/university_research/2026_sogang_inha_hufs_partial.json",
    "data/public/university_research/2026_six_more_universities.json",
    "data/public/university_research/2026_ewha_hongik_kookmin_ajou.json",
    "data/public/university_research/2025_hanyang_uos_sookmyung_ewha.json",
    "data/public/university_research/2026_six_more_universities.json",
    "data/public/university_research/2026_ewha_hongik_kookmin_ajou.json",
    "data/public/university_research/2026_sogang_inha_hufs_partial.json",
    "data/public/university_research/sogang_2023_partially_verified.json",
    "data/public/university_research/2025_soongsil_exact_csat.json",
)
CUTOFF_FILES=(
    "data/public/historical_admissions/khu_medical_70pct_cuts.json",
    "data/public/historical_admissions/konkuk_2025_70pct_cuts.json",
    "data/public/historical_admissions/soongsil_2025_70pct_cuts.json",
)
STATUS_ORDER=("source_link_found","official_subject_weights_found",
              "full_inquiry_conversion_verified","csat_calculation_validated",
              "september_score_transfer_validated","actual_application_labels_verified",
              "publishable_probability")


def extract_entries(source):
    doc=json.loads(source.read_text(encoding="utf-8"))
    if isinstance(doc,list):return doc
    if "records" in doc:return doc["records"]
    if "groups" in doc and isinstance(doc["groups"],list):return doc["groups"]
    if "year" in doc and "university" in doc:return [doc]
    raise ValueError(f"Cannot infer input records: {source}")


def build_matrix(root=ROOT):
    # Read exact existing 20*5 roster, never widen it with unvetted admission units.
    targets=read_research()
    rows={(r["university"],r["year"]):{
         "university":r["university"],"year":r["year"],
         "source_link_found":bool(r["official_guide_url"]),
         "source_link_kind":r["guide_status"],
         "official_subject_weights_found":False,
         "verified_weight_groups":0,
         "full_inquiry_conversion_verified":False,
         "conversion_table_bin_count":0,
         "csat_calculation_validated":False,
         "september_score_transfer_validated":False,
         "actual_application_labels_verified":False,
         "publishable_probability":False,
         "70pct_cutoff_rows":0,
         "missing_requirements":[],
         } for r in targets}
    found=set()
    for path in PARTIALS:
        if path in found: continue
        found.add(path)
        file=root/path
        if not file.exists():continue
        for item in extract_entries(file):
            k=(item.get("university"),item.get("year"))
            if k not in rows:continue
            rows[k]["official_subject_weights_found"]=True
            if item.get("groups") and path.endswith("2025_soongsil_exact_csat.json"):
                rows[k]["verified_weight_groups"]+=len(item["groups"])
            else:
                rows[k]["verified_weight_groups"]+=1
    for path in CUTOFF_FILES:
        f=root/path
        if not f.exists():continue
        for item in extract_entries(f):
            k=(item.get("university"),item.get("year"))
            if k in rows and item.get("probability_label_eligible") is False:
                rows[k]["70pct_cutoff_rows"]+=1
    # Some tables apply to all social/science tests, hence one common "*" column.
    # Only label a table FULL when every integer percentile 0..100 is present.
    con_dir=root/"data/public/conversion_tables"
    tables=defaultdict(set)
    for f in con_dir.glob("pct-*.csv"):
        with f.open(encoding="utf-8-sig",newline="") as io:
            for r in csv.DictReader(io):
                key=(r["university"],int(r["year"]),r["table_id"],r["subject"])
                tables[key].add(int(r["percentile"]))
    for (university,year,_,_),points in tables.items():
        row=rows.get((university,year))
        if row:
            row["conversion_table_bin_count"]+=len(points)
            if len(points)==101 and points==set(range(101)):
                row["full_inquiry_conversion_verified"]=True
    # Explicit program and actual-CSAT-only proof; not a blanket inference.
    ss=rows.get(("숭실대학교",2025))
    if ss and ss["full_inquiry_conversion_verified"] and (
        root/"app/soongsil_2025.py").is_file():
        ss["csat_calculation_validated"]=True
    # No verified September-to-CSAT transfer or 9평/actual-application outcome
    # observations have been attached as verifiable inputs to the pipeline.
    for row in rows.values():
        missing=[]
        if not row["source_link_found"]:missing.append("official_year_guide_link")
        if not row["official_subject_weights_found"]:missing.append("year_specific_subject_weighting")
        if not row["full_inquiry_conversion_verified"]:missing.append("final_inquiry_conversion_table")
        if not row["csat_calculation_validated"]:missing.append("full_csat_calculator_official_examples")
        if not row["september_score_transfer_validated"]:missing.append("validated_september_transfer")
        if not row["actual_application_labels_verified"]:missing.append("consented_actual_application_outcomes")
        row["missing_requirements"]=missing
    results=sorted(rows.values(),key=lambda x:(TOP_20.index(x["university"]),x["year"]))
    if len(results)!=100:raise ValueError("Expected precisely 100 university-year records")
    totals={key:sum(bool(r[key]) for r in results) for key in STATUS_ORDER}
    totals["university_year_pairs"]=len(results)
    totals["total_70pct_cuts"]=sum(r["70pct_cutoff_rows"] for r in results)
    totals["verified_weight_groups"]=sum(r["verified_weight_groups"] for r in results)
    return {
        "schema_version":"1.0","year_range":[2022,2026],
        "purpose":"historical_training_research_not_user_facing",
        "summary":totals,"university_years":results,
        "guardrail":"Link discovery, published enrolled 70% cutoff or one CSAT calculator cannot imply a calibrated September admission forecast."
    }


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    result=build_matrix()
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result["summary"],ensure_ascii=False,sort_keys=True))


if __name__=="__main__":main()
