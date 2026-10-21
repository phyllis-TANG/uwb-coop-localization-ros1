#!/usr/bin/env python3
"""Independently reconstruct numerical comparisons from saved normal files."""
import collections
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def read(name):
    with (ROOT / 'results' / name).open(newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    results = ROOT / 'results'
    summary = json.loads((results / 'summary.json').read_text())
    tracks = read('trajectories.csv')
    grouped = collections.defaultdict(list)
    for row in tracks:
        grouped[row['case'], row['method']].append(row)
    tests = []
    protocol_sha = hashlib.sha256((ROOT / 'protocol.json').read_bytes()).hexdigest()
    assert protocol_sha == summary['provenance']['protocol_sha256']
    assert len(tracks) == 3400 and len(read('keyframe_inputs.csv')) == 1407
    assert len(summary['optimizers']) == 15
    assert all(row['optimizer_success'] for row in summary['optimizers'])
    assert all(x['motion_command_count'] == 0 and x['odom_path_m'] == 0.
               for c in summary['cases'] for x in c['window_checks'])
    tests.append('frozen_protocol_complete_cases_and_stationary_diagnostics')
    for case in summary['cases']:
        cid = case['case']['id']
        for a, b in zip(grouped[cid, 'G_old'], grouped[cid, 'G_new0']):
            for key in ['base_x_m', 'base_y_m', 'yaw_rad', 'antenna_x_m', 'antenna_y_m']:
                assert abs(float(a[key]) - float(b[key])) < 1e-12
    tests.append('old_new_zero_lever_all_states_equivalent')
    static = read('stationary_diagnostics.csv')
    assert len(static) == 72
    for row in static:
        selected = [t for t in grouped[row['case'], row['method']]
                    if float(row['window_start_elapsed_s']) <= float(t['elapsed_s']) < float(row['window_end_elapsed_s'])]
        xy = np.array([[float(t['antenna_x_m']), float(t['antenna_y_m'])] for t in selected])
        center = np.median(xy, axis=0)
        assert len(xy) == int(row['samples'])
        error = math.dist(center, [float(row['reference_x_m']), float(row['reference_y_m'])])
        scatter = math.sqrt(sum(math.dist(p, center) ** 2 for p in xy) / len(xy))
        assert abs(error - float(row['reference_difference_m'])) < 1e-12
        assert abs(scatter - float(row['scatter_about_median_RMS_m'])) < 1e-12
        assert abs(math.dist(xy[-1], xy[0]) - float(row['first_last_displacement_m'])) < 1e-12
    tests.append('all_72_window_positions_scatter_and_drift_reconstructed')
    endpoints = read('endpoint_comparison.csv')
    assert len(endpoints) == 48
    index = {(r['case'], r['method'], r['window']): r for r in static}
    for row in endpoints:
        assert row == index[row['case'], row['method'], row['window']]
    tests.append('all_48_endpoint_rows_and_both_windows_consistent')
    for method_group in grouped.values():
        for row in method_group:
            if not row['base_x_m']:
                continue
            lever = [.12, -.08] if row['method'] == 'G_assumedL' else [0., 0.]
            yaw = float(row['yaw_rad'])
            expected = [float(row['base_x_m']) + math.cos(yaw) * lever[0] - math.sin(yaw) * lever[1],
                        float(row['base_y_m']) + math.sin(yaw) * lever[0] + math.cos(yaw) * lever[1]]
            assert math.dist(expected, [float(row['antenna_x_m']), float(row['antenna_y_m'])]) < 1e-12
    tests.append('rotating_antenna_geometry_reconstructed_for_all_pose_states')
    inputs = {(r['case'], r['elapsed_s'], r['node']): r for r in read('keyframe_inputs.csv')}
    poses = {(r['case'], r['method'], r['elapsed_s']): r for r in tracks}
    case_info = {c['case']['id']: c for c in summary['cases']}
    configs = {day: json.loads((results / 'evidence' / (day + '_config.json')).read_text())
               for day in ['20261010_11', '20261017']}
    errors = []
    residual_groups = collections.defaultdict(list)
    for row in read('range_residuals.csv'):
        inp = inputs[row['case'], row['elapsed_s'], row['node']]
        pose = poses[row['case'], row['method'], row['elapsed_s']]
        info = case_info[row['case']]
        anchor = configs[info['case']['day']]['anchors_xyz_m'][row['node']]
        height = info['run']['start_antenna_xyz_m'][2]
        predicted = math.dist([float(pose['antenna_x_m']), float(pose['antenna_y_m']), height], anchor)
        if row['method'] == 'G_raw':
            bias = 0.
        elif row['method'] in ['G_old', 'G_new0']:
            bias = float(inp['frozen_bias_m'])
        else:
            bias = float(inp['full_P1_bias_m'])
        expected = predicted - (float(inp['range_m']) - bias)
        errors.append(abs(expected - float(row['residual_m'])))
        residual_groups[row['case'], row['method']].append(expected)
    assert len(errors) == 7035 and max(errors) < 1e-12
    for row in read('residual_summary.csv'):
        values = residual_groups[row['case'], row['method']]
        rms = math.sqrt(sum(v * v for v in values) / len(values))
        assert abs(rms - float(row['range_RMS_m'])) < 1e-12
    tests.append('all_7035_physical_range_residuals_and_rms_reconstructed')
    old_results = read('legacy_reproduction.csv')
    assert len(old_results) == 3
    assert max(float(row['absolute_difference_m']) for row in old_results) < 1e-8
    for row in old_results:
        if row['case'].startswith('oct11'):
            assert float(row['absolute_difference_m']) == 0.
    tests.append('historical_endpoint_reproduction_under_1e-8_m')
    verification = {'checks_passed': len(tests), 'checks': tests, 'success': True,
        'endpoint_rows': len(endpoints), 'stationary_rows': len(static), 'trajectory_rows': len(tracks),
        'range_residual_rows': len(errors), 'max_independent_range_difference_m': max(errors),
        'verification_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (results / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
    print(json.dumps(verification, indent=2))


if __name__ == '__main__':
    main()
