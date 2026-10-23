#!/usr/bin/env python3
"""Three confidence strategies crossed with the near-zero-Odom switch."""
import argparse
import copy
import csv
import json
import os
from pathlib import Path
import platform
import sys

import numpy as np
import scipy

from run_two_car_updated_comparison import fingerprint, write_csv, write_json
from run_two_car_stationary_confidence import evaluate
from two_car_updated_comparison import CARS, build_inputs, read_bag, sha256
from two_car_stationary_confidence import PolicyObjective, near_zero_edges, read_odom_motion
from two_car_range_confidence import AdaptiveObjective, predict_confidence, solve_objective

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT/'docs/field_tests/two_car_range_diagnostics_20261023'


def confidence_rows(case, kind, inputs, confidence):
    rows = []
    for name, values in confidence.items():
        for row in values:
            item = dict(case=case, kind=kind, factor=name, **row)
            if name == 'peer':
                directions = inputs['peers'][row['epoch']]['directions_m']
                item['peer_direction_difference_m'] = directions[0]-directions[1] if None not in directions else None
            else: item['peer_direction_difference_m'] = None
            rows.append(item)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=DOCS/'protocol.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dependency-path', type=Path)
    args = parser.parse_args()
    if args.dependency_path: sys.path.append(str(args.dependency_path.resolve()))
    if any(os.environ.get(k) != '1' for k in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS']):
        raise ValueError('Set BLAS and OMP threads to 1')
    protocol = json.loads(args.protocol.read_text())
    parent = json.loads((ROOT/protocol['parent_protocol_path']).read_text())
    previous_policy = json.loads((ROOT/protocol['parent_policy_protocol_path']).read_text())
    fixed = json.loads((ROOT/protocol['frozen_fixed_scales_path']).read_text())
    plan = json.loads((DOCS/'diagnostic_plan.json').read_text())
    sources = ['two_car_range_confidence.py', 'run_two_car_range_confidence.py',
        'test_two_car_range_confidence.py', 'diagnose_two_car_ranges.py',
        'two_car_stationary_confidence.py', 'run_two_car_stationary_confidence.py',
        'two_car_updated_comparison.py', 'single_car_fixed_lag.py', 'single_car_sequential_replay.py']
    before = {name: sha256(ROOT/'tools'/name) for name in sources}
    phash = sha256(args.protocol)
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/'protocol.json', protocol)
    rows, trajectories, table, results = [], [], [], []
    cfg = dict(correction='per_car', peer_sigma_m=.2, withheld_wall_car=None, car2_peer_shift_s=0.)
    # Static runs are instruments only. Known coordinates enter as start priors,
    # provisional zero heading, not as a repeated coordinate constraint.
    for case in plan['static_cases']:
        run = read_bag(ROOT/case['path'], case['sha256'])
        model_case = dict(start_antenna_xyz_m=case['antenna_xyz_m'], initial_heading_deg={c: 0. for c in CARS})
        inputs = build_inputs(run, model_case, parent, cfg, fixed['biases_m'])
        confidence = predict_confidence(inputs, protocol['new_policy'])
        rows.extend(confidence_rows(case['id'], 'static_diagnostic', inputs, confidence))
    oldroot = ROOT/'docs/field_tests/two_car_stationary_confidence_20261023/results'
    with (oldroot/'trajectories.csv').open() as stream:
        previous = {(r['case'], r['configuration'], r['method'], r['car'], float(r['elapsed_s'])): r
                    for r in csv.DictReader(stream)}
    mapping = dict(original='baseline', original_stationary='stationary_only',
                   fixed='confidence_only', fixed_stationary='combined')
    reproduction_max = 0.
    for case in parent['cases']:
        if case['id'] not in protocol['cases']: continue
        run = read_bag(ROOT/case['path'], case['sha256'])
        model_case = {k: copy.deepcopy(case[k]) for k in ['start_antenna_xyz_m', 'initial_heading_deg']}
        inputs = build_inputs(run, model_case, parent, cfg, fixed['biases_m'])
        motion = read_odom_motion(ROOT/case['path'], case['sha256'])
        masks = {c: near_zero_edges(motion[c], inputs['times'], previous_policy['detector'])[0] for c in CARS}
        confidence = predict_confidence(inputs, protocol['new_policy'])
        confidence_hash = fingerprint(confidence)
        rows.extend(confidence_rows(case['id'], 'dynamic_development', inputs, confidence))
        target = args.output/case['id']; target.mkdir()
        write_json(target/'confidence.json', confidence)
        write_json(target/'inputs.json', inputs)
        result = dict(case=case['id'], stationary_car=case['stationary_car'],
            confidence_sha256=confidence_hash, configurations={})
        input_hash = fingerprint(inputs)
        for configuration in protocol['configurations']:
            name = configuration['id']; pair = {}
            for method, joint in [('independent', False), ('joint', True)]:
                if configuration['strategy'] == 'adaptive':
                    objective = AdaptiveObjective(inputs, joint, configuration['stationary_covariance'],
                        masks, fixed['scales'], previous_policy['detector'], confidence)
                else:
                    objective = PolicyObjective(inputs, joint, dict(
                        stationary_covariance=configuration['stationary_covariance'],
                        range_confidence=configuration['strategy']=='fixed'), masks,
                        fixed['scales'], previous_policy['detector'])
                fit = solve_objective(inputs, objective, parent['optimizer'])
                if fingerprint(inputs) != input_hash or fingerprint(confidence) != confidence_hash:
                    raise AssertionError('Solver mutated input or precomputed confidence')
                metrics = evaluate(inputs, fit, objective, masks, case)
                pair[method] = metrics
                for ci, car in enumerate(CARS):
                    table.append(dict(case=case['id'], configuration=name, method=method, car=car,
                        endpoint_difference_m=metrics['endpoint_difference_m'][car],
                        antenna_path_m=metrics['cars'][car]['estimated_antenna_path_m'],
                        start_prior_shift_m=metrics['cars'][car]['start_antenna_prior_displacement_m'],
                        wall_factors=fit['wall_factor_count'], peer_factors=fit['peer_factor_count'],
                        nfev=fit['optimizer']['nfev'], solve_wall_s=fit['optimizer']['solve_wall_s']))
                    for i, stamp in enumerate(inputs['times']):
                        pose, xy = fit['states'][ci, i], fit['antenna_xy'][ci, i]
                        row = dict(case=case['id'], configuration=name, method=method, car=car,
                            elapsed_s=float(stamp), base_x_m=float(pose[0]), base_y_m=float(pose[1]),
                            yaw_rad=float(pose[2]), antenna_x_m=float(xy[0]), antenna_y_m=float(xy[1]))
                        trajectories.append(row)
                        if name in mapping:
                            old = previous[(case['id'], mapping[name], method, car, float(stamp))]
                            delta = max(abs(float(old[k])-row[k]) for k in
                                ['base_x_m', 'base_y_m', 'yaw_rad', 'antenna_x_m', 'antenna_y_m'])
                            reproduction_max = max(reproduction_max, delta)
                            if delta > 1e-9: raise AssertionError('PR39 comparison not reproduced')
                print(json.dumps(dict(case=case['id'], config=name, method=method,
                    endpoint_m=metrics['endpoint_difference_m'],
                    path_m={c: metrics['cars'][c]['estimated_antenna_path_m'] for c in CARS})), flush=True)
            if pair['independent']['wall_factor_count'] != pair['joint']['wall_factor_count']:
                raise AssertionError('Unmatched wall factors')
            pair['joint_minus_independent_endpoint_m'] = {c: pair['joint']['endpoint_difference_m'][c]-
                pair['independent']['endpoint_difference_m'][c] for c in CARS}
            pair['matched_input_sha256'] = input_hash
            result['configurations'][name] = pair
            write_json(target/(name+'_comparison.json'), pair)
        results.append(result)
        write_json(target/'comparison.json', result)
        write_json(args.output/'summary.json', dict(cases=results, limitations=protocol['rules']))
        write_csv(args.output/'comparison.csv', table)
        write_csv(args.output/'trajectories.csv', trajectories)
        write_csv(args.output/'confidence.csv', rows)
    if before != {name: sha256(ROOT/'tools'/name) for name in sources} or phash != sha256(args.protocol):
        raise AssertionError('Source or frozen protocol changed during execution')
    write_json(args.output/'input_manifest.json', dict(base_main_sha=protocol['base_main_sha'],
        protocol_sha256=phash, source_files_sha256=before,
        data_sha256={c['path']: sha256(ROOT/c['path']) for k in ['static', 'dynamic'] for c in plan[k+'_cases']},
        python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
        frozen_fixed_scales_sha256=sha256(ROOT/protocol['frozen_fixed_scales_path']),
        baseline_reproduction_max_component_delta=reproduction_max, all_solves_accepted=True,
        method_records=36, trajectory_rows=len(trajectories), confidence_rows=len(rows),
        source_and_protocol_unchanged=True, confidence_computed_before_fits=True))
    print('Completed confidence comparison', flush=True)


if __name__ == '__main__': main()
