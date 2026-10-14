"""Build reproducible PUBLIC, precomputed grade-boundary score scenarios.

A grade boundary is NOT a representative score for everyone in that grade.
This pipeline never turns a historical 70%-enrollee cutoff into an admission label.
"""
import csv
import itertools
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from app.scoring import compute
from app.scope import in_scope

ROOT = Path(__file__).resolve().parents[1]
CUT_DIR = ROOT / 'data' / 'public' / 'grade_boundaries'
AREAS = ('korean', 'math', 'inquiry1', 'inquiry2')
EXAM_TYPES = ('june', 'september', 'csat')
# Bounded reference lattice, NOT exhaustive possible scores within each grade.
GRADE_LEVELS = (1, 2, 3)
COLUMNS = {'year', 'exam_type', 'bundle_id', 'area', 'subject', 'grade',
           'std_score_floor', 'percentile_floor', 'kind', 'math_track', 'source_url'}


def load_boundaries(directory=CUT_DIR):
    bundles = defaultdict(dict)
    loaded_files = []
    for path in sorted(Path(directory).glob('*.csv')):
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not COLUMNS.issubset(reader.fieldnames):
                raise ValueError(f'{path}: missing grade-boundary columns')
            for line, row in enumerate(reader, 2):
                try:
                    year, grade = int(row['year']), int(row['grade'])
                    exam, area = row['exam_type'], row['area']
                    if year not in range(2022, 2028) or exam not in EXAM_TYPES or area not in AREAS or grade not in range(1, 10):
                        raise ValueError('invalid year, exam, area or grade')
                    if not row['bundle_id'].strip() or not row['subject'].strip():
                        raise ValueError('missing subject/bundle')
                    if not row['source_url'].startswith('https://'):
                        raise ValueError('official source URL required')
                    if area == 'math' and row['math_track'] not in ('calculus', 'probability', 'geometry'):
                        raise ValueError('math option required')
                    if area.startswith('inquiry') and row['kind'] not in ('science', 'social'):
                        raise ValueError('inquiry kind required')
                    std = float(row['std_score_floor']) if row['std_score_floor'] else None
                    pct = float(row['percentile_floor']) if row['percentile_floor'] else None
                    if std is None and pct is None:
                        raise ValueError('no published numerical boundary')
                    if pct is not None and not 0 <= pct <= 100:
                        raise ValueError('percentile out of range')
                    key = (year, exam, row['bundle_id'].strip())
                    slot = (area, grade)
                    if slot in bundles[key]:
                        raise ValueError('duplicate boundary')
                    bundles[key][slot] = {'std': std, 'pct': pct, 'subject': row['subject'],
                                          'kind': row['kind'], 'math_track': row['math_track'],
                                          'source_url': row['source_url']}
                except (ValueError, TypeError) as error:
                    raise ValueError(f'{path}:{line}: {error}') from error
        loaded_files.append(path.name)
    # The minimum boundary cannot rise when grade gets worse.
    for key, slots in bundles.items():
        for area in AREAS:
            grade_items = sorted((g, v) for (a, g), v in slots.items() if a == area)
            for (_, left), (_, right) in zip(grade_items, grade_items[1:]):
                if left['subject'] != right['subject']:
                    raise ValueError(f'{key}: subject changes within grade series')
                for metric in ('std', 'pct'):
                    if left[metric] is not None and right[metric] is not None and left[metric] < right[metric]:
                        raise ValueError(f'{key}: {area} boundary order is reversed')
    return bundles, loaded_files


def build_dataset(programs, boundary_dir=CUT_DIR, grades=GRADE_LEVELS):
    """No synthetic observations are ever treated as actual admissions."""
    bundles, files = load_boundaries(boundary_dir)
    output = {year: [] for year in range(2022, 2028)}
    skipped = Counter()
    for program in programs:
        year = program['year']
        if not in_scope(program):
            continue
        if not program.get('formula_id') or not program.get('formula_source_url'):
            skipped['unverified_formula'] += 1
            continue
        for (bundle_year, exam, bundle_id), slots in bundles.items():
            if bundle_year != year:
                continue
            # One reusable deterministic cohort/grade scenario per K/M/E/I1/I2 combination.
            for kg, mg, eg, i1g, i2g in itertools.product(grades, repeat=5):
                by_area = {'korean': kg, 'math': mg, 'inquiry1': i1g, 'inquiry2': i2g}
                samples = {area: slots.get((area, grade)) for area, grade in by_area.items()}
                if any(value is None or (value['pct'] is None and value['std'] is None) for value in samples.values()):
                    skipped['missing_published_percentile_boundary'] += 1
                    continue
                math_opt = samples['math']['math_track']
                if math_opt not in ('calculus', 'probability', 'geometry'):
                    skipped['missing_math_option'] += 1
                    continue
                student = {'korean_pct': samples['korean']['pct'],
                           'korean_std': samples['korean']['std'],
                           'math_pct': samples['math']['pct'],
                           'math_std': samples['math']['std'],
                           'english_grade': eg, 'history_grade': 1,
                           'math_track': math_opt,
                           'inquiries': [{'pct': samples[area]['pct'], 'std':samples[area]['std'],
                                          'kind': samples[area]['kind'],
                                          'name': samples[area]['subject']}
                                         for area in ('inquiry1', 'inquiry2')]}
                score = compute(student, program)
                if score is None:
                    skipped['unsupported_formula'] += 1
                    continue
                # Strictly EX-POST, same-exam year; not a true decision boundary or pass label.
                cutoff = program.get('cutoff_70') if exam == 'csat' and program.get('cutoff_source_url') else None
                margin = round(score.total - float(cutoff), 3) if cutoff is not None else None
                output[year].append({
                    'year': year, 'exam_type': exam, 'university': program['university'],
                    'department': program['department'], 'program_key': program['program_key'],
                    'bundle_id': bundle_id, 'grade_profile': f'{kg}-{mg}-{eg}-{i1g}-{i2g}',
                    'grades': {'korean': kg, 'math': mg, 'english': eg, 'inquiry1': i1g, 'inquiry2': i2g},
                    'subjects': {area: samples[area]['subject'] for area in AREAS},
                    'reference': 'published_grade_lower_bound_not_typical_score',
                    'converted_score': round(score.total, 3), 'score_scale': score.score_scale,
                    'historical_70pct_cutoff': cutoff, 'retrospective_margin': margin,
                    'assessment': 'retrospective_70pct_comparison' if margin is not None else 'score_only',
                    'admitted': None, 'admission_probability': None,
                    'formula_source_url': program['formula_source_url'],
                    'cutoff_source_url': program.get('cutoff_source_url') if margin is not None else None,
                    'grade_cut_sources': sorted({v['source_url'] for v in samples.values()}),
                })
    summary = {
        'schema_version': '1.0', 'grade_levels': list(grades),
        'reference_definition': '각 과목 확정 등급의 하한 경계값 조합 (등급 전체의 대표값 아님)',
        'assessment_definition': '동일 학년도 최종등록자 70%컷과 사후 비교; 실측 합불이나 합격확률 아님',
        'boundary_csv_files': files,
        'bundle_count': len(bundles),
        'records_by_year': {str(y): len(rows) for y, rows in output.items()},
        'skipped': dict(skipped),
        'official_person_level_outcomes': 0,
    }
    return output, summary
