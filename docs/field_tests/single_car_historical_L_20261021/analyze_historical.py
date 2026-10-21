#!/usr/bin/env python3
"""Three frozen historical L cases; no hardware, tuning, or endpoint fitting."""
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import math
import platform
import sys
import tarfile
from pathlib import Path

import numpy as np
import scipy

PROTOCOL_SHA = 'cae9add09682483dcca1ae45fa4ae381f1a6638ce6ec09eaf13a3d843cc3bbaf'


def sha(value):
    return hashlib.sha256(value).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def antenna(states, lever):
    c, s = np.cos(states[:, 2]), np.sin(states[:, 2])
    return states[:, :2] + np.column_stack((c * lever[0] - s * lever[1],
                                          s * lever[0] + c * lever[1]))


def final_stop_window(data, high):
    command = np.array(data['cmd'], dtype=float)
    nonzero = (np.hypot(command[:, 1], command[:, 2]) > .005) | (np.abs(command[:, 3]) > .04)
    moving = np.flatnonzero(nonzero)
    if len(moving) == 0:
        return {'available': False, 'reason': 'no motion command'}
    last = int(moving[-1])
    following = np.flatnonzero((np.arange(len(command)) > last) & ~nonzero)
    if len(following) == 0:
        return {'available': False, 'reason': 'no zero command after last motion'}
    stop = float(command[following[0], 0])
    left, right = stop + 2., stop + 7.
    if right > high:
        return {'available': False, 'reason': 'stop+[2,7) not fully covered',
                'stop_elapsed_s': stop - data['start'], 'window_elapsed_s': [left - data['start'], right - data['start']]}
    if np.any(nonzero & (command[:, 0] >= left) & (command[:, 0] < right)):
        raise ValueError('Motion command inside frozen stop window')
    return {'available': True, 'stop_elapsed_s': stop - data['start'], 'bounds': [left, right],
            'window_elapsed_s': [left - data['start'], right - data['start']]}


def body_increments(states):
    delta = np.diff(states[:, :2], axis=0)
    c, s = np.cos(states[:-1, 2]), np.sin(states[:-1, 2])
    return np.column_stack((c * delta[:, 0] + s * delta[:, 1],
                           -s * delta[:, 0] + c * delta[:, 1]))


def main(args):
    folder = Path(__file__).resolve().parent
    if sha((folder / 'protocol.json').read_bytes()) != PROTOCOL_SHA:
        raise ValueError('Frozen protocol changed')
    protocol = json.loads((folder / 'protocol.json').read_text())
    manifest = json.loads((folder / 'source_manifest.json').read_text())
    for entry in manifest['verified_local_source_blobs']:
        b = (args.repo_dir / entry['path']).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest()
        if blob != entry['git_blob_sha']:
            raise ValueError('Archived source changed: ' + entry['path'])
    if args.rosbags_path:
        sys.path.append(str(args.rosbags_path))
    old_path = args.repo_dir / 'tools/analyze_october_field_session.py'
    new_path = args.new_solver or args.repo_dir / 'docs/field_tests/20261018/single_car_transfer_20261021/results/fusion_trial/archived_sources/analyze_october_field_session.py'
    helper_path = args.uwb_helper or args.repo_dir / 'docs/field_tests/20261018/single_car_benefit_20261021/analyze_benefit.py'
    old = load_module('old_graph', old_path)
    new = load_module('new_graph', new_path)
    helper = load_module('matched_uwb', helper_path)
    out = args.output; out.mkdir(parents=True, exist_ok=False)
    evidence = out / 'evidence'; evidence.mkdir()
    for name, path in [('old_graph.py', old_path), ('new_graph.py', new_path), ('matched_uwb.py', helper_path)]:
        (evidence / name).write_bytes(path.read_bytes())
    configs = {}
    for day in ['20261010_11', '20261017']:
        path = args.repo_dir / 'docs/field_tests' / day / 'session_config.json'
        configs[day] = json.loads(path.read_text())
        (evidence / (day + '_config.json')).write_bytes(path.read_bytes())
    raw_cache = out.parent / 'scratch_inputs'; raw_cache.mkdir(exist_ok=False)
    archive_sha = sha(args.oct17_archive.read_bytes())
    if archive_sha != '06a4d4e1b70d7fca8e01dc8723149d04bc6f02167bfcc7dc8b21ea71872d5278':
        raise ValueError('Oct17 archive changed')
    with tarfile.open(args.oct17_archive, 'r:gz') as tar:
        for relative in [configs['20261017']['calibration']['bag'],
                         '20261017/CAR2_auto_Lshape_reinstall_20261017_061540.bag']:
            b = tar.extractfile(relative).read()
            if sha(b) != configs['20261017']['known_sha256'][relative]:
                raise ValueError('Oct17 member changed')
            (raw_cache / Path(relative).name).write_bytes(b)
    calibration = {}
    for day, config in configs.items():
        name = Path(config['calibration']['bag']).name
        path = args.oct11_data / name if day == '20261010_11' else raw_cache / name
        print('READING_CALIBRATION', day, name, flush=True)
        data = old.read_bag(str(path), config['anchors_xyz_m'])
        expected = config['known_sha256'].get(config['calibration']['bag'])
        if expected and data['info']['sha256'] != expected:
            raise ValueError('Calibration SHA mismatch')
        point = np.array(config['calibration']['antenna_xyz_m'])
        collected = collections.defaultdict(list)
        for _, values, tag in data['uwb']:
            if tag == 'node_0':
                for node, value in values.items():
                    collected[node].append(value)
        full = {node: float(np.median(collected[node]) - np.linalg.norm(point - np.array(anchor)))
                for node, anchor in config['anchors_xyz_m'].items()}
        rounded = config['calibration']['frozen_bias_m']
        max_diff = max(abs(full[k] - rounded[k]) for k in full)
        if max_diff > .001:
            raise ValueError('P1 differs from historical calibration')
        calibration[day] = {'source_bag': name, 'source_sha256': data['info']['sha256'],
            'antenna_xyz_m': point.tolist(), 'frozen_bias_m': rounded, 'full_precision_bias_m': full,
            'max_rounding_difference_m': max_diff, 'evaluation_bags_used': False}
    write_json(out / 'calibration.json', calibration)
    endpoints, tracks, static_rows, range_rows, residuals, optimizer, reproduced, input_rows, cases = ([] for _ in range(9))
    equivalence = []
    for case in protocol['cases']:
        day, ident = case['day'], case['id']
        config = configs[day]
        run = next(r for r in config['runs_2d'] if r['label'] == case['label'])
        if run.get('range_exclusions') or run.get('odom_innovation_gate_m'):
            raise ValueError('Primary case contains an exclusion/gate')
        path = args.oct11_data / case['bag'] if day == '20261010_11' else raw_cache / case['bag']
        print('READING_CASE', ident, flush=True)
        data = old.read_bag(str(path), config['anchors_xyz_m'])
        if data['info']['sha256'] != case['bag_sha256']:
            raise ValueError('L bag SHA mismatch')
        for topic in ['/car2/odom', '/car2/imu', '/car2/uwb/ranges']:
            if data['info']['timing'][topic]['header_nonincreasing_steps']:
                raise ValueError('Nonmonotonic header time')
        archived_path = args.repo_dir / case['historical_summary']
        archived = json.loads(archived_path.read_text())
        (evidence / (ident + '_historical_summary.json')).write_bytes(archived_path.read_bytes())
        odom = np.asarray(data['odom']); odom[:, 3] = np.unwrap(odom[:, 3])
        low = max(odom[0, 0], data['uwb'][0][0]); high = min(odom[-1, 0], data['uwb'][-1][0])
        params = config['graph_parameters']
        times = np.arange(math.ceil(low - data['start'] + 1.), math.floor(high - data['start']), params['keyframe_step_s']) + data['start']
        local = np.column_stack([np.interp(times, odom[:, 0], odom[:, j]) for j in [1, 2, 3]])
        observations = old.bin_ranges(data['uwb'], times, params['range_bin_half_width_s'])
        if any(len(row) < 3 for row in observations):
            raise ValueError('Unexpected insufficient UWB-only geometry')
        height = run['start_antenna_xyz_m'][2]
        heading = math.radians(run['initial_heading_deg'])
        start_ref = np.array(run['start_antenna_xyz_m'][:2]); end_ref = np.array(run['end_antenna_xyz_m'][:2])
        frozen_bias = calibration[day]['frozen_bias_m']; full_bias = calibration[day]['full_precision_bias_m']
        zero_bias = {k: 0. for k in full_bias}
        states = {'A': old.align_odom(local, run['start_antenna_xyz_m'], heading)}
        estimates = {'A': states['A'][:, :2]}
        success = {'A': True}
        for method, bias in [('U_raw', zero_bias), ('U_P1', full_bias)]:
            print('SOLVING_UWB', ident, method, flush=True)
            estimates[method] = np.array([helper.uwb_only(row, config['anchors_xyz_m'], bias, height, params['range_sigma_m']) for row in observations])
            if estimates[method].shape != (len(times), 2):
                raise ValueError('UWB solve unavailable')
            success[method] = True
        for method, engine, bias, lever in [
            ('G_raw', new, zero_bias, np.zeros(2)),
            ('G_old', old, frozen_bias, np.zeros(2)),
            ('G_new0', new, frozen_bias, np.zeros(2)),
            ('G_P1', new, full_bias, np.zeros(2)),
            ('G_assumedL', new, full_bias, np.array([.12, -.08]))]:
            base_start = start_ref - new.rotation(heading).dot(lever)
            print('SOLVING_GRAPH', ident, method, flush=True)
            try:
                keywords = {} if method == 'G_old' else {'tag_to_base_lever_xy_m': lever, 'raise_on_failure': False}
                st, info = engine.optimize_graph(local, observations, config['anchors_xyz_m'], bias, height,
                                                  base_start, heading, times, params, **keywords)
                if not np.isfinite(st).all():
                    raise ValueError('Nonfinite iterate')
                states[method] = st; estimates[method] = antenna(st, lever)
                success[method] = info['optimizer_success']
                optimizer.append({'case': ident, 'method': method, 'assumed_lever_xy_m': lever.tolist(),
                                  'historical_geometry_verified': False, **info})
                range_values = []
                for i, values in enumerate(observations):
                    for node, measured in sorted(values.items()):
                        a = np.array(config['anchors_xyz_m'][node])
                        predicted = math.sqrt(float(np.sum((estimates[method][i] - a[:2]) ** 2)) + (height - a[2]) ** 2)
                        residual = predicted - (measured - bias[node])
                        range_rows.append({'case': ident, 'method': method, 'elapsed_s': float(times[i] - data['start']),
                                           'node': node, 'residual_m': residual})
                        range_values.append(residual)
                step_error = body_increments(st) - body_increments(local)
                yaw_error = new.wrap(np.diff(st[:, 2]) - new.wrap(np.diff(local[:, 2])))
                residuals.append({'case': ident, 'method': method, 'optimizer_success': success[method],
                    'range_RMS_m': float(np.sqrt(np.mean(np.square(range_values)))),
                    'range_abs_median_m': float(np.median(np.abs(range_values))),
                    'odom_step_translation_RMS_m': float(np.sqrt(np.mean(np.sum(step_error ** 2, axis=1)))),
                    'odom_step_yaw_RMS_deg': float(np.degrees(np.sqrt(np.mean(yaw_error ** 2))))})
            except Exception as exc:
                optimizer.append({'case': ident, 'method': method, 'optimizer_success': False,
                                  'exception': f'{type(exc).__name__}: {exc}'})
                print('GRAPH_FAILED', ident, method, repr(exc), flush=True)
        if 'G_old' in states and 'G_new0' in states:
            delta = float(np.max(np.abs(states['G_old'] - states['G_new0'])))
            if delta > 1e-9:
                raise ValueError('New zero-lever solver not equivalent to old solver')
            equivalence.append({'case': ident, 'old_new0_max_state_difference': delta})
        windows = {name: tuple(data['start'] + np.array(w)) for name, w in zip(
            ['initial', 'historical_tail5'], archived['endpoint_windows_elapsed_s'])}
        stop = final_stop_window(data, high)
        if stop['available']:
            windows['after_stop_2_7'] = tuple(stop['bounds'])
        window_checks = []
        for name, (left, right) in windows.items():
            mask = (times >= left) & (times < right)
            if mask.sum() < 2:
                raise ValueError('Insufficient frozen-window states')
            oo = odom[(odom[:, 0] >= left) & (odom[:, 0] < right)]
            odom_path = float(np.sum(np.linalg.norm(np.diff(oo[:, 1:3], axis=0), axis=1)))
            yaw_span = float(np.degrees(np.ptp(oo[:, 3])))
            commands = np.array(data['cmd'])
            command_motion = int(np.sum(((np.hypot(commands[:, 1], commands[:, 2]) > .005) | (np.abs(commands[:, 3]) > .04)) &
                                        (commands[:, 0] >= left) & (commands[:, 0] < right)))
            window_checks.append({'window': name, 'odom_path_m': odom_path, 'odom_yaw_span_deg': yaw_span,
                                  'motion_command_count': command_motion, 'keyframes': int(mask.sum()),
                                  'bounds_elapsed_s': [left - data['start'], right - data['start']]})
            for method, xy in estimates.items():
                metrics = helper.position_metrics(xy[mask])
                ref = start_ref if name == 'initial' else end_ref
                difference = float(np.linalg.norm(np.array([metrics['median_x_m'], metrics['median_y_m']]) - ref))
                row = {'case': ident, 'method': method, 'window': name, 'optimizer_success': success[method],
                       'conditional_nonzero_lever': method == 'G_assumedL',
                       'window_start_elapsed_s': left - data['start'], 'window_end_elapsed_s': right - data['start'],
                       **metrics, 'reference_x_m': float(ref[0]), 'reference_y_m': float(ref[1]),
                       'reference_difference_m': difference, 'odom_window_path_m': odom_path,
                       'odom_window_yaw_span_deg': yaw_span, 'motion_command_count': command_motion}
                static_rows.append(row)
                if name != 'initial':
                    endpoints.append(row)
                if method == 'G_old' and name == 'historical_tail5':
                    before = archived['batch_graph_2d']['end_reference_difference_m']
                    reproduced.append({'case': ident, 'archived_endpoint_difference_m': before,
                        'rerun_old_endpoint_difference_m': difference, 'absolute_difference_m': abs(difference - before),
                        'old_runtime_differs': day == '20261017', 'runtime_note': 'Oct17 old SciPy0.19.1 vs current1.17.0; backend effect not algorithm gain'})
        for method, xy in estimates.items():
            reference = estimates.get('G_P1')
            for i, t in enumerate(times):
                st = states.get(method)
                tracks.append({'case': ident, 'method': method, 'elapsed_s': float(t - data['start']),
                    'antenna_x_m': float(xy[i, 0]), 'antenna_y_m': float(xy[i, 1]),
                    'base_x_m': float(st[i, 0]) if st is not None else '',
                    'base_y_m': float(st[i, 1]) if st is not None else '',
                    'yaw_rad': float(st[i, 2]) if st is not None else '', 'optimizer_success': success[method],
                    'displacement_from_G_P1_m': float(np.linalg.norm(xy[i] - reference[i])) if reference is not None else ''})
        for i, t in enumerate(times):
            for node, measured in sorted(observations[i].items()):
                input_rows.append({'case': ident, 'elapsed_s': float(t - data['start']), 'absolute_time_s': float(t),
                    'local_odom_x_m': float(local[i, 0]), 'local_odom_y_m': float(local[i, 1]), 'local_yaw_rad': float(local[i, 2]),
                    'node': node, 'range_m': measured, 'frozen_bias_m': frozen_bias[node], 'full_P1_bias_m': full_bias[node]})
        cases.append({'case': case, 'run': run, 'bag_metadata': data['info'], 'keyframes': len(times),
                      'origin_float_s': data['start'], 'available_anchor_combinations': dict(collections.Counter('|'.join(sorted(row)) for row in observations)),
                      'window_checks': window_checks, 'stop_window': stop, 'inherited_start_heading': True,
                      'horizontal_lever_independently_measured': False})
        print('CASE_FINISHED', ident, flush=True)
    for name, rows in [('endpoint_comparison.csv', endpoints), ('stationary_diagnostics.csv', static_rows),
                       ('trajectories.csv', tracks), ('range_residuals.csv', range_rows),
                       ('residual_summary.csv', residuals), ('legacy_reproduction.csv', reproduced),
                       ('keyframe_inputs.csv', input_rows)]:
        write_csv(out / name, rows)
    write_json(out / 'optimizer_records.json', optimizer)
    write_json(out / 'input_audit.json', cases)
    checks = {'main_source_files_verified': len(manifest['verified_local_source_blobs']),
              'L_bags_hash_verified': 3, 'calibration_bags_hash_verified': 2, 'graph_attempts': len(optimizer),
              'successful_graphs': sum(bool(o['optimizer_success']) for o in optimizer),
              'old_new0_equivalence': equivalence, 'legacy_reproduction': reproduced,
              'no_parameter_selection': True, 'protocol_unchanged': sha((folder / 'protocol.json').read_bytes()) == PROTOCOL_SHA}
    if len(optimizer) != 15 or len(equivalence) != 3:
        raise ValueError('Incomplete frozen experiment')
    write_json(out / 'summary.json', {'cases': cases, 'calibration': calibration, 'endpoints': endpoints,
        'stationary': static_rows, 'residuals': residuals, 'optimizers': optimizer, 'checks': checks,
        'provenance': {'base_main_sha': protocol['base_main_sha'], 'protocol_sha256': PROTOCOL_SHA,
            'script_sha256': sha(Path(__file__).read_bytes()), 'old_graph_sha256': sha(old_path.read_bytes()),
            'new_graph_sha256': sha(new_path.read_bytes()), 'UWB_helper_sha256': sha(helper_path.read_bytes()),
            'oct17_archive_sha256': archive_sha, 'python': sys.version, 'numpy': np.__version__,
            'scipy': scipy.__version__, 'platform': platform.platform()}})
    print(json.dumps(checks, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-dir', type=Path, required=True)
    parser.add_argument('--oct11-data', type=Path, required=True)
    parser.add_argument('--oct17-archive', type=Path, required=True)
    parser.add_argument('--new-solver', type=Path)
    parser.add_argument('--uwb-helper', type=Path)
    parser.add_argument('--rosbags-path', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
