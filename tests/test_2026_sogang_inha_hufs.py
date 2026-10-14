"""2026 standalone historical A/B subject weight groups from official Adiga notices."""
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/public/university_research/2026_sogang_inha_hufs_partial.json"

def test_sogang_inha_hufs_2026_groups_and_ab_types():
    x=json.loads(P.read_text(encoding="utf-8"))
    rows=x["groups"]
    assert x["year"]==2026 and len(rows)==11
    assert {r["university"] for r in rows}=={"서강대학교","인하대학교","한국외국어대학교"}
    assert all(not r["fully_computable"] and r["missing"]
      and r["source_url"].startswith("https://www.adiga.kr/") for r in rows)
    for r in rows:
        if "weights" in r:
            assert abs(sum(r["weights"].values())-1)<1e-8
        else:
            assert abs(sum(r["normalized_relative_weights"].values())-1)<1e-8
    sogang=[r for r in rows if r["university"]=="서강대학교"]
    assert len(sogang)==2
    assert sogang[0]["best_of_types"] is True
    assert {r["group"] for r in sogang}=={"전 계열 수능 A형","전 계열 수능 B형"}
    han=next(r for r in rows if r["university"]=="한국외국어대학교" and r["group"]=="일반 인문 B")
    assert han["weights"]=={"korean":.30,"math":.35,"english":.15,"inquiry":.20}
    natural=next(r for r in rows if r["university"]=="인하대학교" and r["group"]=="일반 자연계열")
    assert natural["weights"]=={"korean":.25,"math":.35,"english":.10,"inquiry":.30}
