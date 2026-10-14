"""Offline, distribution-only September to CSAT standard-score adjustment.

No student rows, no longitudinal student gains, no admission probabilities.
Only reviewed official per-score frequencies belong in the input directory.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median, mean

ROOT = Path(__file__).resolve().parents[1]
FREQUENCIES = ROOT / 'data' / 'public' / 'score_frequencies'
COLUMNS = {'year', 'exam_type', 'subject', 'option_name', 'std_score',
           'examinee_count', 'source_url'}
QUANTILES = (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
             0.60, 0.70, 0.80, 0.90, 0.95, 0.99)
MIN_HISTORICAL_YEARS = 3


@dataclass(frozen=True)
class Distribution:
    frequencies: dict[int, int]
    source_urls: tuple[str, ...]

    @property
    def total(self):
        return sum(self.frequencies.values())

    def quantile(self, p):
        if not 0 <= p <= 1:
            raise ValueError('quantile must be within [0,1]')
        rank = max(1, math.ceil(p * self.total))
        cumulative = 0
        for score, count in sorted(self.frequencies.items()):
            cumulative += count
            if cumulative >= rank:
                return score
        raise AssertionError('nonempty distribution required')

    def midrank(self, score):
        """Estimated cumulative percentile with half-weight for ties."""
        below = sum(n for s, n in self.frequencies.items() if s < score)
        at = self.frequencies.get(score, 0)
        return (below + at / 2) / self.total


def read_frequencies(directory=FREQUENCIES):
    groups = defaultdict(dict)
    provenance = defaultdict(set)
    paths = sorted(Path(directory).glob('*.csv'))
    for path in paths:
        with path.open('r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not COLUMNS.issubset(reader.fieldnames):
                raise ValueError(f'{path}: required columns missing')
            for index, r in enumerate(reader, 2):
                try:
                    year = int(r['year'])
                    exam = r['exam_type'].strip()
                    subject = r['subject'].strip()
                    option = r['option_name'].strip() or 'all'
                    score = int(r['std_score'])
                    count = int(r['examinee_count'])
                    url = r['source_url'].strip()
                    if year not in range(2022, 2028) or exam not in ('september', 'csat'):
                        raise ValueError('unsupported year / exam type')
                    if year == 2027 and exam == 'csat':
                        raise ValueError('2027 CSAT not yet administered')
                    if not subject or not 0 <= score <= 250 or count <= 0:
                        raise ValueError('invalid subject, score or count')
                    if not url.startswith('https://'):
                        raise ValueError('source URL must use HTTPS')
                    key = (year, exam, subject, option)
                    if score in groups[key]:
                        raise ValueError('duplicate score bin')
                    groups[key][score] = count
                    provenance[key].add(url)
                except (ValueError, TypeError) as error:
                    raise ValueError(f'{path}:{index}: {error}') from error
    result = {key: Distribution(values, tuple(sorted(provenance[key])))
              for key, values in groups.items()}
    return result, [p.name for p in paths]


def forecast(distributions, *, target_year=2027, min_history=MIN_HISTORICAL_YEARS):
    """Forecast score distribution given stability of within-exam rank.

    Historical shifts are quantile-curve differences, NOT within-student gains.
    The min-max interval is a historical shift range, NOT a confidence interval.
    """
    results = []
    target = [(key, dist) for key, dist in distributions.items()
              if key[0] == target_year and key[1] == 'september']
    for (_, _, subject, option), current in sorted(target):
        history = []
        for year in range(2022, target_year):
            sep = distributions.get((year, 'september', subject, option))
            csat = distributions.get((year, 'csat', subject, option))
            if sep is not None and csat is not None:
                history.append((year, sep, csat))
        row = {
            'subject': subject, 'option_name': option, 'reference_exam': 'september',
            'reference_year': target_year, 'reference_n': current.total,
            'historical_pairs': [h[0] for h in history],
            'reference_sources': list(current.source_urls), 'quantiles': [],
            'status': 'ready' if len(history) >= min_history else 'insufficient_paired_years',
            'admission_probability': None,
        }
        if len(history) >= min_history:
            last = 0
            for p in QUANTILES:
                sep_score = current.quantile(p)
                shifts = [csat.quantile(p) - sep.quantile(p) for _, sep, csat in history]
                median_shift = float(median(shifts))
                forecast_score = max(last, max(0, min(250, sep_score + median_shift)))
                last = forecast_score
                row['quantiles'].append({
                    'cumulative_percentile': round(100 * p, 1),
                    'september_std_score': sep_score,
                    'projected_csat_std_score': round(forecast_score, 1),
                    'historical_shift_median': round(median_shift, 1),
                    'historical_shift_min': min(shifts),
                    'historical_shift_max': max(shifts),
                })
        results.append(row)
    return results


def walk_forward_backtest(distributions):
    """2025 and 2026 score-curve holdout evaluations if previous years exist."""
    checks = []
    subjects = sorted({(k[2], k[3]) for k in distributions})
    for subject, option in subjects:
        for year in range(2025, 2027):
            actual = distributions.get((year, 'csat', subject, option))
            prior = {key: val for key, val in distributions.items() if key[0] < year}
            current = distributions.get((year, 'september', subject, option))
            if actual is None or current is None:
                continue
            input_distributions = {**prior, (year, 'september', subject, option): current}
            rows = forecast(input_distributions, target_year=year)
            matched = next((r for r in rows if r['subject'] == subject and r['option_name'] == option), None)
            if not matched or matched['status'] != 'ready':
                checks.append({'year': year, 'subject': subject, 'option_name': option,
                               'status': 'insufficient_paired_years'})
                continue
            errors = [abs(q['projected_csat_std_score'] - actual.quantile(q['cumulative_percentile']/100))
                      for q in matched['quantiles']]
            checks.append({'year': year, 'subject': subject, 'option_name': option,
                           'status': 'evaluated', 'quantile_mae_std_points': round(mean(errors), 2),
                           'historical_training_years': matched['historical_pairs']})
    return checks


def make_snapshot(directory=FREQUENCIES):
    distributions, files = read_frequencies(directory)
    # Public builds must fail closed if a CSV slice has no documented total/XLSX approval.
    if Path(directory).resolve() == FREQUENCIES.resolve():
        from scripts.source_inventory import assert_approved_distributions
        assert_approved_distributions(distributions)
    predictions = forecast(distributions)
    backtests = walk_forward_backtest(distributions)
    return {
        'schema_version': '1.0', 'method': 'historical_paired_exam_quantile_shift_median',
        'reference_year': 2027, 'reference_exam': 'september',
        'input_csv_files': files, 'distribution_count': len(distributions),
        'ready_subject_count': sum(r['status'] == 'ready' for r in predictions),
        'subjects': predictions, 'backtests': backtests,
        'student_records_stored': False, 'admission_probabilities_validated': False,
        'interpretation': (
            '과거 9평과 수능의 같은 전국 분위 위치에서 나타난 표준점수 분포 차이를 '
            '2027년 9평에 적용한 조건부 추정. 동일 학생의 성적 변화가 아님.'
        ),
        'uncertainty_note': '표시하는 과거 이동폭 최소·최대는 신뢰구간이 아닙니다.',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', default=str(FREQUENCIES))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot = make_snapshot(args.input_dir)
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print('Public distributions:', snapshot['distribution_count'],
          '2027 forecastable subjects:', snapshot['ready_subject_count'])

if __name__ == '__main__':
    main()
