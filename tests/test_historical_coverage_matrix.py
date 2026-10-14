from scripts.historical_coverage_matrix import build_matrix

def test_all_20_universities_and_five_historical_years_are_covered():
    m=build_matrix()
    rows=m["university_years"]
    assert len(rows)==100
    assert len(set((r["university"],r["year"]) for r in rows))==100
    assert {r["year"] for r in rows}=={2022,2023,2024,2025,2026}
    assert m["summary"]["university_year_pairs"]==100
    assert m["summary"]["source_link_found"]==97

def test_actual_training_data_never_inferred_from_separate_cutoffs():
    m=build_matrix()
    assert m["summary"]["total_70pct_cuts"]==72
    assert m["summary"]["actual_application_labels_verified"]==0
    assert m["summary"]["publishable_probability"]==0
    assert all(not row["september_score_transfer_validated"] for row in m["university_years"])
    assert all(row["70pct_cutoff_rows"]==0 or
        "consented_actual_application_outcomes" in row["missing_requirements"]
        for row in m["university_years"])

def test_soongsil_csat_calculator_is_not_marked_as_september_prediction():
    rows=build_matrix()["university_years"]
    target=next(x for x in rows if x["university"]=="숭실대학교" and x["year"]==2025)
    assert target["conversion_table_bin_count"]==101
    assert target["full_inquiry_conversion_verified"] is True
    assert target["csat_calculation_validated"] is True
    assert target["september_score_transfer_validated"] is False
    assert target["publishable_probability"] is False

def test_year_specific_partial_weights_are_not_projected_to_other_years():
    rows=build_matrix()["university_years"]
    inha2026=next(x for x in rows if x["university"]=="인하대학교" and x["year"]==2026)
    inha2022=next(x for x in rows if x["university"]=="인하대학교" and x["year"]==2022)
    assert inha2026["official_subject_weights_found"] is True
    assert inha2022["official_subject_weights_found"] is False
