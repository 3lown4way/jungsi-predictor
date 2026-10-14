"""Check privacy and reproducibility of offline mock-support snapshots."""
import csv
import json
from types import SimpleNamespace

import pytest
from scripts.batch_cohort import FIELDS, build_snapshot, read_private_submissions


def program():
    return {'year': 2027, 'program_key': 'unit-test-med',
            'university': '서울대학교', 'department': '의예과', 'round': '나',
            'formula_id': 'test-formula', 'formula_source_url': 'https://example.org/official'}


def private_csv(tmp_path, count=35, duplicate=False):
    path = tmp_path / 'private.csv'
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=sorted(FIELDS))
        writer.writeheader()
        for i in range(count):
            writer.writerow({'submission_id': f'opaque-student-{0 if duplicate else i:04d}',
                'year': 2027, 'exam_type': 'september', 'program_key': 'unit-test-med',
                'korean_pct': 90 + i % 5, 'math_pct': 91 + i % 5,
                'math_track': 'calculus', 'english_grade': 1, 'history_grade': 1,
                'inquiry1_pct': 90, 'inquiry1_kind': 'social', 'inquiry1_name': '사회·문화',
                'inquiry2_pct': 92, 'inquiry2_kind': 'social',
                'inquiry2_name': '생활과 윤리', 'consented': 1})
    return path


def fake_score(student, prog):
    return SimpleNamespace(total=student['korean_pct'] * 10)


def test_public_only_aggregate(tmp_path):
    submissions = read_private_submissions(private_csv(tmp_path))
    output = build_snapshot(submissions, [program()], scorer=fake_score)
    assert output['published_programs'] == 1
    row = output['predictions'][0]
    assert row['participant_count_band'] == '30–49'
    assert row['admission_probability'] is None
    assert row['score_p25'] <= row['score_p50'] <= row['score_p75']
    assert 'opaque-student-' not in json.dumps(output, ensure_ascii=False)
    assert 'korean_pct' not in json.dumps(output)


def test_groups_under_30_not_public(tmp_path):
    output = build_snapshot(read_private_submissions(private_csv(tmp_path, 29)),
                            [program()], scorer=fake_score)
    assert output['predictions'] == []


def test_duplicate_rejected(tmp_path):
    with pytest.raises(ValueError, match='duplicate'):
        read_private_submissions(private_csv(tmp_path, duplicate=True))


def test_unverified_formula_skipped(tmp_path):
    p = program()
    p['formula_id'] = None
    output = build_snapshot(read_private_submissions(private_csv(tmp_path)),
                            [p], scorer=fake_score)
    assert not output['predictions']


def test_threshold_cannot_be_lowered():
    with pytest.raises(ValueError, match='at least 30'):
        build_snapshot([], [], min_group=5)
