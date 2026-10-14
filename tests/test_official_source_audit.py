from scripts.audit import run
def test_2025_soongsil_source_and_cutoff_audit_separates_csat_from_september():
    r=run()
    assert r['historical_research_non_KHU_70pct_cut_count']==52
    assert r['historical_2025_soongsil_actual_conversion_percentiles']==101
    assert r['historical_actual_csat_calculator_count']==1
    assert r['historical_september_adjusted_calculator_count']==0
    assert r['historical_official_research']['historical_admission_cut_rows']==20
