"""A link to a release is not a validated frequency dataset."""
import json
import pytest
from scripts.source_inventory import load_sources,build_report,assert_approved_distributions
from scripts.score_adjustment import Distribution

def test_official_source_registry_complete():
    rows=load_sources()
    assert len(rows)==11
    assert {(r["year"],r["exam_type"]) for r in rows}==(
        {(y,"september") for y in range(2022,2028)} |
        {(y,"csat") for y in range(2022,2027)})
    report=build_report()
    assert report["imported_distribution_groups"]==25
    sep=[row for row in report["entries"] if (row["year"],row["exam_type"])==(2027,"september")]
    assert sep[0]["numeric_data_imported"] is True
    assert all(not row["numeric_data_imported"] for row in report["entries"] if (row["year"],row["exam_type"])!=(2027,"september"))

def test_missing_release_rejected(tmp_path):
    rows=load_sources()[:-1]
    f=tmp_path/"partial.json"
    f.write_text(json.dumps(rows,ensure_ascii=False))
    with pytest.raises(ValueError,match="Missing release"):
        load_sources(f)

def test_unapproved_score_bins_rejected(tmp_path):
    url="https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=294&boardSeq=107307&lev=0&m=020402"
    groups={(2027,"september","국어","all"):Distribution({120:15,121:15},(url,))}
    file=tmp_path/"approved.json"
    file.write_text("[]")
    with pytest.raises(ValueError,match="Unapproved"):
        assert_approved_distributions(groups,file)
    entry=dict(year=2027,exam_type="september",subject="국어",option_name="all",
               source_page=url,attachment_sha256="a"*64,reviewer="reviewer",
               checked_on="2026-10-14",expected_total_examinees=31)
    file.write_text(json.dumps([entry],ensure_ascii=False))
    with pytest.raises(ValueError,match="total disagrees"):
        assert_approved_distributions(groups,file)
    entry["expected_total_examinees"]=30
    file.write_text(json.dumps([entry],ensure_ascii=False))
    assert assert_approved_distributions(groups,file)==1


def test_2027_september_25_complete_distributions():
    from scripts.score_adjustment import read_frequencies,make_snapshot
    groups,_=read_frequencies()
    assert len(groups)==25
    k=groups[(2027,"september","국어","all")]
    m=groups[(2027,"september","수학","all")]
    assert (k.total,k.frequencies[144])==(393751,75)
    assert (m.total,m.frequencies[137])==(390456,2741)
    snap=make_snapshot()
    assert snap["distribution_count"]==25
    assert snap["ready_subject_count"]==0
    assert all(r["status"]=="insufficient_paired_years" and r["admission_probability"] is None for r in snap["subjects"])
