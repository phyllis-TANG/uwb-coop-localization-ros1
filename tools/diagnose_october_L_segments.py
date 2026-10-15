#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only phase and stationary-range diagnostics; no endpoint-based tuning."""
from __future__ import print_function
import argparse
import collections
import csv
import json
import math
import os
import sys

import numpy as np
import analyze_october_field_session as core


def phase_bounds(data):
    cmd = np.asarray(data['cmd'])
    translating = np.hypot(cmd[:, 1], cmd[:, 2]) > .005
    turning = (~translating) & (np.abs(cmd[:, 3]) > .04)
    if not np.any(translating) or not np.any(turning):
        raise ValueError('Expected both translation and in-place turn commands')
    turn = cmd[turning, 0]
    before = cmd[translating & (cmd[:, 0] < turn[0]), 0]
    after = cmd[translating & (cmd[:, 0] > turn[-1]), 0]
    if not len(before) or not len(after):
        raise ValueError('Could not identify two translation segments')
    return {'first_motion': float(before[0]), 'first_turn': float(turn[0]),
            'last_turn': float(turn[-1]), 'second_translation': float(after[0]),
            'last_translation': float(after[-1])}


def endpoint_link_stats(data, run, config, windows):
    result = []
    for label, point, window in zip(['start', 'end'],
                                   [run['start_antenna_xyz_m'], run['end_antenna_xyz_m']], windows):
        values = collections.defaultdict(list)
        for t, ranges, tag in data['uwb']:
            if tag == 'node_0' and window[0] <= t < window[1]:
                for key, value in ranges.items():
                    values[key].append(value)
        for key, v in sorted(values.items()):
            expected = float(np.linalg.norm(np.asarray(point)-config['anchors_xyz_m'][key]))
            median = float(np.median(v))
            result.append({'endpoint': label, 'anchor': key, 'samples': len(v),
                           'raw_median_m': median, 'range_std_m': float(np.std(v)),
                           'manual_geometry_m': expected,
                           'frozen_bias_m': config['calibration']['frozen_bias_m'][key],
                           'corrected_minus_manual_geometry_m': median-
                               config['calibration']['frozen_bias_m'][key]-expected})
    return result


def diagnose(data, run, config, trajectory, output):
    odom = np.asarray(data['odom'])
    odom[:, 3] = np.unwrap(odom[:, 3])
    low = max(odom[0, 0], data['uwb'][0][0])
    high = min(odom[-1, 0], data['uwb'][-1][0])
    windows = core.endpoint_windows(data, low, high)
    bounds = phase_bounds(data)
    with open(trajectory) as stream:
        rows = list(csv.DictReader(stream))
    t = np.asarray([float(r['elapsed_s']) for r in rows])+data['start']
    aligned = np.asarray([[float(r['odom_x_m']), float(r['odom_y_m'])] for r in rows])
    graph_xy = np.asarray([[float(r['graph_x_m']), float(r['graph_y_m'])] for r in rows])
    local = np.column_stack([np.interp(t, odom[:, 0], odom[:, j]) for j in [1, 2, 3]])
    observations = core.bin_ranges(data['uwb'], t, config['graph_parameters']['range_bin_half_width_s'])
    phases = [('initial', low, bounds['first_motion']),
              ('first_translation', bounds['first_motion'], bounds['first_turn']),
              ('turn_and_settle', bounds['first_turn'], bounds['second_translation']),
              ('second_translation', bounds['second_translation'], bounds['last_translation']),
              ('final_stationary', bounds['last_translation']+2., high)]
    phase_results = []
    for label, a, b in phases:
        selected = (t >= a) & (t < b)
        if selected.any():
            separation = np.linalg.norm(graph_xy[selected]-aligned[selected], axis=1)
            phase_results.append({'phase': label, 'elapsed_window_s': [a-data['start'], b-data['start']],
                                  'keyframes': int(selected.sum()),
                                  'graph_minus_aligned_odom_median_m': float(np.median(separation)),
                                  'graph_minus_aligned_odom_max_m': float(np.max(separation)),
                                  'interpretation': 'sensor/model disagreement, not trajectory error'})
    tail_results = []
    for extra in [10., 30., None]:
        stop = high if extra is None else min(high, bounds['last_translation']+extra)
        selected = t <= stop
        times, poses = t[selected], local[selected]
        ranges = [row for row, keep in zip(observations, selected) if keep]
        if extra is None:
            xy = graph_xy
        else:
            graph, _ = core.optimize_graph(poses, ranges, config['anchors_xyz_m'],
                config['calibration']['frozen_bias_m'], run['start_antenna_xyz_m'][2],
                np.asarray(run['start_antenna_xyz_m'][:2]), math.radians(run['initial_heading_deg']),
                times, config['graph_parameters'])
            xy = graph[:, :2]
        # All variants finish well after the final translation; endpoint used only here.
        end = np.median(xy[(times >= stop-5.) & (times <= stop)], axis=0)
        tail_results.append({'tail': 'full_recording' if extra is None else 'motion_end_plus_%ds' % extra,
                             'last_keyframe_elapsed_s': float(times[-1]-data['start']),
                             'end_xy_m': end.tolist(), 'endpoint_difference_m': float(np.linalg.norm(
                                 end-np.asarray(run['end_antenna_xyz_m'][:2]))),
                             'weights_and_calibration_unchanged': True})
    stationary = []
    for delta in [0., 10., 30., 60.]:
        a = bounds['last_translation']+2.+delta
        b = a+8.
        if b > high:
            continue
        values = core.window_ranges(data['uwb'], a, b)
        corrected = dict((k, v-config['calibration']['frozen_bias_m'][k]) for k, v in values.items())
        xy, rms = core.solve_xy(corrected, config['anchors_xyz_m'], run['start_antenna_xyz_m'][2])
        oo = odom[(odom[:, 0] >= a) & (odom[:, 0] < b), 1:3]
        stationary.append({'elapsed_window_s': [a-data['start'], b-data['start']],
                           'odom_xy_span_m': np.ptp(oo, axis=0).tolist(),
                           'median_ranges_m': values, 'corrected_uwb_xy_m': xy.tolist(),
                           'range_fit_rms_m': rms})
    result = {'label': run['label'], 'bag_sha256': data['info']['sha256'],
              'diagnostic_script_sha256': core.sha256(__file__),
              'baseline_trajectory_csv_sha256': core.sha256(trajectory),
              'bounds_elapsed_s': dict((k, v-data['start']) for k, v in bounds.items()),
              'initial_stationary_window_elapsed_s': [v-data['start'] for v in windows[0]],
              'endpoint_links': endpoint_link_stats(data, run, config, windows),
              'phases': phase_results, 'static_tail_variants': tail_results,
              'post_motion_windows': stationary,
              'parameter_policy': 'same frozen calibration and graph weights; all tail variants reported; none selected to replace baseline',
              'continuous_ground_truth': False}
    core.write_json(os.path.join(output, run['label']+'_diagnostics.json'), result)
    plot(data, run, config, bounds, odom, t, aligned, observations, output)
    return result


def plot(data, run, config, bounds, odom, key_times, aligned, observations, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    cmd = np.asarray(data['cmd'])
    axes[0].step(cmd[:, 0]-data['start'], cmd[:, 1], where='post', label='Command vx (m/s)')
    axes[0].step(cmd[:, 0]-data['start'], cmd[:, 3], where='post', label='Command wz (rad/s)')
    axes[0].set_ylabel('Command')
    axes[0].legend(loc='upper right', fontsize=8)
    axes[1].plot(odom[:, 0]-data['start'], np.degrees(odom[:, 3]-odom[0, 3]), label='Odom heading change')
    axes[1].set_ylabel('Relative heading (deg)')
    axes[1].legend(loc='upper right', fontsize=8)
    for key in ['node_10', 'node_2', 'node_3']:
        measured = np.asarray([r.get(key, np.nan) for r in observations])
        ref = np.asarray(config['anchors_xyz_m'][key])
        expected = np.sqrt(np.sum((aligned-ref[:2])**2, axis=1)+(run['start_antenna_xyz_m'][2]-ref[2])**2)
        residual = measured-config['calibration']['frozen_bias_m'][key]-expected
        axes[2].plot(key_times-data['start'], residual, label=key)
    axes[2].set_ylabel('Range discrepancy (m)')
    axes[2].set_xlabel('Bag elapsed time (s); sensor alignment uses Car2 headers')
    axes[2].legend(loc='upper right', fontsize=8)
    axes[2].axhline(0., color='black', lw=.7)
    for ax in axes:
        ax.axvspan(bounds['first_turn']-data['start'], bounds['second_translation']-data['start'],
                   color='#b39ddb', alpha=.18)
        ax.axvline(bounds['last_translation']-data['start'], color='gray', ls='--', lw=.8)
        ax.grid(alpha=.2)
    fig.suptitle(run['label']+': turn shaded; final command dashed\nCorrected range minus Odom geometry; NOT ground-truth error', fontsize=11)
    fig.tight_layout(rect=[.025, 0., 1., .94])
    fig.savefig(os.path.join(output, run['label']+'_phase_diagnostics.png'), dpi=150)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root', required=True)
    p.add_argument('--config', required=True)
    p.add_argument('--base-results', required=True)
    p.add_argument('--output-dir', required=True)
    args = p.parse_args()
    with open(args.config) as stream:
        config = json.load(stream)
    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)
    timeline = []
    for day in ['20261010', '20261011']:
        for name in sorted(os.listdir(os.path.join(args.data_root, day))):
            if not name.endswith('.bag'):
                continue
            data = core.read_bag(os.path.join(args.data_root, day, name), config['anchors_xyz_m'])
            count = sum('node_8' in values for _, values, _ in data['uwb'])
            timeline.append([day+'/'+name, data['info']['sha256'], data['start'], len(data['uwb']), count,
                             '|'.join(sorted(data['info']['tag_id_counts']))])
    core.write_csv(os.path.join(args.output_dir, 'N8_visibility.csv'),
                   ['bag', 'sha256', 'bag_start_epoch_s', 'uwb_frames', 'valid_node_8_target_frames', 'source_tag_ids'],
                   sorted(timeline, key=lambda r: r[2]))
    all_results = []
    for run in config['runs_2d']:
        data = core.read_bag(os.path.join(args.data_root, run['bag']), config['anchors_xyz_m'])
        if data['info']['sha256'] != config['known_sha256'][run['bag']]:
            raise ValueError('Diagnostic input bag SHA256 mismatch')
        trajectory = os.path.join(args.base_results, run['label']+'_trajectory.csv')
        result = diagnose(data, run, config, trajectory, args.output_dir)
        all_results.append(result)
        print(run['label'], 'initial window', result['initial_stationary_window_elapsed_s'])
        print('tail endpoint differences', [(r['tail'], round(r['endpoint_difference_m'], 4))
                                           for r in result['static_tail_variants']])
    core.write_json(os.path.join(args.output_dir, 'segmented_diagnostics.json'), all_results)


if __name__ == '__main__':
    main()
