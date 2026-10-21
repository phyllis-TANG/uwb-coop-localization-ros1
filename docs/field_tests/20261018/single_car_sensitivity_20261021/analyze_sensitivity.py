#!/usr/bin/env python3
"""Fixed retrospective offline sensitivity; no hardware or parameter selection."""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import itertools
import json
import math
import platform
import sys
import zipfile
from pathlib import Path

import numpy as np
import scipy


EXPECTED_PROTOCOL_SHA256 = '048de25b3fb93344f0863d0c62245ada0b9aaf4f7cde76d7ef03e66acc78cd35'
EXPECTED_REVIEW_SHA256 = '5536b5217127de0975b2a3839d844eea37630fb4aa2e7009a231b5c62397a13c'


def digest(value):
    return hashlib.sha256(value).hexdigest()


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    if not rows:
        raise ValueError('Empty output: ' + str(path))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def verify_manifest(directory):
    checked = 0
    for line in (directory / 'SHA256SUMS.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        expected, name = line.split('  ', 1)
        if digest((directory / name).read_bytes()) != expected:
            raise ValueError('Previous artifact changed: ' + name)
        checked += 1
    return checked


def antenna_xy(states, lever):
    c, s = np.cos(states[:, 2]), np.sin(states[:, 2])
    return states[:, :2] + np.column_stack((c * lever[0] - s * lever[1],
                                          s * lever[0] + c * lever[1]))


def body_increments(states):
    delta = np.diff(states[:, :2], axis=0)
    c, s = np.cos(states[:-1, 2]), np.sin(states[:-1, 2])
    return np.column_stack((c * delta[:, 0] + s * delta[:, 1],
                           -s * delta[:, 0] + c * delta[:, 1]))


def wrap(values):
    return np.arctan2(np.sin(values), np.cos(values))


def statistics(values):
    values = np.asarray(values, dtype=float)
    return {'samples': int(len(values)), 'median_m': float(np.median(values)),
            'abs_median_m': float(np.median(np.abs(values))),
            'RMS_m': float(np.sqrt(np.mean(values ** 2))),
            'abs_p95_m': float(np.percentile(np.abs(values), 95))}


def position_metrics(xy):
    center = np.median(xy, axis=0)
    return {'samples': len(xy), 'median_x_m': float(center[0]), 'median_y_m': float(center[1]),
            'scatter_about_median_RMS_m': float(np.sqrt(np.mean(np.sum((xy - center) ** 2, axis=1)))),
            'first_last_displacement_m': float(np.linalg.norm(xy[-1] - xy[0])),
            'path_m': float(np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1)))}


def stationary_windows(times, bounds):
    return {'initial': (times[0], bounds['forward'][0]['start_s'] - .5),
            'idle_before_turn': (bounds['forward'][0]['end_s'] + 2., bounds['turn_start_s']),
            'idle_after_turn': (bounds['turn_end_s'] + 2., bounds['forward'][1]['start_s']),
            'endpoint': tuple(bounds['evaluation_window_s'])}


def phase_at(time, phases):
    matches = [p['phase'] for p in phases if p['start_s'] <= time < p['end_s']]
    if len(matches) != 1:
        raise ValueError('Ambiguous phase')
    return matches[0]


def main(args):
    protocol_path = Path(__file__).with_name('protocol.json')
    if digest(protocol_path.read_bytes()) != EXPECTED_PROTOCOL_SHA256:
        raise ValueError('Frozen protocol changed')
    protocol = json.loads(protocol_path.read_text())
    if digest(args.review_zip.read_bytes()) != EXPECTED_REVIEW_SHA256:
        raise ValueError('Review archive changed')
    counts = {'PR31': verify_manifest(args.transfer_dir), 'PR32': verify_manifest(args.benefit_dir)}
    source = args.transfer_dir / 'results/fusion_trial/archived_sources/analyze_october_field_session.py'
    spec = importlib.util.spec_from_file_location('frozen_graph', source)
    graph = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(graph)
    bias = json.loads((args.transfer_dir / 'results/summary.json').read_text())['P1_bias_m']
    previous_tracks = read_csv(args.transfer_dir / 'results/fusion_trial/trajectories.csv')
    previous_endpoints = read_csv(args.benefit_dir / 'results/endpoint_comparison.csv')
    previous_stationary = read_csv(args.benefit_dir / 'results/stationary_diagnostics.csv')
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    trajectories, endpoints, stationary, residual_summary = [], [], [], []
    per_link, per_phase, step_rows, optimizers = [], [], [], []
    checks = {'dependency_manifest_files_checked': counts, 'protocol_sha256': EXPECTED_PROTOCOL_SHA256,
              'no_parameter_selection': True, 'continuous_truth_available': False,
              'new_imu_factor': False, 'reference_assumption_unchanged': True,
              'baseline_checks': [], 'input_checks': []}
    with zipfile.ZipFile(args.review_zip) as archive:
        prefix = 'repo/docs/field_tests/20261018/single_car_rebuilt_20261020_v1/'
        config_bytes = archive.read(prefix + 'frozen_config.json')
        config = json.loads(config_bytes)
        manifest = json.loads(archive.read(prefix + 'input_manifest.json'))
        base = config['graph_parameters']
        for key, value in [('range_sigma_m', .2), ('odom_translation_sigma_m', .03),
                           ('odom_yaw_sigma_deg', 2.), ('prior_position_sigma_m', .2),
                           ('prior_heading_sigma_deg', 5.)]:
            if base[key] != value:
                raise ValueError('Baseline parameter changed: ' + key)
        grid = list(itertools.product(protocol['grid']['range_sigma_scale'],
                                      protocol['grid']['odom_translation_sigma_scale']))
        for entry in manifest['selected_inputs']:
            run = entry['run']
            cache = archive.read(prefix + f'input_audit/{run}_decoded.json.gz')
            if digest(cache) != entry['cache_sha256']:
                raise ValueError('Cache changed: ' + run)
            data = json.loads(gzip.decompress(cache))
            bin_bytes = archive.read(prefix + f'baseline/{run}_range_bins.csv')
            bins = [r for r in csv.DictReader(io.StringIO(bin_bytes.decode())) if r['method'] == 'B']
            times = np.array(sorted({float(r['time_s']) for r in bins}))
            observations = [{r['node']: float(r['range_m']) for r in bins
                             if float(r['time_s']) == t and r['factor_present'] == 'True'} for t in times]
            if any(len(row) != 4 for row in observations):
                raise ValueError('Unexpected range support')
            raw_odom = np.asarray(data['odom'], dtype=float)
            raw_odom[:, 3] = np.unwrap(raw_odom[:, 3])
            local = np.column_stack([np.interp(times, raw_odom[:, 0], raw_odom[:, j]) for j in [1, 2, 3]])
            lever = np.array(config['base_to_antenna_body_xy_m'])
            heading = math.radians(config['initial_heading_deg'])
            start_base = np.array(config['candidate_start_antenna_xyz_m'][:2]) - graph.rotation(heading).dot(lever)
            old = sorted([r for r in previous_tracks if r['run'] == run and r['method'] == 'D'],
                         key=lambda r: float(r['time_s']))
            if not np.array_equal(times, [float(r['time_s']) for r in old]):
                raise ValueError('Previous keyframes differ')
            frozen_states = np.array([[float(r[k]) for k in ['base_x_m', 'base_y_m', 'yaw_rad']] for r in old])
            frozen_xy = np.array([[float(r[k]) for k in ['antenna_x_m', 'antenna_y_m']] for r in old])
            windows = stationary_windows(times, data['bounds'])
            phases = [phase_at(t, data['phases']) for t in times]
            checks['input_checks'].append({'run': run, 'cache_sha256': digest(cache),
                                          'bins_sha256': digest(bin_bytes), 'keyframes': len(times),
                                          'wall_factors': sum(map(len, observations)),
                                          'tf_topics_present': any(t in entry['topic_counts'] for t in ['/tf', '/tf_static']),
                                          'frames': entry['frames'], 'odom_child_frames': entry['odom_child_frames']})
            references = {r['method']: r for r in previous_endpoints if r['run'] == run}
            for range_scale, odom_scale in grid:
                cell = f'r{range_scale:g}_o{odom_scale:g}'
                ident = {'run': run, 'cell': cell, 'range_scale': range_scale, 'odom_translation_scale': odom_scale}
                parameters = dict(base, range_sigma_m=base['range_sigma_m'] * range_scale,
                                  odom_translation_sigma_m=base['odom_translation_sigma_m'] * odom_scale)
                print('SOLVING', run, cell, flush=True)
                try:
                    states, info = graph.optimize_graph(local, observations, config['anchors_xyz_m'], bias,
                            config['antenna_height_m'], start_base, heading, times, parameters,
                            tag_to_base_lever_xy_m=lever, raise_on_failure=False)
                    if not np.isfinite(states).all():
                        raise ValueError('Nonfinite iterate')
                except Exception as exc:
                    optimizers.append({**ident, 'parameters': parameters, 'optimizer_success': False,
                                       'exception': f'{type(exc).__name__}: {exc}'})
                    print('FAILED', run, cell, repr(exc), flush=True)
                    continue
                optimizers.append({**ident, 'parameters': parameters, **info})
                success = info['optimizer_success']
                common = {**ident, 'optimizer_success': success}
                xy = antenna_xy(states, lever)
                shift = np.linalg.norm(xy - frozen_xy, axis=1)
                low, high = windows['endpoint']
                sel = (times >= low) & (times < high)
                m = position_metrics(xy[sel])
                target = np.array(config['evaluation']['endpoints_xyz_m'][run][:2])
                endpoint_error = float(np.linalg.norm(np.array([m['median_x_m'], m['median_y_m']]) - target))
                endpoints.append({**common, 'range_sigma_m': parameters['range_sigma_m'],
                                  'odom_translation_sigma_m_at_1s': parameters['odom_translation_sigma_m'],
                                  'window_start_s': low, 'window_end_s': high, **m,
                                  'endpoint_difference_m': endpoint_error,
                                  'frozen_F_endpoint_difference_m': float(references['F']['endpoint_difference_m']),
                                  'U_endpoint_difference_m': float(references['U']['endpoint_difference_m']),
                                  'A_endpoint_difference_m': float(references['A']['endpoint_difference_m']),
                                  'trajectory_displacement_from_F_median_m': float(np.median(shift)),
                                  'trajectory_displacement_from_F_max_m': float(np.max(shift))})
                for phase, (low, high) in windows.items():
                    sel = (times >= low) & (times < high)
                    if sel.sum() < 2:
                        raise ValueError('Insufficient stationary samples')
                    stationary.append({**common, 'phase': phase, 'window_start_s': low, 'window_end_s': high,
                                       **position_metrics(xy[sel])})
                range_values, links, range_phases = [], [], []
                for i, row in enumerate(observations):
                    for node, raw_range in sorted(row.items()):
                        anchor = np.array(config['anchors_xyz_m'][node])
                        pred = math.sqrt(float(np.sum((xy[i] - anchor[:2]) ** 2)) + (config['antenna_height_m'] - anchor[2]) ** 2)
                        range_values.append(pred - (raw_range - bias[node]))
                        links.append(node)
                        range_phases.append(phases[i])
                range_values = np.array(range_values)
                body_error = body_increments(states) - body_increments(local)
                yaw_error = wrap(np.diff(states[:, 2]) - wrap(np.diff(local[:, 2])))
                dt = np.diff(times)
                translation_norm = np.linalg.norm(body_error, axis=1)
                normalized_range = range_values / parameters['range_sigma_m']
                robust_range = normalized_range * np.sqrt(2. / (np.sqrt(1. + normalized_range ** 2) + 1.))
                normalized_body = body_error / (parameters['odom_translation_sigma_m'] * np.sqrt(dt)[:, None])
                normalized_yaw = yaw_error / (math.radians(parameters['odom_yaw_sigma_deg']) * np.sqrt(dt))
                prior = np.r_[(states[0, :2] - start_base) / parameters['prior_position_sigma_m'],
                              wrap(states[0, 2] - heading) / math.radians(parameters['prior_heading_sigma_deg'])]
                recomputed_cost = .5 * float(np.sum(prior ** 2) + np.sum(normalized_body ** 2) +
                                            np.sum(normalized_yaw ** 2) + np.sum(robust_range ** 2))
                if not math.isclose(recomputed_cost, info['cost'], rel_tol=1e-12, abs_tol=1e-10):
                    raise ValueError('Independent objective reconstruction failed')
                residual_summary.append({**common, 'range_factors': len(range_values),
                    **{'range_' + k: v for k, v in statistics(range_values).items()},
                    'odom_step_translation_vector_RMS_m': float(np.sqrt(np.mean(translation_norm ** 2))),
                    'odom_step_translation_vector_p95_m': float(np.percentile(translation_norm, 95)),
                    'odom_step_yaw_RMS_deg': float(np.degrees(np.sqrt(np.mean(yaw_error ** 2)))),
                    'start_base_prior_displacement_m': float(np.linalg.norm(states[0, :2] - start_base)),
                    'start_heading_prior_difference_deg': float(np.degrees(wrap(states[0, 2] - heading))),
                    'objective_not_comparable_between_scales': info['cost'],
                    'reconstructed_cost_abs_difference': abs(recomputed_cost - info['cost'])})
                for node in sorted(set(links)):
                    per_link.append({**common, 'node': node, **statistics(range_values[np.array(links) == node])})
                for phase in dict.fromkeys(range_phases):
                    per_phase.append({**common, 'phase': phase, **statistics(range_values[np.array(range_phases) == phase])})
                for i, t in enumerate(times):
                    trajectories.append({**common, 'time_s': float(t), 'phase': phases[i],
                        'base_x_m': float(states[i, 0]), 'base_y_m': float(states[i, 1]), 'yaw_rad': float(states[i, 2]),
                        'antenna_x_m': float(xy[i, 0]), 'antenna_y_m': float(xy[i, 1]),
                        'displacement_from_F_m': float(shift[i])})
                for i in range(len(times) - 1):
                    step_rows.append({**common, 'from_time_s': float(times[i]), 'to_time_s': float(times[i + 1]),
                        'body_x_residual_m': float(body_error[i, 0]), 'body_y_residual_m': float(body_error[i, 1]),
                        'yaw_residual_deg': float(np.degrees(yaw_error[i]))})
                if range_scale == odom_scale == 1:
                    max_state = float(np.max(np.abs(states - frozen_states)))
                    max_xy = float(np.max(np.abs(xy - frozen_xy)))
                    end_diff = abs(endpoint_error - float(references['F']['endpoint_difference_m']))
                    if max_state > 1e-9 or max_xy > 1e-9 or end_diff > 1e-10:
                        raise ValueError('Frozen baseline did not reproduce')
                    max_static = 0.
                    for row in [s for s in stationary if s['run'] == run and s['cell'] == cell]:
                        before = next(s for s in previous_stationary if s['run'] == run and s['method'] == 'F' and s['phase'] == row['phase'])
                        max_static = max(max_static, abs(row['scatter_about_median_RMS_m'] - float(before['scatter_about_median_RMS_m'])))
                    if max_static > 1e-10:
                        raise ValueError('Previous stationary scatter differs')
                    checks['baseline_checks'].append({'run': run, 'max_state_abs_difference': max_state,
                        'max_antenna_xy_abs_difference_m': max_xy, 'endpoint_abs_difference_m': end_diff,
                        'stationary_scatter_max_abs_difference_m': max_static})
                print('DONE', run, cell, 'success', success, 'nfev', info['optimizer_nfev'],
                      'endpoint_m', endpoint_error, flush=True)
    for name, rows in [('endpoint_comparison.csv', endpoints), ('stationary_diagnostics.csv', stationary),
                       ('residual_summary.csv', residual_summary), ('residual_by_link.csv', per_link),
                       ('residual_by_phase.csv', per_phase), ('trajectories.csv', trajectories),
                       ('odom_step_residuals.csv', step_rows)]:
        write_csv(output / name, rows)
    write_json(output / 'optimizer_records.json', optimizers)
    checks.update({'attempted_solves': len(optimizers), 'successful_solves': sum(o['optimizer_success'] for o in optimizers),
                   'failed_or_nonconverged_cells': [dict(run=o['run'], cell=o['cell']) for o in optimizers if not o['optimizer_success']],
                   'endpoint_rows': len(endpoints), 'stationary_rows': len(stationary),
                   'trajectory_rows': len(trajectories), 'odom_step_rows': len(step_rows),
                   'objective_reconstruction_passed': True,
                   'protocol_unchanged_after_solves': digest(protocol_path.read_bytes()) == EXPECTED_PROTOCOL_SHA256})
    if checks['attempted_solves'] != 18 or len(checks['baseline_checks']) != 2:
        raise ValueError('Incomplete fixed protocol')
    write_json(output / 'checks.json', checks)
    write_json(output / 'summary.json', {'endpoints': endpoints, 'stationary': stationary,
        'residuals': residual_summary, 'checks': checks, 'provenance': {
            'base_main_sha': protocol['base_main_sha'], 'protocol_sha256': EXPECTED_PROTOCOL_SHA256,
            'script_sha256': digest(Path(__file__).read_bytes()), 'graph_source_sha256': digest(source.read_bytes()),
            'frozen_config_sha256': digest(config_bytes), 'review_archive_sha256': EXPECTED_REVIEW_SHA256,
            'transfer_summary_sha256': digest((args.transfer_dir / 'results/summary.json').read_bytes()),
            'benefit_endpoints_sha256': digest((args.benefit_dir / 'results/endpoint_comparison.csv').read_bytes()),
            'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__, 'scipy': scipy.__version__}})
    print(json.dumps(checks, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-zip', type=Path, required=True)
    parser.add_argument('--transfer-dir', type=Path, required=True)
    parser.add_argument('--benefit-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
