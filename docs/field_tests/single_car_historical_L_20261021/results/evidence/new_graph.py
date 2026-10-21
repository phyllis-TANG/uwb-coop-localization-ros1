#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only October 2026 session audit and single-car 2D batch-graph pilot.

Native ROS1 rosbag (Python 2.7/3) or rosbags (Python 3) is supported.
No ROS node, serial device, or motion publisher is initialized by this program.
"""
from __future__ import print_function

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import platform
import sys

import numpy as np
from scipy.optimize import least_squares, leastsq
from scipy.sparse import lil_matrix


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def wrap(value):
    return np.arctan2(np.sin(value), np.cos(value))


def rotation(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.asarray([[c, -s], [s, c]])


def header_seconds(msg):
    stamp = msg.header.stamp
    if hasattr(stamp, 'to_sec'):
        return stamp.to_sec()
    return float(stamp.sec) + float(stamp.nanosec) * 1e-9


def messages(path):
    try:
        import rosbag
    except ImportError:
        rosbag = None
    if rosbag is not None:
        with rosbag.Bag(path, 'r') as bag:
            for topic, msg, received in bag.read_messages():
                yield topic, msg, received.to_sec()
    else:
        from pathlib import Path
        from rosbags.highlevel import AnyReader
        with AnyReader([Path(path)]) as reader:
            for connection, timestamp, raw in reader.messages():
                yield (connection.topic,
                       reader.deserialize(raw, connection.msgtype),
                       timestamp * 1e-9)


def read_bag(path, anchor_ids):
    data = {'odom': [], 'uwb': [], 'imu': [], 'cmd': [], 'voltage': []}
    counts, tags, combinations = collections.Counter(), collections.Counter(), collections.Counter()
    offsets, stamps = collections.defaultdict(list), collections.defaultdict(list)
    first = last = None
    invalid = duplicate = 0
    frames, child_frames = collections.defaultdict(set), collections.defaultdict(set)
    for topic, msg, received in messages(path):
        counts[topic] += 1
        first = received if first is None else min(first, received)
        last = received if last is None else max(last, received)
        timestamp = received
        if hasattr(msg, 'header'):
            timestamp = header_seconds(msg)
            if not np.isfinite(timestamp) or timestamp <= 0:
                raise ValueError('Invalid header timestamp in ' + path)
            offsets[topic].append(received - timestamp)
            stamps[topic].append(timestamp)
            frames[topic].add(msg.header.frame_id)
        if topic.endswith('/uwb/ranges') or topic == '/lab/uwb/ranges':
            tags[msg.tag_id] += 1
            grouped = collections.defaultdict(list)
            for entry in msg.ranges:
                if entry.anchor_id in anchor_ids:
                    grouped[entry.anchor_id].append(float(entry.range))
            values = {}
            for key, value in grouped.items():
                if len(value) != 1:
                    duplicate += 1
                elif np.isfinite(value[0]) and value[0] > 0:
                    values[key] = value[0]
                else:
                    invalid += 1
            data['uwb'].append((timestamp, values, msg.tag_id))
            combinations['|'.join(sorted(values))] += 1
        elif topic == '/car2/odom':
            p, q = msg.pose.pose.position, msg.pose.pose.orientation
            norm = math.sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w)
            if not np.isfinite(norm) or norm < .5 or norm > 1.5:
                raise ValueError('Invalid Odom quaternion in ' + path)
            x, y, z, w = q.x/norm, q.y/norm, q.z/norm, q.w/norm
            yaw = math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
            data['odom'].append((timestamp, p.x, p.y, yaw))
            child_frames[topic].add(msg.child_frame_id)
        elif topic == '/car2/imu':
            data['imu'].append((timestamp, msg.angular_velocity.z))
        elif topic == '/car2/cmd_vel':
            data['cmd'].append((received, msg.linear.x, msg.linear.y, msg.angular.z))
        elif topic == '/car2/PowerVoltage':
            data['voltage'].append((received, float(msg.data)))
    if first is None:
        raise ValueError('Empty bag: ' + path)
    timing = {}
    for topic, values in stamps.items():
        delta = np.diff(values)
        timing[topic] = {
            'header_nonincreasing_steps': int(np.sum(delta <= 0)),
            'header_max_gap_s': float(np.max(delta)) if len(delta) else None,
            'bag_minus_header_median_s': float(np.median(offsets[topic])),
            'bag_minus_header_p95_s': float(np.percentile(offsets[topic], 95)),
            'negative_bag_minus_header_count': int(np.sum(np.asarray(offsets[topic]) < 0)),
        }
    info = {
        'bag_file': os.path.basename(path), 'sha256': sha256(path),
        'size_bytes': os.path.getsize(path), 'duration_s': last-first,
        'topic_counts': dict(counts), 'tag_id_counts': dict(tags),
        'usable_anchor_combinations': dict(combinations),
        'invalid_surveyed_range_entries': invalid,
        'duplicate_surveyed_id_groups': duplicate,
        'timing': timing,
        'header_frame_ids': dict((k, sorted(v)) for k, v in frames.items()),
        'child_frame_ids': dict((k, sorted(v)) for k, v in child_frames.items()),
    }
    if data['odom']:
        a = np.asarray(data['odom'])
        yaw = np.unwrap(a[:, 3])
        delta = a[-1, 1:3] - a[0, 1:3]
        info['odom'] = {
            'local_delta_xy_m': delta.tolist(),
            'net_displacement_m': float(np.linalg.norm(delta)),
            'path_m': float(np.sum(np.linalg.norm(np.diff(a[:, 1:3], axis=0), axis=1))),
            'yaw_change_deg': float(np.degrees(yaw[-1]-yaw[0])),
        }
    if data['voltage']:
        v = [r[1] for r in data['voltage']]
        info['voltage'] = {'first_v': v[0], 'last_v': v[-1], 'min_v': min(v)}
    info['command_counts'] = {
        'translation_nonzero': sum(math.hypot(r[1], r[2]) > .001 for r in data['cmd']),
        'angular_nonzero': sum(abs(r[3]) > .001 for r in data['cmd']),
    }
    data['start'] = first
    data['info'] = info
    return data


def solve_xy(values, anchors, height):
    ids = sorted(values)
    if len(ids) < 3:
        return np.asarray([np.nan, np.nan]), np.nan
    refs = np.asarray([anchors[k] for k in ids])
    if np.linalg.matrix_rank(refs[1:, :2] - refs[0, :2]) < 2:
        raise ValueError('Horizontally degenerate references')
    ranges = np.asarray([values[k] for k in ids])

    def residual(xy):
        return np.sqrt(np.sum((xy[None, :] - refs[:, :2])**2, axis=1) +
                       (height-refs[:, 2])**2) - ranges
    best = None
    for seed in ([2.665, 2.69], [0., 0.], [5.33, 5.38]):
        xy, _, _, _, status = leastsq(residual, seed, full_output=True)
        cost = float(np.sum(residual(xy)**2))
        if status in (1, 2, 3, 4) and (best is None or cost < best[0]):
            best = (cost, xy)
    if best is None:
        raise ValueError('XY optimization failed')
    return best[1], math.sqrt(best[0]/len(ids))


def bin_ranges(rows, key_times, half_width, tag='node_0'):
    observations = []
    for center in key_times:
        values = collections.defaultdict(list)
        for stamp, ranges, tag_id in rows:
            if tag_id == tag and abs(stamp-center) <= half_width:
                for key, value in ranges.items():
                    values[key].append(value)
        observations.append(dict((key, float(np.median(v)))
                                 for key, v in values.items() if len(v) >= 5))
    return observations


def window_ranges(rows, low, high):
    values = collections.defaultdict(list)
    for stamp, ranges, tag in rows:
        if tag == 'node_0' and low <= stamp < high:
            for key, value in ranges.items():
                values[key].append(value)
    return dict((k, float(np.median(v))) for k, v in values.items() if len(v) >= 10)


def align_odom(local, start_xyz, initial_heading):
    """Only the surveyed start and marked initial heading define this transform."""
    angle = initial_heading - local[0, 2]
    xy = np.dot(local[:, :2]-local[0, :2], rotation(angle).T) + np.asarray(start_xyz[:2])
    return np.column_stack((xy, local[:, 2] + angle))


def optimize_graph(local, observations, anchors, biases, height, start_xy,
                   heading, times, parameters, tag_to_base_lever_xy_m=None,
                   raise_on_failure=True):
    """Batch SE(2) states + between-Odom + robust range factors; no endpoint input."""
    n = len(local)
    if n < 3 or len(observations) != n:
        raise ValueError('Insufficient or inconsistent graph inputs')
    dt = np.diff(times)
    if np.any(dt <= 0):
        raise ValueError('Keyframe times must increase')
    lever = np.zeros(2) if tag_to_base_lever_xy_m is None else np.asarray(tag_to_base_lever_xy_m, dtype=float)
    if lever.shape != (2,) or not np.all(np.isfinite(lever)):
        raise ValueError('Invalid antenna lever arm')
    deltas = np.diff(local[:, :2], axis=0)
    co, si = np.cos(local[:-1, 2]), np.sin(local[:-1, 2])
    body_delta = np.column_stack((co*deltas[:, 0]+si*deltas[:, 1],
                                 -si*deltas[:, 0]+co*deltas[:, 1]))
    angle_delta = wrap(np.diff(local[:, 2]))
    sigma_xy = parameters['odom_translation_sigma_m'] * np.sqrt(dt)
    sigma_yaw = math.radians(parameters['odom_yaw_sigma_deg']) * np.sqrt(dt)
    samples = [(i, key, value-biases[key]) for i, row in enumerate(observations)
               for key, value in sorted(row.items())]
    if len(samples) < n:
        raise ValueError('Too few range factors')
    ki = np.asarray([s[0] for s in samples], dtype=int)
    refs = np.asarray([anchors[s[1]] for s in samples])
    measured = np.asarray([s[2] for s in samples])
    if np.any(measured <= 0):
        raise ValueError('Nonpositive bias-corrected range')

    def residual(flat):
        states = flat.reshape((n, 3))
        prior = np.r_[(states[0, :2]-start_xy)/parameters['prior_position_sigma_m'],
                      wrap(states[0, 2]-heading)/math.radians(parameters['prior_heading_sigma_deg'])]
        delta = np.diff(states[:, :2], axis=0)
        c, s = np.cos(states[:-1, 2]), np.sin(states[:-1, 2])
        body = np.column_stack((c*delta[:, 0]+s*delta[:, 1],
                                -s*delta[:, 0]+c*delta[:, 1]))
        between = np.column_stack(((body-body_delta)/sigma_xy[:, None],
                                    wrap(np.diff(states[:, 2])-angle_delta)/sigma_yaw))
        theta = states[ki, 2]
        antenna_xy = states[ki, :2] + np.column_stack((
            np.cos(theta)*lever[0]-np.sin(theta)*lever[1],
            np.sin(theta)*lever[0]+np.cos(theta)*lever[1]))
        predicted = np.sqrt(np.sum((antenna_xy-refs[:, :2])**2, axis=1) +
                            (height-refs[:, 2])**2)
        error = (predicted-measured)/parameters['range_sigma_m']
        # Pseudo-Huber only for ranges. Prior and Odom stay Gaussian.
        robust = error * np.sqrt(2./(np.sqrt(1.+error*error)+1.))
        return np.r_[prior, between.ravel(), robust]

    count = 3*n+len(samples)
    sparse = lil_matrix((count, 3*n), dtype=int)
    sparse[:3, :3] = 1
    for i in range(n-1):
        sparse[3+3*i:6+3*i, 3*i:6+3*i] = 1
    for j, index in enumerate(ki):
        sparse[3*n+j, 3*index:3*index+(3 if np.any(lever) else 2)] = 1
    initial = align_odom(local, list(start_xy)+[height], heading)
    result = least_squares(residual, initial.ravel(), jac_sparsity=sparse,
                           loss='linear', max_nfev=300, ftol=1e-7, xtol=1e-7, gtol=1e-7)
    if not result.success and raise_on_failure:
        raise ValueError('2D graph failed: ' + result.message)
    return result.x.reshape((n, 3)), {
        'optimizer_success': bool(result.success), 'optimizer_message': str(result.message),
        'optimizer_nfev': int(result.nfev), 'cost': float(result.cost),
        'optimizer_status': int(result.status), 'optimizer_optimality': float(result.optimality),
        'optimizer_njev': int(result.njev) if result.njev is not None else None,
        'keyframes': n, 'range_factors': len(samples), 'odom_between_factors': n-1,
    }


def write_json(path, value):
    with open(path, 'w') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def write_csv(path, fields, rows):
    with open(path, 'wb' if sys.version_info[0] == 2 else 'w') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(fields)
        writer.writerows(rows)


def endpoint_metrics(xy, start_reference, end_reference):
    start, end = np.asarray(xy[0]), np.asarray(xy[-1])
    reference_delta = np.asarray(end_reference)-np.asarray(start_reference)
    estimated_delta = end-start
    return {'start_xy_m': start.tolist(), 'end_xy_m': end.tolist(),
            'start_reference_difference_m': float(np.linalg.norm(start-start_reference)),
            'end_reference_difference_m': float(np.linalg.norm(end-end_reference)),
            'displacement_xy_m': estimated_delta.tolist(),
            'displacement_length_m': float(np.linalg.norm(estimated_delta)),
            'displacement_vector_difference_m': float(np.linalg.norm(estimated_delta-reference_delta))}


def endpoint_windows(data, low, high):
    """Keep the initial reference window clear of the first motion command."""
    motion = [row[0] for row in data['cmd']
              if math.hypot(row[1], row[2]) > .005 or abs(row[3]) > .04]
    start_end = min(low+5., min(motion)-.5) if motion else low+5.
    if start_end-low < 1.:
        raise ValueError('Less than 1 s of initial stationary reference data')
    return [(low, start_end), (high-5., high+1e-6)]


def gate_by_odom(values, pose, anchors, biases, height, threshold, rejected):
    kept = {}
    for key, measured in values.items():
        xyz = anchors[key]
        predicted = math.sqrt((pose[0]-xyz[0])**2 +
                              (pose[1]-xyz[1])**2 +
                              (height-xyz[2])**2) + biases[key]
        if abs(measured-predicted) <= threshold:
            kept[key] = measured
        else:
            rejected[key] += 1
    return kept


def analyze_run(data, run, config, biases, output):
    anchors, params = config['anchors_xyz_m'], config['graph_parameters']
    if any(data['info']['timing'][key]['header_nonincreasing_steps']
           for key in ['/car2/odom', '/car2/uwb/ranges', '/car2/imu']):
        raise ValueError('Nonmonotonic header timestamp in analysis input')
    odom = np.asarray(data['odom'])
    if len(odom) < 20 or not np.all(np.isfinite(odom)):
        raise ValueError('Invalid Odom input')
    odom[:, 3] = np.unwrap(odom[:, 3])
    low = max(odom[0, 0], data['uwb'][0][0])
    high = min(odom[-1, 0], data['uwb'][-1][0])
    # Stay within both sensor streams and leave room for each +/-0.4 s bin.
    times = np.arange(math.ceil(low-data['start']+1.),
                      math.floor(high-data['start']), params['keyframe_step_s']) + data['start']
    local = np.column_stack([np.interp(times, odom[:, 0], odom[:, j]) for j in [1, 2, 3]])
    exclusions = run.get('range_exclusions', [])
    filtered_uwb = []
    removed = 0
    for stamp, ranges, tag in data['uwb']:
        kept = dict(ranges)
        elapsed = stamp - data['start']
        for exclusion in exclusions:
            key = exclusion['anchor_id']
            if (exclusion['elapsed_start_s'] <= elapsed <
                    exclusion['elapsed_end_s'] and key in kept):
                del kept[key]
                removed += 1
        filtered_uwb.append((stamp, kept, tag))
    observations = bin_ranges(filtered_uwb, times, params['range_bin_half_width_s'])
    height = run['start_antenna_xyz_m'][2]
    start_ref = np.asarray(run['start_antenna_xyz_m'][:2])
    end_ref = np.asarray(run['end_antenna_xyz_m'][:2])
    heading = math.radians(run['initial_heading_deg'])
    aligned = align_odom(local, run['start_antenna_xyz_m'], heading)
    automatic_gate_m = run.get('odom_innovation_gate_m')
    gate_bin_rejections = collections.Counter()
    gate_endpoint_rejections = collections.Counter()
    if automatic_gate_m is not None:
        if automatic_gate_m <= 0:
            raise ValueError('Invalid odom innovation gate')
        observations = [
            gate_by_odom(row, pose, anchors, biases, height,
                         automatic_gate_m, gate_bin_rejections)
            for row, pose in zip(observations, aligned)
        ]
    raw, corrected, raw_fit, corrected_fit = [], [], [], []
    for values in observations:
        xy, rms = solve_xy(values, anchors, height)
        raw.append(xy)
        raw_fit.append(rms)
        xy, rms = solve_xy(dict((k, v-biases[k]) for k, v in values.items()), anchors, height)
        corrected.append(xy)
        corrected_fit.append(rms)
    raw, corrected = np.asarray(raw), np.asarray(corrected)
    missing_xy = [i for i, pair in enumerate(zip(raw, corrected))
                  if not (np.all(np.isfinite(pair[0])) and
                          np.all(np.isfinite(pair[1])))]
    if missing_xy and (automatic_gate_m is None or
                       any(len(observations[i]) >= 3 for i in missing_xy)):
        raise ValueError('Unexpected missing XY bins')
    missing_xy_s = [float(times[i]-data['start']) for i in missing_xy]
    graph, graph_info = optimize_graph(local, observations, anchors, biases, height,
                                        start_ref, heading, times, params)
    # Independent 5 s endpoint windows; graph/Odom use medians at the same times.
    windows = endpoint_windows(data, low, high)
    endpoints_raw, endpoints_corrected, endpoints_odom, endpoints_graph = [], [], [], []
    for left, right in windows:
        values = window_ranges(filtered_uwb, left, right)
        if automatic_gate_m is not None:
            window_states = (times >= left) & (times < right)
            if not np.any(window_states):
                raise ValueError('No Odom state for range gate window')
            window_pose = np.median(aligned[window_states, :2], axis=0)
            values = gate_by_odom(values, window_pose, anchors, biases,
                                  height, automatic_gate_m,
                                  gate_endpoint_rejections)
        endpoints_raw.append(solve_xy(values, anchors, height)[0])
        endpoints_corrected.append(solve_xy(dict((k, v-biases[k]) for k, v in values.items()), anchors, height)[0])
        select = (times >= left) & (times < right)
        if not np.any(select):
            raise ValueError('Empty endpoint state window')
        endpoints_odom.append(np.median(aligned[select, :2], axis=0))
        endpoints_graph.append(np.median(graph[select, :2], axis=0))
    result = {
        'label': run['label'], 'bag_file': data['info']['bag_file'],
        'endpoint_window_policy': 'initial <=5 s, ending 0.5 s before first motion command; final 5 s',
        'bag_sha256': data['info']['sha256'], 'endpoint_windows_elapsed_s':
            [[a-data['start'], b-data['start']] for a, b in windows],
        'manual_start_xyz_m': run['start_antenna_xyz_m'],
        'manual_end_xyz_m': run['end_antenna_xyz_m'],
        'initial_heading_deg': run['initial_heading_deg'],
        'initial_heading_source': run['initial_heading_source'],
        'usable_anchor_combinations': data['info']['usable_anchor_combinations'],
        'range_exclusions': exclusions,
        'range_values_removed': removed,
        'odom_innovation_gate_m': automatic_gate_m,
        'odom_gate_rejected_keyframe_bins': dict(gate_bin_rejections),
        'odom_gate_rejected_endpoint_windows': dict(gate_endpoint_rejections),
        'standalone_xy_unavailable_elapsed_s': missing_xy_s,
        'raw_uwb': endpoint_metrics(endpoints_raw, start_ref, end_ref),
        'corrected_uwb': endpoint_metrics(endpoints_corrected, start_ref, end_ref),
        'aligned_odom': endpoint_metrics(endpoints_odom, start_ref, end_ref),
        'batch_graph_2d': endpoint_metrics(endpoints_graph, start_ref, end_ref),
        'graph': graph_info,
        'raw_uwb_fit_rms_median_m': float(np.nanmedian(raw_fit)),
        'corrected_uwb_fit_rms_median_m': float(np.nanmedian(corrected_fit)),
        'timestamp_basis': 'Car2 message header time; bag reception times kept in manifest diagnostics',
        'method': 'single-car fixed-height SE(2) batch least-squares graph; not iSAM2; IMU diagnostic only',
        'tag_to_base_lever_arm_m': [0., 0., 0.],
        'lever_arm_status': 'unmeasured; zero horizontal offset is an explicit pilot approximation',
        'continuous_trajectory_ground_truth': False,
        'endpoint_used_in_optimizer': False,
    }
    imu = np.asarray(data['imu'])
    imask = (imu[:, 0] >= low) & (imu[:, 0] < low+5.)
    bias = float(np.median(imu[imask, 1]))
    integral = np.sum(.5*(imu[1:, 1]+imu[:-1, 1]-2*bias)*np.diff(imu[:, 0]))
    result['imu_diagnostic'] = {
        'initial_5s_gyro_z_median_rad_s': bias,
        'gyro_integrated_change_after_static_bias_deg': float(np.degrees(integral)),
        'odom_heading_change_deg': float(np.degrees(local[-1, 2]-local[0, 2])),
        'independent_sensor_status': 'on-board gyro and Odom yaw may share a source; no independent angle ground truth',
    }
    stem = run['label']
    write_json(os.path.join(output, stem+'_summary.json'), result)
    rows = []
    for i in range(len(times)):
        rows.append([times[i]-data['start']] + aligned[i, :2].tolist() + raw[i].tolist() +
                    corrected[i].tolist() + graph[i, :2].tolist() +
                    [float(np.degrees(graph[i, 2])), raw_fit[i], corrected_fit[i], len(observations[i])])
    write_csv(os.path.join(output, stem+'_trajectory.csv'),
              ['elapsed_s', 'odom_x_m', 'odom_y_m', 'raw_uwb_x_m', 'raw_uwb_y_m',
               'corrected_uwb_x_m', 'corrected_uwb_y_m', 'graph_x_m', 'graph_y_m',
               'graph_heading_deg', 'raw_range_fit_rms_m', 'corrected_range_fit_rms_m', 'references'], rows)
    plot_run(run, config, result, times-data['start'], aligned, raw, corrected, graph, output)
    return result


def plot_run(run, config, result, times, odom, raw, corrected, graph, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.3))
    methods = [('Aligned Odom', odom[:, :2], '#2471a3'),
               ('Raw UWB', raw, '#a6acaf'), ('Corrected UWB', corrected, '#e67e22'),
               ('2D batch graph', graph[:, :2], '#148f77')]
    for name, xy, color in methods:
        axes[0].plot(xy[:, 0], xy[:, 1], '.-', ms=2, lw=1.2, alpha=.85, color=color, label=name)
    refs = np.asarray([run['start_antenna_xyz_m'][:2], run['end_antenna_xyz_m'][:2]])
    axes[0].scatter(refs[:, 0], refs[:, 1], marker='x', s=100, color='#b03a2e', label='Manual start/end')
    axes[0].annotate('A', refs[0], xytext=(5, 7), textcoords='offset points')
    axes[0].annotate('Actual C', refs[1], xytext=(5, 7), textcoords='offset points')
    for key, xyz in config['anchors_xyz_m'].items():
        active = any(key in combination.split('|')
                     for combination in result['usable_anchor_combinations'])
        axes[0].plot(xyz[0], xyz[1], '^', color='black' if active else '#aaaaaa',
                     markerfacecolor='black' if active else 'none', ms=5)
        label = key if active else key+' (no data)'
        axes[0].annotate(label, xyz[:2], xytext=(3, 4), textcoords='offset points', fontsize=8)
    axes[0].set(xlabel='Room x (m)', ylabel='Room y (m)', title='Fixed height 0.20 m; preliminary manual survey')
    axes[0].set_aspect('equal', adjustable='box')
    axes[0].legend(fontsize=8)
    labels = ['Aligned\nOdom', 'Raw\nUWB', 'Corrected\nUWB', '2D batch\ngraph']
    keys = ['aligned_odom', 'raw_uwb', 'corrected_uwb', 'batch_graph_2d']
    errors = [result[k]['end_reference_difference_m'] for k in keys]
    bars = axes[1].bar(labels, errors, color=[m[2] for m in methods])
    for bar, value in zip(bars, errors):
        axes[1].text(bar.get_x()+bar.get_width()/2, value+.015, '%.3f' % value, ha='center', fontsize=9)
    axes[1].set(ylabel='Endpoint difference from manual reference (m)', title='Endpoint evaluation only; no trajectory ground truth')
    axes[1].set_ylim(0, max(errors)*1.23+.03)
    for ax in axes:
        ax.grid(alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle(run['label']+' | Odom + wall-UWB offline pilot', fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(output, run['label']+'_comparison.png'), dpi=160)
    plt.close(fig)


def self_test():
    anchors = {'a': [0., 0., 2.], 'b': [5., 0., 2.5], 'c': [5., 5., 2.], 'd': [0., 5., 2.3]}
    bias = dict((k, .3) for k in anchors)
    xy = [[2., 2., math.pi/2]]
    for i in range(1, 11):
        xy.append([2., 2.+i*.1, math.pi/2])
    for i in range(1, 11):
        xy.append([2., 3., math.pi/2-i*math.pi/20])
    for i in range(1, 11):
        xy.append([2.+i*.1, 3., 0.])
    truth = np.asarray(xy)
    # Arbitrary Odom origin/heading, including a quaternion-yaw wrap boundary.
    angle = math.radians(175)
    local = np.column_stack((np.dot(truth[:, :2]-truth[0, :2], rotation(angle).T)+[8., -3.],
                             truth[:, 2]+angle))
    observations = []
    for row in truth:
        observations.append(dict((k, float(np.linalg.norm(np.r_[row[:2], .2]-xyz)+bias[k]))
                                 for k, xyz in anchors.items()))
    params = {'odom_translation_sigma_m': .03, 'odom_yaw_sigma_deg': 2.,
              'range_sigma_m': .2, 'prior_position_sigma_m': .2, 'prior_heading_sigma_deg': 5.}
    result, _ = optimize_graph(local, observations, anchors, bias, .2, [2., 2.], math.pi/2,
                               np.arange(len(truth), dtype=float), params)
    assert np.max(np.abs(result-truth)) < 1e-5
    bad = [dict(row) for row in observations]
    bad[15]['a'] += 8.
    contaminated, _ = optimize_graph(local, bad, anchors, bias, .2, [2., 2.], math.pi/2,
                                     np.arange(len(truth), dtype=float), params)
    assert np.max(np.linalg.norm(contaminated[:, :2]-truth[:, :2], axis=1)) < .1
    recovered, _ = solve_xy(dict((k, v-bias[k]) for k, v in observations[-1].items()), anchors, .2)
    assert np.linalg.norm(recovered-truth[-1, :2]) < 1e-6
    try:
        solve_xy({'a': 1., 'b': 1., 'c': 1.},
                 {'a': [0., 0., 2.], 'b': [1., 0., 2.], 'c': [2., 0., 2.]}, .2)
    except ValueError:
        pass
    else:
        raise AssertionError('Degenerate geometry accepted')
    print('PASS: synthetic L shape, Odom frame invariance, yaw wrap, range outlier, degenerate geometry.')


def static_overview(data_root, cache, config, output):
    """Collect hash-checked retained static reports; recompute ABC link medians."""
    selected = [
        ('P1 R1', 'P1_raised_xy_analysis/MOBILE_P1_h1p00_clear_R1_20261011_020429'),
        ('P1 R2', 'P1_raised_xy_analysis/MOBILE_P1_h1p00_clear_R2_20261011_020505'),
        ('P2', 'multipoint_xy_analysis/MOBILE_P2_raised_LOS_20261011_021656'),
        ('P3', 'multipoint_xy_analysis/MOBILE_P3_h1p00_clear_20261011_022616'),
        ('P4', 'multipoint_xy_analysis/MOBILE_P4_h1p00_clear_20261011_023347'),
        ('P5 R1', 'multipoint_xy_analysis_P5_corrected/MOBILE_P5_raised_LOS_20261011_023837'),
        ('P5 R2', 'multipoint_xy_analysis_P5_corrected/MOBILE_P5_raised_LOS_20261011_025440'),
    ]
    records = []
    for label, sub in selected:
        path = os.path.join(data_root, '20261011', sub, 'summary.json')
        with open(path) as stream:
            value = json.load(stream)
        if value['bag_sha256'] != cache['20261011/'+value['bag_file']]['info']['sha256']:
            raise ValueError('Retained static report does not match source bag')
        record = dict((key, value[key]) for key in
                      ['bag_file', 'bag_sha256', 'manual_reference_xy_m', 'mean_xy_m', 'std_xy_m'])
        record.update({
            'label': label, 'source_summary_sha256': sha256(path),
            'source_summary_path': '20261011/'+sub+'/summary.json',
            'per_frame_reference_difference_mean_m': value['reference_difference_mean_m'],
            'per_frame_reference_difference_p95_m': value['reference_difference_p95_m'],
            'source': 'preserved field report; no bias correction',
        })
        records.append(record)
    write_json(os.path.join(output, 'raised_static_summary.json'), records)
    values = []
    for label, name in zip(['clear_A', 'human_B', 'clear_C'], [
            'MOBILE_P1_h0p20_clear_A_20261011_014350.bag',
            'MOBILE_P1_h0p20_human_B_20261011_014654.bag',
            'MOBILE_P1_h0p20_clear_C_20261011_014758.bag']):
        data = cache['20261011/'+name]
        collected = collections.defaultdict(list)
        for _, ranges, tag in data['uwb']:
            if tag == 'node_0':
                for key, value in ranges.items():
                    collected[key].append(value)
        values.append({'label': label, 'bag_file': name, 'bag_sha256': data['info']['sha256'],
                       'links': dict((k, {'median_m': float(np.median(v)),
                                          'std_m': float(np.std(v)), 'samples': len(v)})
                                     for k, v in collected.items())})
    write_json(os.path.join(output, 'human_obstruction_ABC.json'), values)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for key in ['node_10', 'node_2', 'node_3', 'node_8']:
        axes[0].plot(['clear_A', 'human_B', 'clear_C'],
                     [r['links'][key]['median_m'] for r in values], 'o-', label=key)
    axes[0].set(title='Low mounting: clear / obstruction / clear', ylabel='Median range (m)')
    axes[0].legend(fontsize=9)
    axes[0].grid(alpha=.2)
    errors = [r['per_frame_reference_difference_mean_m'] for r in records]
    bars = axes[1].bar([r['label'] for r in records], errors, color='#2471a3')
    for bar, value in zip(bars, errors):
        axes[1].text(bar.get_x()+bar.get_width()/2, value+.008, '%.3f' % value,
                     ha='center', fontsize=8)
    axes[1].set(title='Raised mounting: 1 m; raw UWB-only XY',
                ylabel='Mean per-frame difference from manual reference (m)', ylim=(0, max(errors)*1.25))
    axes[1].grid(axis='y', alpha=.2)
    axes[1].set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(output, 'static_and_obstruction_overview.png'), dpi=160)
    plt.close(fig)


def run_session(data_root, config, output):
    if not os.path.isdir(output):
        os.makedirs(output)
    anchors = config['anchors_xyz_m']
    bags, cache = [], {}
    for day in config.get('session_days', ('20261010', '20261011')):
        directory = os.path.join(data_root, day)
        for name in sorted(os.listdir(directory)):
            if not name.endswith('.bag'):
                continue
            relative = day+'/'+name
            data = read_bag(os.path.join(directory, name), anchors)
            data['info']['relative_path'] = relative
            data['info']['classification'] = config['experiments'].get(name, 'unreviewed')
            bags.append(data['info'])
            cache[relative] = data
    for relative, expected in config['known_sha256'].items():
        if cache[relative]['info']['sha256'] != expected:
            raise ValueError('Known SHA256 mismatch: ' + relative)
    write_json(os.path.join(output, 'bag_manifest.json'), bags)
    with open(os.path.join(output, 'SHA256SUMS.txt'), 'w') as stream:
        for row in bags:
            stream.write(row['sha256']+'  '+row['relative_path']+'\n')
    write_csv(os.path.join(output, 'bag_manifest.csv'),
              ['relative_path', 'sha256', 'size_bytes', 'duration_s', 'messages', 'classification'],
              [[r['relative_path'], r['sha256'], r['size_bytes'], '%.6f' % r['duration_s'],
                sum(r['topic_counts'].values()), r['classification']] for r in bags])
    calibration = cache[config['calibration']['bag']]
    point = np.asarray(config['calibration']['antenna_xyz_m'])
    collected = collections.defaultdict(list)
    for _, values, tag in calibration['uwb']:
        if tag == 'node_0':
            for key, value in values.items():
                collected[key].append(value)
    recomputed, biases = {}, config['calibration']['frozen_bias_m']
    for key, xyz in anchors.items():
        estimate = float(np.median(collected[key])-np.linalg.norm(point-np.asarray(xyz)))
        if abs(estimate-biases[key]) > .001:
            raise ValueError('Frozen calibration not reproduced: ' + key)
        recomputed[key] = estimate
    write_json(os.path.join(output, 'calibration.json'), {
        'source_bag': config['calibration']['bag'], 'source_sha256': calibration['info']['sha256'],
        'reference_xyz_m': point.tolist(), 'recomputed_bias_m': recomputed,
        'frozen_bias_used_m': biases, 'evaluation_bags_used_for_calibration': False,
        'interpretation': 'site/height/mounting-specific median residual; includes survey/model effects',
    })
    results = []
    for run in config['runs_2d']:
        result = analyze_run(cache[run['bag']], run, config, biases, output)
        results.append(result)
        print(run['label'], dict((key, round(result[key]['end_reference_difference_m'], 4))
                                for key in ['aligned_odom', 'raw_uwb', 'corrected_uwb', 'batch_graph_2d']))
    write_json(os.path.join(output, 'two_dimensional_summary.json'), results)
    if config.get('include_static_overview', True):
        static_overview(data_root, cache, config, output)
    write_csv(os.path.join(output, 'two_dimensional_comparison.csv'),
              ['run', 'method', 'end_x_m', 'end_y_m', 'endpoint_reference_difference_m',
               'displacement_vector_difference_m'],
              [[r['label'], key]+r[key]['end_xy_m']+
               [r[key]['end_reference_difference_m'], r[key]['displacement_vector_difference_m']]
               for r in results for key in ['aligned_odom', 'raw_uwb', 'corrected_uwb', 'batch_graph_2d']])
    import scipy
    write_json(os.path.join(output, 'analysis_provenance.json'), {
        'python_version': platform.python_version(), 'numpy_version': np.__version__,
        'scipy_version': scipy.__version__, 'analysis_script_sha256': sha256(__file__),
        'config_content_sha256': hashlib.sha256(json.dumps(config, sort_keys=True).encode('utf-8')).hexdigest(),
        'input_bags_read': len(bags), 'configured_known_hashes_verified': len(config['known_sha256']),
        'new_analysis_timestamp_basis': 'Car2 header timestamps',
        'historical_analysis_timestamp_basis': 'bag reception timestamps; preserved in original scripts',
        'clock_correction_applied': False, 'raw_input_files_modified': False,
    })
    print('Audited %d bags; all configured known hashes and calibration checks passed.' % len(bags))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--data-root', help='Directory containing 20261010 and 20261011')
    parser.add_argument('--config')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not all([args.data_root, args.config, args.output_dir]):
        parser.error('Require --data-root, --config, --output-dir')
    with open(args.config) as stream:
        config = json.load(stream)
    run_session(args.data_root, config, args.output_dir)


if __name__ == '__main__':
    main()
