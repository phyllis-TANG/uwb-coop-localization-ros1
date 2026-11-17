#!/usr/bin/env python3
"""Read saved CSV/JSON only. No localization, optimization, simulation or resampling.
Run at any cwd: python3 path/to/evidence/verify_sources.py > /tmp/c-evidence-check.json
"""
import csv
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DELIVERY = HERE.parent
REPO = HERE.parents[3]
checks = []
manifest = json.loads((HERE / 'SOURCE_COPIES.json').read_text())
for item in manifest['copies']:
    data = (DELIVERY / item['delivery_file']).read_bytes()
    assert len(data) == item['bytes']
    assert hashlib.sha256(data).hexdigest() == item['sha256']
checks.append({'check': 'exact_source_copy_hashes', 'files': len(manifest['copies']), 'status': 'PASS'})

def read_rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))

def one(rows, **criteria):
    chosen = [r for r in rows if all(r[k] == str(v) for k, v in criteria.items())]
    assert len(chosen) == 1, (criteria, len(chosen))
    return chosen[0]

noise = read_rows(HERE / 'pr108/noise/COVERAGE.csv.gz')
fault = read_rows(HERE / 'pr108/fault/COVERAGE.csv.gz')
assert len(noise) == len(fault) == 110592
r = one(noise, id='n32', method='B2', view='C_true_noise', car=1, level='0.95', subset='all', aggregation='point_average')
assert (r['covered'], r['planned'], r['available'], r['selected_seeds']) == ('221', '300', '300', '50')
assert abs(float(r['coverage_available']) - 221 / 300) < 1e-14
checks.append({'check': 'PR108_n32', 'covered': 221, 'planned_points': 300, 'independent_seeds': 50, 'coverage': float(r['coverage_available']), 'status': 'PASS'})
for injection in ['wrong_link', 'multi_link']:
    chosen = [r for r in fault if r['method'] == 'B2' and r['view'] == 'A_total' and r['car'] == '1' and r['level'] == '0.95' and r['subset'] == 'all' and r['aggregation'] == 'point_average' and r['injection'] == injection]
    assert len(chosen) == 12
    assert all(r['covered'] == '0' and r['planned'] == '600' and r['selected_seeds'] == '100' for r in chosen)
    checks.append({'check': 'PR108_' + injection, 'conditions': 12, 'covered_per_condition': 0, 'points_per_condition': 600, 'independent_seeds_per_condition': 100, 'status': 'PASS'})

prior_root = REPO / 'docs/research/midterm_prior_mechanism_b/results'
coverage = read_rows(prior_root / 'COVERAGE.csv')
summary = read_rows(prior_root / 'SUMMARY.csv')
for sigma, mechanism, expected in [('0.5', 'fixed_correct', [544, 537]), ('0.05', 'fixed_survey', [11, 60])]:
    for car, count in enumerate(expected, 1):
        r = one(coverage, geometry='weak', bias_m='0.3', prior_sigma=sigma, mechanism=mechanism, method='B2', model='nonlinear', car=car, view='curvature', level='0.95', subset='all', aggregation='point_average')
        assert (r['covered'], r['planned']) == (str(count), '600')
        checks.append({'check': f'PR109_{mechanism}_{sigma}_car{car}', 'covered': count, 'planned_points': 600, 'independent_seeds': 100, 'coverage': float(r['coverage']), 'status': 'PASS'})
r = one(summary, geometry='weak', bias_m='0.3', prior_sigma='0.05', mechanism='fixed_survey', method='B2', model='nonlinear')
assert r['accepted'] == r['planned'] == '100'
counts = json.loads((prior_root / 'COUNTS.json').read_text())
assert counts['nonlinear']['planned'] == counts['nonlinear']['completed'] == 14400
assert counts['truth_linearized']['planned'] == counts['truth_linearized']['completed'] == 14400
assert counts['nonlinear']['categories'] == {'ACCEPTED': 14335, 'NOT_STATIONARY': 65}
# Pick one nominal level and the point-average aggregate only: no double counting
# across 95/99, time rows, trajectory rows or numerical subsets.
selected = [r for r in coverage if r['level'] == '0.95' and r['subset'] == 'all' and r['aggregation'] == 'point_average']
assert sum(int(r['planned']) for r in selected) == 691200
assert sum(int(r['unavailable']) for r in selected) == 6400
checks.append({'check': 'PR109_counts_and_singular_blocks', 'nonlinear': 14400, 'truth_linearized_diagnostics': 14400, 'not_stationary': 65, 'planned_blocks': 691200, 'unavailable_blocks': 6400, 'status': 'PASS'})
claims = read_rows(DELIVERY / 'CLAIM_EVIDENCE.csv')
assert len({r['claim_id'] for r in claims}) == len(claims)
assert all(len(r['fixed_commit']) == 40 and r['source_url'].endswith(r['table_figure_or_line'].split(';')[0]) for r in claims)
checks.append({'check': 'claim_ids_and_fixed_commit_urls', 'claims': len(claims), 'status': 'PASS'})
print(json.dumps({'status': 'PASS', 'localization_runs': 0, 'new_random_samples': 0, 'checks': checks}, ensure_ascii=False, indent=2))
