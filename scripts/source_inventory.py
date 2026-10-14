"""Official KICE/MOE release-page inventory. Release located != numeric rows verified."""
from __future__ import annotations
import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data/public/official_sources.json"
FREQUENCIES = ROOT / "data/public/score_frequencies"
APPROVALS = FREQUENCIES / "approved_distributions.json"

def load_sources(path=SOURCES):
    entries = json.loads(Path(path).read_text(encoding="utf-8"))
    expected={(y,"september") for y in range(2022,2028)} | {(y,"csat") for y in range(2022,2027)}
    found=set()
    for row in entries:
        key=(row["year"],row["exam_type"])
        if key not in expected or key in found:
            raise ValueError(f"Unexpected or duplicate official release: {key}")
        found.add(key)
        url=row["source_page"]
        parsed=urlparse(url)
        if parsed.scheme!="https" or parsed.netloc not in {"www.moe.go.kr","eiec.kdi.re.kr"}:
            raise ValueError(f"Unsupported publication source: {url}")
        if row["attachment_status"] not in ("listed_xlsx","release_only"):
            raise ValueError("Invalid attachment verification status")
        if row["review_status"]!="release_page_located":
            raise ValueError("Release-page catalogue is not an ingestion ledger")
    if found!=expected:
        raise ValueError(f"Missing release entries: {sorted(expected-found)}")
    return sorted(entries,key=lambda r:(r["year"],r["exam_type"]))

def assert_approved_distributions(groups, approvals_file=APPROVALS, sources_file=SOURCES):
    """Only complete, separately checked frequency distributions can reach Pages."""
    approvals=json.loads(Path(approvals_file).read_text(encoding="utf-8"))
    source_map={(r["year"],r["exam_type"]):r["source_page"] for r in load_sources(sources_file)}
    expected=set(groups)
    approved=set()
    for item in approvals:
        key=(item["year"],item["exam_type"],item["subject"],item["option_name"])
        if key in approved or key not in expected:
            raise ValueError(f"Approval does not match exactly one distribution: {key}")
        approved.add(key)
        if item["source_page"]!=source_map.get(key[:2]):
            raise ValueError("Approval source must match its year/exam publication")
        if not re.fullmatch(r"[a-f0-9]{64}",item["attachment_sha256"]):
            raise ValueError("Approval requires XLSX SHA-256")
        if not item["reviewer"].strip() or len(item["reviewer"].strip())<2:
            raise ValueError("Approval requires a reviewer")
        date.fromisoformat(item["checked_on"])
        n=item["expected_total_examinees"]
        if type(n) is not int or n<=0 or groups[key].total!=n:
            raise ValueError(f"Official participant total disagrees with extracted frequency bins: {key}")
        if set(groups[key].source_urls)!={item["source_page"]}:
            raise ValueError("Frequency CSV provenance does not match reviewed source")
    if expected!=approved:
        raise ValueError("Unapproved official score distribution(s): "+str(sorted(expected-approved)))
    return len(approved)

def build_report(source_file=SOURCES, frequency_dir=FREQUENCIES):
    entries=load_sources(source_file)
    from scripts.score_adjustment import read_frequencies
    groups,files=read_frequencies(frequency_dir)
    if Path(frequency_dir).resolve()==FREQUENCIES.resolve():
        assert_approved_distributions(groups)
    available={(k[0],k[1]) for k in groups}
    return {"version":1,"meaning":"official_release_locations_not_verified_numeric_data",
            "release_pages_found":len(entries),
            "xlsx_attachments_listed":sum(r["attachment_status"]=="listed_xlsx" for r in entries),
            "imported_distribution_groups":len(groups),"imported_frequency_csv_files":files,
            "entries":[dict(r,numeric_data_imported=((r["year"],r["exam_type"]) in available)) for r in entries],
            "warning":"공식 보도자료 원문 위치 확인은 엑셀 수치 추출 또는 검증 완료와 다릅니다."}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="official-source-status.json")
    a=ap.parse_args()
    result=build_report()
    path=Path(a.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Located release pages:",result["release_pages_found"],
          "approved distributions:",result["imported_distribution_groups"])

if __name__=="__main__":
    main()
