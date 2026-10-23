#!/usr/bin/env python3
"""Frozen stationary-covariance / static-range-confidence development ablation."""
from __future__ import annotations

import argparse
import copy
import csv
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

import numpy as np
import scipy

from run_two_car_updated_comparison import fingerprint, serial, stats, write_csv, write_json
from single_car_sequential_replay import rotation
from two_car_updated_comparison import CARS, PEERS, build_inputs, fit_static_wall_bias, read_bag, sha256
from two_car_stationary_confidence import confidence_scales, near_zero_edges, read_odom_motion, solve_policy

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT/'docs/field_tests/two_car_stationary_confidence_20261023'


def static_record(run, case, parent, biases):
    walls, details = {}, []
    for car in CARS:
        walls[car] = {}
        point = np.asarray(case['antenna_xyz_m'][car])
        for key, xyz in sorted(parent['anchors_xyz_m'].items()):
            values = [r[key] for _, r in run['uwb'][car] if key in r]
            if len(values) < 5:
                raise ValueError('Missing static training/validation link')
            geometry = float(np.linalg.norm(point-xyz))
            median = float(np.median(values))
            error = median-biases[car][key]-geometry
            walls[car][key] = error
            details.append(dict(car=car, anchor=key, samples=len(values), raw_median_m=median,
                geometry_m=geometry, applied_bias_m=biases[car][key], corrected_error_m=error))
    directions = []
    for car in CARS:
        values = [r[PEERS[car]] for _, r in run['uwb'][car] if PEERS[car] in r]
        if len(values) < 5:
            raise ValueError('Missing static reciprocal peer samples')
        directions.append(float(np.median(values)))
    reference = float(np.linalg.norm(np.asarray(case['antenna_xyz_m']['car1'])-
                                    case['antenna_xyz_m']['car2']))
    return dict(id=case['id'], path=case['path'], sha256=case['sha256'],
        reference_source=case['source'], wall_errors_m=walls, wall_details=details,
        peer_directional_medians_m=directions, peer_aggregate_m=float(np.mean(directions)),
        peer_reference_m=reference, peer_error_m=float(np.mean(directions)-reference))


def prepare_scales(protocol, parent, output):
    calibration = parent['calibration']['car1']
    raw = read_bag(ROOT/calibration['path'], calibration['sha256'])
    fit = fit_static_wall_bias(raw, 'car1', calibration['reference_antenna_xyz_m'], parent['anchors_xyz_m'])
    biases = dict(car1={k: v['bias_m'] for k, v in fit.items()},
                  car2=copy.deepcopy(parent['calibration']['car2']['range_bias_m']))
    previous = json.loads((ROOT/'docs/field_tests/two_car_updated_comparison_20261022/results/calibration.json').read_text())
    if biases != previous['applied_biases_m']:
        raise AssertionError('Frozen range means changed')
    training, validation = [], []
    for split, target in [('training', training), ('validation', validation)]:
        for case in protocol['range_confidence'][split]:
            run = read_bag(ROOT/case['path'], case['sha256'])
            target.append(static_record(run, case, parent, biases))
    policy = protocol['range_confidence']
    scales = confidence_scales(training, policy['wall_sigma_floor_m'], policy['peer_sigma_floor_m'])
    write_json(output/'range_confidence.json', dict(biases_m=biases, scales=scales,
        training=training, validation=validation, formula=policy['formula'],
        validation_and_dynamic_endpoints_used_for_fitting=False))
    rows = []
    for split, records in [('training', training), ('validation', validation)]:
        for record in records:
            for row in record['wall_details']:
                rows.append(dict(split=split, bag=record['id'], **row,
                    uncertainty_scale_m=scales['wall_sigma_m'][row['car']][row['anchor']]))
    write_csv(output/'static_range_errors.csv', rows)
    return biases, scales


def evaluate(inputs, fit, objective, masks, case):
    """Truth is first accessed here, after fitting; ledger uses actual covariances."""
    states, ant, n = fit['states'], fit['antenna_xy'], len(inputs['times'])
    endpoint = np.median(ant[:, -5:], axis=1)
    result = dict(optimizer=fit['optimizer'], endpoint_difference_m={}, endpoint_xy_m={},
        cars={}, wall_residual_by_link={}, stationary_car=case['stationary_car'],
        keyframes=n, endpoint_window_s=inputs['times'][-5:].tolist(),
        wall_factor_count=fit['wall_factor_count'], peer_factor_count=fit['peer_factor_count'])
    ledger = {}
    for ci, car in enumerate(CARS):
        data, part = inputs['cars'][car], objective.parts[ci]
        model = data['model']
        target = case['evaluation_only']['end_antenna_xyz_m'][car][:2]
        result['endpoint_difference_m'][car] = float(np.linalg.norm(endpoint[ci]-target))
        result['endpoint_xy_m'][car] = endpoint[ci].tolist()
        delta = np.diff(states[ci, :, :2], axis=0)
        body = np.asarray([rotation(-th)@d for th, d in zip(states[ci, :-1, 2], delta)])
        errors = np.linalg.norm(body-part.measured_body, axis=1)
        r = part.fun(states[ci].ravel())
        ledger[car] = dict(prior=.5*float(r[:3]@r[:3]),
            odom=.5*float(r[3:3*n]@r[3:3*n]), wall=.5*float(r[3*n:]@r[3*n:]))
        result['cars'][car] = dict(
            estimated_antenna_path_m=float(np.linalg.norm(np.diff(ant[ci], axis=0), axis=1).sum()),
            antenna_net_displacement_m=float(np.linalg.norm(ant[ci, -1]-ant[ci, 0])),
            start_antenna_prior_displacement_m=float(np.linalg.norm(ant[ci, 0]-model['start_antenna_xyz_m'][:2])),
            aligned_odom_path_m=float(np.linalg.norm(np.diff(data['local'][:, :2], axis=0), axis=1).sum()),
            odom_translation_correction_m=stats(errors),
            near_zero_edges=int(np.sum(masks[car])),
            near_zero_odom_correction_m=stats(errors[masks[car]]))
        links = {key: [] for key in model['anchors_xyz_m']}
        for i, observations in enumerate(data['observations']):
            for key, raw in observations.items():
                distance = np.linalg.norm(np.r_[ant[ci, i], model['antenna_height_m']]-model['anchors_xyz_m'][key])
                links[key].append(float(distance-(raw-model['range_bias_m'][key])))
        result['wall_residual_by_link'][car] = {key: stats(values) for key, values in links.items()}
    peer_errors = []
    dz = inputs['cars']['car1']['model']['antenna_height_m']-inputs['cars']['car2']['model']['antenna_height_m']
    for i, row in enumerate(inputs['peers']):
        if row['range_m'] is not None:
            peer_errors.append(float(np.linalg.norm(np.r_[ant[0, i]-ant[1, i], dz])-row['range_m']))
    result['peer_residual_m'] = stats(peer_errors)
    r = objective.fun(states.ravel()); count = fit['peer_factor_count']
    ledger['peer'] = .5*float(r[-count:]@r[-count:]) if count else 0.
    cost = sum(sum(v.values()) if isinstance(v, dict) else v for v in ledger.values())
    if abs(cost-fit['optimizer']['cost']) > 1e-9*(1+abs(cost)):
        raise AssertionError('Actual factor ledger differs from solver cost')
    result['factor_cost_ledger'] = ledger
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=DOCS/'protocol.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dependency-path', type=Path)
    args = parser.parse_args()
    if args.dependency_path:
        # NumPy/SciPy are imported first; avoid the bag reader's bundled NumPy.
        sys.path.append(str(args.dependency_path.resolve()))
    if any(os.environ.get(k) != '1' for k in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS']):
        raise ValueError('Set OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1')
    protocol = json.loads(args.protocol.read_text())
    parent_path = ROOT/protocol['parent_protocol_path']
    if sha256(parent_path) != protocol['parent_protocol_sha256']:
        raise ValueError('Parent protocol hash mismatch')
    parent = json.loads(parent_path.read_text())
    sources = ['two_car_stationary_confidence.py', 'run_two_car_stationary_confidence.py',
        'test_two_car_stationary_confidence.py', 'two_car_updated_comparison.py',
        'run_two_car_updated_comparison.py', 'single_car_fixed_lag.py', 'single_car_sequential_replay.py']
    before = {name: sha256(ROOT/'tools'/name) for name in sources}
    protocol_hash = sha256(args.protocol)
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/'protocol.json', protocol)
    biases, scales = prepare_scales(protocol, parent, args.output)
    oldroot = ROOT/'docs/field_tests/two_car_updated_comparison_20261022/results'
    with (oldroot/'trajectories.csv').open() as stream:
        previous = {(r['case'], r['method'], r['car'], float(r['elapsed_s'])): r
                    for r in csv.DictReader(stream) if r['configuration'] == 'per_car_walls'}
    table, trajectories, results, detector_rows = [], [], [], []
    reproduction_max = 0.
    for case in parent['cases']:
        if case['id'] not in protocol['cases']:
            continue
        run = read_bag(ROOT/case['path'], case['sha256'])
        motion = read_odom_motion(ROOT/case['path'], case['sha256'])
        target = args.output/case['id']; target.mkdir()
        model_case = {k: copy.deepcopy(case[k]) for k in ['start_antenna_xyz_m', 'initial_heading_deg']}
        basecfg = dict(correction='per_car', peer_sigma_m=.2, withheld_wall_car=None, car2_peer_shift_s=0.)
        full = build_inputs(run, model_case, parent, basecfg, biases)
        masks, detail = {}, {}
        for car in CARS:
            # Extra reader must reproduce the frozen pose receipts exactly.
            np.testing.assert_array_equal(motion[car][:, :4], np.asarray(run['odom'][car]))
            masks[car], detail[car] = near_zero_edges(motion[car], full['times'], protocol['detector'])
            detector_rows.extend(dict(case=case['id'], car=car, **row) for row in detail[car])
        write_json(target/'motion_candidates.json', detail)
        case_result = dict(case=case['id'], role=case['role'], stationary_car=case['stationary_car'], configurations={})
        for configuration in protocol['configurations']:
            name = configuration['id']
            inputs = copy.deepcopy(full)
            withheld = configuration['withheld_wall_car']
            if withheld:
                inputs['cars'][withheld]['observations'] = [{} for _ in inputs['times']]
            paired_hash = fingerprint(inputs)
            pair = {}
            print(f"Starting {case['id']} / {name}", flush=True)
            for method, joint in [('independent', False), ('joint', True)]:
                fit, objective = solve_policy(inputs, joint, configuration, masks, scales,
                                               protocol['detector'], protocol['optimizer'])
                if fingerprint(inputs) != paired_hash:
                    raise AssertionError('Optimizer mutated matched inputs')
                metrics = evaluate(inputs, fit, objective, masks, case)
                pair[method] = metrics
                for ci, car in enumerate(CARS):
                    table.append(dict(case=case['id'], configuration=name, method=method, car=car,
                        endpoint_difference_m=metrics['endpoint_difference_m'][car],
                        antenna_path_m=metrics['cars'][car]['estimated_antenna_path_m'],
                        antenna_net_m=metrics['cars'][car]['antenna_net_displacement_m'],
                        start_prior_shift_m=metrics['cars'][car]['start_antenna_prior_displacement_m'],
                        near_zero_edges=int(np.sum(masks[car])), wall_factors=fit['wall_factor_count'],
                        peer_factors=fit['peer_factor_count'], nfev=fit['optimizer']['nfev'],
                        solve_wall_s=fit['optimizer']['solve_wall_s']))
                    for i, stamp in enumerate(inputs['times']):
                        pose, xy = fit['states'][ci, i], fit['antenna_xy'][ci, i]
                        trajectories.append(dict(case=case['id'], configuration=name, method=method, car=car,
                            elapsed_s=float(stamp), base_x_m=float(pose[0]), base_y_m=float(pose[1]),
                            yaw_rad=float(pose[2]), antenna_x_m=float(xy[0]), antenna_y_m=float(xy[1])))
                        if name == 'baseline':
                            old = previous[(case['id'], method, car, float(stamp))]
                            delta = max(abs(float(old[k])-trajectories[-1][k]) for k in
                                        ['base_x_m', 'base_y_m', 'yaw_rad', 'antenna_x_m', 'antenna_y_m'])
                            reproduction_max = max(reproduction_max, delta)
                            if delta > protocol['evaluation_only']['baseline_reproduction_tolerance_m']:
                                raise AssertionError('PR38 baseline trajectory not reproduced')
                print(json.dumps(dict(case=case['id'], configuration=name, method=method,
                    endpoint_m=metrics['endpoint_difference_m'],
                    path_m={c: metrics['cars'][c]['estimated_antenna_path_m'] for c in CARS})), flush=True)
            if pair['independent']['wall_factor_count'] != pair['joint']['wall_factor_count']:
                raise AssertionError('Wall factor counts differ in matched pair')
            pair['matched_inputs_sha256'] = paired_hash
            pair['endpoint_effect_joint_minus_independent_m'] = {c:
                pair['joint']['endpoint_difference_m'][c]-pair['independent']['endpoint_difference_m'][c]
                for c in CARS}
            case_result['configurations'][name] = pair
            write_json(target/(name+'_comparison.json'), pair)
        write_json(target/'comparison.json', case_result)
        results.append(case_result)
        write_csv(args.output/'comparison.csv', table)
        write_csv(args.output/'trajectories.csv', trajectories)
        write_json(args.output/'summary.json', dict(cases=results, limitations=protocol['limitations']))
    write_csv(args.output/'motion_candidates.csv', [{k: row.get(k) for k in sorted(set().union(
        *(r.keys() for r in detector_rows)))} for row in detector_rows])
    if before != {name: sha256(ROOT/'tools'/name) for name in sources} or protocol_hash != sha256(args.protocol):
        raise AssertionError('Sources or protocol changed during run')
    data = parent['cases']+[r for split in ['training', 'validation']
                            for r in protocol['range_confidence'][split]]
    actual_data = {r['path']: sha256(ROOT/r['path']) for r in data}
    if actual_data != {r['path']: r['sha256'] for r in data}:
        raise AssertionError('Bag contents changed during run')
    write_json(args.output/'input_manifest.json', dict(base_main_sha=protocol['base_main_sha'],
        protocol_sha256=protocol_hash, source_files_sha256=before, data_files_sha256=actual_data,
        python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
        rosbags=importlib.metadata.version('rosbags'), thread_environment={k: os.environ[k] for k in
        ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS']}, source_and_protocol_unchanged_during_run=True,
        baseline_reproduction_max_component_delta=reproduction_max,
        method_records=sum(len(c['configurations'])*2 for c in results),
        trajectory_rows=len(trajectories), all_solves_accepted=True))
    print('Completed frozen development ablation', flush=True)


if __name__ == '__main__':
    main()
