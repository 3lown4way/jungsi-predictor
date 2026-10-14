"""Synthetic test distributions only. Never publish fixtures as real official score curves."""
import csv

import pytest
from scripts.score_adjustment import (COLUMNS, Distribution, forecast,
                                      read_frequencies, make_snapshot, walk_forward_backtest)


def create_fixture(path, include_current=True):
    path.mkdir(parents=True, exist_ok=True)
    with (path/'fake_for_tests_only.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=sorted(COLUMNS))
        w.writeheader()
        for year in range(2022, 2028 if include_current else 2027):
            for exam in ('september', 'csat'):
                if year == 2027 and exam == 'csat':
                    continue
                for score in (90, 100, 110, 120, 130):
                    w.writerow({'year': year, 'exam_type':exam,'subject':'수학',
                                'option_name':'all', 'std_score':score+(2 if exam=='csat' else 0),
                                'examinee_count':100, 'source_url':'https://example.org/synthetic-test'})


def test_quantile_and_tied_score_midrank():
    d = Distribution({100:4, 110:6}, ('https://example.org',))
    assert d.quantile(0.4) == 100
    assert d.quantile(0.41) == 110
    assert d.midrank(100) == 0.2
    assert d.midrank(110) == 0.7


def test_forecast_and_year_forward_validation(tmp_path):
    create_fixture(tmp_path)
    d, files = read_frequencies(tmp_path)
    result = forecast(d)
    assert len(result) == 1
    assert result[0]['status'] == 'ready'
    assert result[0]['historical_pairs'] == [2022,2023,2024,2025,2026]
    assert all(q['projected_csat_std_score'] == q['september_std_score'] + 2 for q in result[0]['quantiles'])
    backtests = walk_forward_backtest(d)
    assert [t['year'] for t in backtests] == [2025,2026]
    assert all(t['quantile_mae_std_points'] == 0 for t in backtests)
    snap = make_snapshot(tmp_path)
    assert snap['student_records_stored'] is False
    assert snap['admission_probabilities_validated'] is False
    assert snap['ready_subject_count'] == 1


def test_absent_current_distribution_reports_no_prediction(tmp_path):
    create_fixture(tmp_path, include_current=False)
    snap = make_snapshot(tmp_path)
    assert snap['ready_subject_count'] == 0
    assert snap['subjects'] == []


def test_cannot_use_future_csat_or_duplicate_bins(tmp_path):
    create_fixture(tmp_path)
    csv_file = tmp_path/'fake_for_tests_only.csv'
    content = csv_file.read_text()
    with csv_file.open('a', newline='') as f:
        csv.DictWriter(f, fieldnames=sorted(COLUMNS)).writerow({'year':2027,'exam_type':'csat','subject':'수학','option_name':'all','std_score':160,'examinee_count':100,'source_url':'https://example.org/future'})
    with pytest.raises(ValueError, match='2027 CSAT'):
        read_frequencies(tmp_path)
    csv_file.write_text(content)
    with csv_file.open('a', newline='') as f:
        csv.DictWriter(f, fieldnames=sorted(COLUMNS)).writerow({'year':2022,'exam_type':'csat','subject':'수학','option_name':'all','std_score':92,'examinee_count':100,'source_url':'https://example.org/duplicate'})
    with pytest.raises(ValueError, match='duplicate'):
        read_frequencies(tmp_path)


def test_unpaired_years_do_not_produce_estimated_scores(tmp_path):
    create_fixture(tmp_path)
    d,_ = read_frequencies(tmp_path)
    only_current = {k:v for k,v in d.items() if k[0] == 2027 or k[0] == 2026}
    r = forecast(only_current)[0]
    assert r['status'] == 'insufficient_paired_years'
    assert r['quantiles'] == []
