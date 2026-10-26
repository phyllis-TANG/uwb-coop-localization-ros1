"""T10 hypothesis-only pilot; unchanged PR46/48 engines, immutable PR51 inputs.

Never call this through the strict B-end entry point or treat readiness/valid as
reference acceptance. Numeric clocks and placements below are explicit assumed
inputs, not recovered measurements or calibrated error bounds.
"""
import argparse
from collections import Counter, defaultdict
import copy
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[3]
PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARENT / 't10_closure'))
import common as closure
import model
import replay

PROTOCOL = Path(__file__).with_name('protocol.json')
DOCS = ROOT / 'docs/field_tests/20261024_25/t10_exploratory_20261027'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def read_csv(path):
    with Path(path).open(newline='') as f:
        return list(csv.DictReader(f))


def antenna_xy(pose, lever):
    return np.asarray(pose[:2]) + model.rotation(pose[2]) @ np.asarray(lever)


def configuration(protocol, profile, odom, ranges, origin):
    if protocol['experiment_id'] != 'T10' or protocol['bag_sha256'] != closure.BAG_SHA:
        raise ValueError('only the authorized T10 development retry')
    config = json.loads((ROOT / 'docs/field_tests/20261024_25/t10_closure_20261027/results/T10_strict_baseline_config.json').read_text())
    config['odom_only_frame'] = 'room'
    config['exploration_only'] = True
    config['strict_field_acceptance'] = False
    config['experiment_notes'] = ['All supplied placements/base origins/clocks are unverified hypotheses; no reference or endpoint fitting.']
    change = profile['change']
    for car in model.CARS:
        cc = config['vehicles'][car]
        lever = list(protocol['geometric_center_offset_as_base_hypothesis_xy_m'][car])
        shift = protocol['total_header_to_comparison_time_hypothesis_ns'][car]
        if change and change['car'] == car:
            if change['kind'] == 'lever_x': lever[0] += change['delta']
            elif change['kind'] == 'clock_ns': shift += change['delta']
            else: raise ValueError('unknown sensitivity factor')
        cc['antenna_body_xy_m'] = dict(status='provided', value=lever,
            source_kind='engineering_assumption', measured_base_relation=False,
            source='Assume physical odometry point equals surveyed approximate chassis center; T10 mounting continuity unverified.')
        for name, rows in [('odom_clock', odom), ('range_clock', ranges)]:
            own = [r for r in rows if r['vehicle_id'] == car]
            headers = [int(r['header_epoch_ns']) for r in own]
            cc[name] = dict(status='provided', field='header_epoch_ns',
                source_origin_ns=origin, destination_origin_ns=origin+shift,
                rate_numerator=1, rate_denominator=1,
                uncertainty_ns=protocol['clock_uncertainty_api_parameter_ns'],
                uncertainty_role='unverified_API_parameter_NOT_calibrated_bound',
                valid_source_interval_ns=[min(headers), max(headers)],
                source_clock_id=car+':hypothesized_host_header',
                destination_clock_id=config['master_clock_id'],
                source_kind='engineering_assumption',
                source='Unverified identity rate/epoch plus total header adjustment; NOT clock calibration.')
        candidates = sorted((r for r in odom if r['vehicle_id'] == car),
            key=lambda r: (int(r['receive_epoch_ns']), int(r['record_index'])))
        candidates = [r for r in candidates
            if int(r['receive_epoch_ns']) >= origin+round(protocol['initialization_after_receive_seconds']*1e9)
            and 0 <= int(r['receive_epoch_ns'])-model.map_time(r, cc['odom_clock']) <= config['max_measurement_latency_ns']]
        if not candidates: raise ValueError('no fresh source record for assumed initialization')
        initial = candidates[0]
        yaw = protocol['nominal_body_yaw_rad'][car]
        nominal = np.asarray(protocol['nominal_antenna_xy_m'][car])
        base = nominal-model.rotation(yaw) @ lever
        cc['initial_room_pose'] = dict(status='provided', value=[*base.tolist(), yaw],
            source_kind='engineering_assumption',
            source='Assume instructed Car1 placement / carried Car2 T09 manual endpoint and planned heading at selected record; not actual T10 measurement.')
        cc['initial_record_binding'] = dict(status='provided',
            source='Exact record identity; associated physical room pose is only a hypothesis.',
            source_file_sha256=closure.BAG_SHA,
            **{k: int(initial[k]) for k in ('record_index', 'header_epoch_ns', 'receive_epoch_ns')})
    model.validate_config(config)
    assert not any(reasons for methods in model.readiness(config).values() for reasons in methods.values())
    return config


def uwb_solution(anchors, targets, distances, height):
    xyz = np.array([anchors[k] for k in targets], dtype=float)
    values = np.asarray(distances)
    def residual(p):
        return np.sqrt(np.sum((p-xyz[:, :2])**2, axis=1)+(height-xyz[:, 2])**2)-values
    guess = np.mean(np.array(list(anchors.values()))[:, :2], axis=0)
    result = least_squares(residual, guess, max_nfev=150,
        ftol=1e-10, xtol=1e-10, gtol=1e-10)
    independent = np.linalg.norm(np.c_[np.tile(result.x, (len(xyz), 1)), np.full(len(xyz), height)]-xyz, axis=1)-values
    if not np.allclose(independent, result.fun, atol=1e-12): raise AssertionError('range residual mismatch')
    return result


def uwb_only(ranges, config, origin, output):
    anchors = config['anchors_xyz_m']['value']
    groups, stamps = defaultdict(dict), {}
    for r in ranges:
        if r['source'] != 'raw' or r['primary_observation'] != '1' or r['valid'] != '1' or r['target_id'] not in anchors: continue
        key = r['vehicle_id'], int(r['record_index'])
        if r['target_id'] in groups[key]: raise ValueError('duplicate target in raw frame')
        groups[key][r['target_id']] = float(r['range_m'])
        stamps[key] = int(r['receive_epoch_ns'])
    rows, summary = [], {}
    for car in model.CARS:
        last, own = None, []
        height = model.antenna_height(config['vehicles'][car])
        for key in sorted((k for k in groups if k[0] == car), key=lambda k: (stamps[k], k[1])):
            if len(groups[key]) < 3 or last is not None and stamps[key]-last < 200000000: continue
            last = stamps[key]
            result = uwb_solution(anchors, list(groups[key]), list(groups[key].values()), height)
            own.append(dict(vehicle_id=car, record_index=key[1], receive_epoch_ns=last,
                canonical_time_s=(last-origin)/1e9, x_antenna_m=float(result.x[0]), y_antenna_m=float(result.x[1]),
                optimizer_converged=int(result.success), range_fit_residual_rms_m=float(np.sqrt(np.mean(result.fun**2)))))
        rows += own
        summary[car] = dict(selected_frames=len(own), optimizer_converged=sum(r['optimizer_converged'] for r in own),
            median_range_fit_residual_m=float(np.median([r['range_fit_residual_rms_m'] for r in own])),
            residual_is_position_error=False)
    with (output/'uwb_only.csv').open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return summary


def execute(events, config, origin, end, directory, deadline):
    directory.mkdir(exist_ok=False)
    save(directory/'config.json', config)
    states = []
    with (directory/'estimate.csv').open('x', newline='') as f, gzip.open(directory/'decisions.jsonl.gz', 'xt', compresslevel=3) as trace, gzip.open(directory/'diagnostics.jsonl.gz', 'xt', compresslevel=3) as diagnostics:
        writer = csv.DictWriter(f, fieldnames=replay.ESTIMATE_COLUMNS); writer.writeheader()
        for rows, diag, decisions in replay.replay_events(events, config, 'T10', origin, end,
                config_hash=digest(directory/'config.json'), deadline=deadline):
            for r in rows:
                r = dict(r); r['source_version'] = 'PR51_T10_selection_exploratory_only'
                r['pose_covariance'] = json.dumps(r['pose_covariance'], allow_nan=False) if r['pose_covariance'] is not None else ''
                writer.writerow(r); states.append(r)
            for decision in decisions: trace.write(json.dumps(decision, allow_nan=False)+'\n')
            diagnostics.write(json.dumps(diag, allow_nan=False)+'\n')
    metrics = {'scope': 'output response under hypotheses; no true-position errors', 'methods': {},
        'event_counts': {m: diag['methods'][m]['cumulative_event_status'] for m in model.METHODS}}
    for method in model.METHODS:
        metrics['methods'][method] = {}
        for car in model.CARS:
            own = [r for r in states if r['method_id'] == method and r['vehicle_id'] == car and r['valid']]
            lever = model.antenna_offset_xy(config['vehicles'][car])
            xy = [antenna_xy([r['x_m'], r['y_m'], r['yaw_rad']], lever) for r in own]
            tail = [p for r, p in zip(own, xy) if int(r['publish_receive_epoch_ns']) >= end-10000000000]
            metrics['methods'][method][car] = dict(valid_rows=len(own),
                final_antenna_xy_m=xy[-1].tolist() if xy else None,
                terminal_10s_output_excursion_m=max((float(np.linalg.norm(p-tail[0])) for p in tail), default=None),
                terminal_window_is_independently_validated_stationary_truth=False)
    for car in model.CARS:
        paired = {}
        lever = model.antenna_offset_xy(config['vehicles'][car])
        for r in states:
            if r['vehicle_id'] == car and r['method_id'] in ('independent', 'joint') and r['valid']:
                key = r['publish_receive_epoch_ns'], r['state_epoch_ns']
                paired.setdefault(key, {})[r['method_id']] = antenna_xy([r['x_m'], r['y_m'], r['yaw_rad']], lever)
        delta = [float(np.linalg.norm(p['joint']-p['independent'])) for p in paired.values() if len(p) == 2]
        metrics.setdefault('peer_vs_independent_output_shift_m', {})[car] = dict(samples=len(delta),
            median=float(np.median(delta)) if delta else None, p95=float(np.percentile(delta, 95)) if delta else None,
            maximum=max(delta, default=None), is_accuracy_gain_or_harm=False)
    save(directory/'metrics.json', metrics)
    return metrics


def verify(directory, odom, ranges, config):
    source = {(r['vehicle_id'], int(r['record_index'])): r for r in odom}
    links = {(r['vehicle_id'], int(r['record_index']), int(r['link_index'])): r for r in ranges}
    accepted, updates, numerical = {}, Counter(), 0
    with gzip.open(directory/'decisions.jsonl.gz', 'rt') as f:
        for line in f:
            d = json.loads(line); status = d['status']; numerical += status.startswith('numerical_')
            if status in ('initialized', 'odometry_predicted'):
                accepted.setdefault((d['method_id'], d['vehicle_id']), []).append(d)
            if status in ('wall_updated', 'peer_updated'):
                r = links[d['vehicle_id'], d['record_index'], d['link_index']]
                assert r['source'] == 'raw' and r['primary_observation'] == '1' and r['valid'] == '1'
                assert d['measurement_epoch_ns'] <= d['receive_epoch_ns'] <= d['admitted_at_publication_ns']
                assert all(0 <= age <= config['max_extrapolation_ns'] for age in d['support_age_ns'].values())
                if status == 'peer_updated': assert d['method_id'] == 'joint' and d['vehicle_id'] == 'car1'
                updates[d['method_id']+':'+status] += 1
    n = poses = 0
    for r in read_csv(directory/'estimate.csv'):
        n += 1
        if not r['x_m']: continue
        poses += 1; tick = int(r['publish_receive_epoch_ns'])
        original = source[r['vehicle_id'], int(r['source_record_index'])]
        assert int(r['source_header_epoch_ns']) == int(original['header_epoch_ns'])
        assert int(r['source_receive_epoch_ns']) == int(original['receive_epoch_ns']) <= tick
        own = [d for d in accepted[r['method_id'], r['vehicle_id']] if d['admitted_at_publication_ns'] <= tick]
        assert own and own[-1]['record_index'] == int(r['source_record_index'])
        assert int(r['state_epoch_ns']) <= tick
        covariance = np.asarray(json.loads(r['pose_covariance']))
        assert covariance.shape == (3, 3) and np.isfinite(covariance).all()
        assert np.allclose(covariance, covariance.T, atol=1e-10) and np.linalg.eigvalsh(covariance).min() >= -1e-10
        assert all(math.isfinite(float(r[k])) for k in ('x_m', 'y_m', 'yaw_rad'))
    result = dict(rows=n, existing_poses=poses, update_identity_support_and_direction_checks=dict(updates),
        numerical_failure_events=numerical, provenance_and_accepted_asof_verified=True,
        per_car_covariance_PSD_checked=True, field_accuracy_evaluated=False)
    save(directory/'verification.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--packet', required=True, type=Path); p.add_argument('--output', required=True, type=Path)
    p.add_argument('--max-seconds', type=float, default=900)
    args = p.parse_args(); started = time.monotonic()
    if not 0 < args.max_seconds <= 3600: raise ValueError('pilot budget must be <= one hour')
    args.output.mkdir(parents=True, exist_ok=False)
    provenance = closure.verify_packet(args.packet)
    protocol = json.loads(PROTOCOL.read_text())
    manifest = json.loads((closure.SESSION/'manifest.json').read_text())
    item = next(r for r in manifest['formal_bags'] if r['id'] == 'T10')
    assert item['sha256'] == protocol['bag_sha256'] == closure.BAG_SHA and item['split'] == 'development'
    odom = read_csv(args.packet/'normalized_T10/odom.csv'); ranges = read_csv(args.packet/'normalized_T10/ranges.csv')
    assert all(r['experiment_id'] == 'T10' and r['source_file_sha256'] == closure.BAG_SHA for r in odom+ranges)
    origin, end = item['first_bag_receive_epoch_ns'], item['last_bag_receive_epoch_ns']
    source_paths = [Path(__file__), PROTOCOL, Path(model.__file__), Path(replay.__file__), Path(closure.__file__)]
    run = dict(status='IN_PROGRESS', scope='EXPLORATORY_ONLY', strict_acceptance=False,
        code_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        worktree_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        sources={str(q.relative_to(ROOT)): digest(q) for q in source_paths}, packet=provenance,
        protocol_sha256=digest(PROTOCOL), argv=sys.argv, profiles={}, field_accuracy=protocol['evaluation'])
    save(args.output/'started.json', run)
    try:
        for profile in protocol['profiles']:
            if time.monotonic()-started >= args.max_seconds: raise TimeoutError('pilot budget exhausted')
            config = configuration(protocol, profile, odom, ranges, origin)
            events, counts, _ = replay.read_events(args.packet/'normalized_T10', 'T10', config, manifest)
            if profile['id'] == 'nominal': run['uwb_only'] = uwb_only(ranges, config, origin, args.output)
            directory = args.output/profile['id']
            metrics = execute(events, config, origin, end, directory, started+args.max_seconds)
            checked = verify(directory, odom, ranges, config)
            run['profiles'][profile['id']] = dict(input_events=counts, metrics=metrics, verification=checked)
            print(json.dumps({'profile':profile['id'], 'verified_rows':checked['rows'], 'numerical_failures':checked['numerical_failure_events']}, ensure_ascii=False), flush=True)
        run['status'] = 'DONE_EXPLORATORY_ONLY'
    except Exception as error:
        run['status'] = 'FAILED'; run['error'] = repr(error)
        raise
    finally:
        run['elapsed_seconds'] = time.monotonic()-started
        run['outputs'] = {str(q.relative_to(args.output)): digest(q) for q in args.output.rglob('*') if q.is_file()}
        save(args.output/'run.json', run)


if __name__ == '__main__': main()
