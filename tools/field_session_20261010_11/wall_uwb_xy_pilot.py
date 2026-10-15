#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Read-only fixed-height XY pilot. Python 2.7 / ROS Melodic compatible."""
from __future__ import print_function
import argparse
import csv
import hashlib
import json
import os
import sys
import numpy as np

# Preliminary survey, metres. Right-wall x = 5.33 - 0.10, layout-derived.
ANCHORS = {
    'node_8': [0.10, 2.38, 2.22],
    'node_10': [3.27, 0.10, 2.35],
    'node_3': [5.23, 2.91, 2.33],
    'node_2': [5.23, 5.12, 2.88],
}
RUNS = [
    ('WALL_N8_N2_N3_N10_static_20261010_061958.bag', '/lab/uwb/ranges', 'node_8'),
    ('WALL_N10_N2_N3_N8_static_20261010_064512.bag', '/lab/n10/uwb/ranges', 'node_10'),
    ('WALL_N3_N2_N8_N10_static_20261010_070846.bag', '/lab/n3/uwb/ranges', 'node_3'),
]

def distances(xy, refs, height):
    delta = xy[:, None, :] - refs[None, :, :2]
    return np.sqrt(np.sum(delta * delta, axis=2) +
                   (height - refs[None, :, 2]) ** 2)

def solve_xy(ranges, refs, height):
    """Independent per-frame multi-start LM; no wall constraint or filtering."""
    n = len(ranges)
    best_xy = np.zeros((n, 2))
    best_cost = np.full(n, np.inf)
    # Squared-range linear seed plus nine independent room-grid seeds.
    matrix = 2.0 * (refs[1:, :2] - refs[0, :2])
    const = (np.sum(refs[1:, :2] ** 2, axis=1) -
             np.sum(refs[0, :2] ** 2) +
             (height - refs[1:, 2]) ** 2 - (height - refs[0, 2]) ** 2)
    rhs = ranges[:, :1] ** 2 - ranges[:, 1:] ** 2 + const[None, :]
    seeds = [np.dot(rhs, np.linalg.pinv(matrix).T)]
    seeds += [np.tile([x, y], (n, 1))
              for x in (0.0, 2.665, 5.33) for y in (0.0, 2.69, 5.38)]
    for seed in seeds:
        xy = seed.copy()
        damping = np.full(n, 1e-3)
        for _ in range(60):
            pred = distances(xy, refs, height)
            residual = pred - ranges
            jac = (xy[:, None, :] - refs[None, :, :2]) / np.maximum(pred[:, :, None], 1e-12)
            jx, jy = jac[:, :, 0], jac[:, :, 1]
            aa = np.sum(jx * jx, axis=1) + damping
            bb = np.sum(jx * jy, axis=1)
            cc = np.sum(jy * jy, axis=1) + damping
            gx = np.sum(jx * residual, axis=1)
            gy = np.sum(jy * residual, axis=1)
            det = np.maximum(aa * cc - bb * bb, 1e-20)
            step = np.column_stack(((cc * gx - bb * gy) / det,
                                    (aa * gy - bb * gx) / det))
            trial = xy - step
            before = np.sum(residual ** 2, axis=1)
            after = np.sum((distances(trial, refs, height) - ranges) ** 2, axis=1)
            accept = after < before
            xy[accept] = trial[accept]
            damping = np.where(accept, np.maximum(damping / 3.0, 1e-12),
                               np.minimum(damping * 10.0, 1e12))
        cost = np.sum((distances(xy, refs, height) - ranges) ** 2, axis=1)
        improve = cost < best_cost
        best_xy[improve] = xy[improve]
        best_cost[improve] = cost[improve]
    return best_xy, np.sqrt(best_cost / ranges.shape[1])

def self_test():
    for tag in ('node_8', 'node_10', 'node_3', 'mobile'):
        ids = sorted(k for k in ANCHORS if k != tag)
        refs = np.array([ANCHORS[k] for k in ids], dtype=float)
        height = ANCHORS[tag][2] if tag in ANCHORS else 0.45
        truth = np.array([ANCHORS[tag][:2]]) if tag in ANCHORS else np.array([[1.0, 1.0], [2.0, 2.0], [4.0, 4.0]])
        xy, rms = solve_xy(distances(truth, refs, height), refs, height)
        assert np.max(np.abs(xy - truth)) < 1e-6, (tag, xy, truth)
        assert np.max(rms) < 1e-6
    print('PASS: exact synthetic 3D ranges recover fixed-height XY.')

def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def analyze(path, topic, tag, height, reference, out_root):
    import rosbag
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ids = sorted(k for k in ANCHORS if k != tag)
    refs = np.array([ANCHORS[k] for k in ids], dtype=float)
    rows, total, wrong_tag, missing, bad = [], 0, 0, 0, 0
    with rosbag.Bag(path, 'r') as bag:
        for _, msg, received in bag.read_messages(topics=[topic]):
            total += 1
            if msg.tag_id != tag:
                wrong_tag += 1
                continue
            groups = dict((k, []) for k in ids)
            for entry in msg.ranges:
                if entry.anchor_id in groups:
                    groups[entry.anchor_id].append(float(entry.range))
            chosen = [k for k in ids if len(groups[k]) == 1 and
                      np.isfinite(groups[k][0]) and groups[k][0] > 0]
            if any(len(v) > 1 or any(not np.isfinite(x) or x <= 0 for x in v)
                   for v in groups.values()):
                bad += 1
                continue
            if len(chosen) < 3:
                missing += 1
                continue
            rows.append((received.to_sec(), msg.header.stamp.to_sec(), chosen,
                         [groups[k][0] for k in chosen]))
    if not rows:
        raise RuntimeError('No complete frames with >=3 surveyed references. Check topic, tag ID and powered nodes.')
    # Group by available references; use every valid surveyed reference in frame.
    xy = np.zeros((len(rows), 2))
    rms = np.zeros(len(rows))
    for key in sorted(set(tuple(row[2]) for row in rows)):
        index = [i for i, row in enumerate(rows) if tuple(row[2]) == key]
        group_refs = np.array([ANCHORS[k] for k in key], dtype=float)
        group_ranges = np.array([rows[i][3] for i in index], dtype=float)
        if np.linalg.matrix_rank(group_refs[1:, :2] - group_refs[0, :2]) < 2:
            raise RuntimeError('References are horizontally collinear; cannot uniquely solve XY.')
        xy[index], rms[index] = solve_xy(group_ranges, group_refs, height)
    out = os.path.join(out_root, os.path.splitext(os.path.basename(path))[0])
    if not os.path.isdir(out):
        os.makedirs(out)
    t = np.array([row[0] for row in rows])
    rel_t = t - t[0]
    result = {
        'bag_file': os.path.basename(path), 'bag_sha256': file_sha(path),
        'topic': topic, 'tag_id': tag, 'frames': total,
        'solved_frames': len(rows), 'solved_percent': 100.0 * len(rows) / total,
        'wrong_tag_frames': wrong_tag, 'insufficient_references_frames': missing,
        'invalid_or_duplicate_frames': bad,
        'height_fixed_m': height, 'preliminary_reference_coordinates_m': ANCHORS,
        'right_wall_x_source': 'layout-derived: 5.33 m minus 0.10 m inset',
        'model': '3D ranges; fixed surveyed height; unweighted nonlinear XY least squares',
        'timestamp_basis': 'bag reception time; original header time also preserved',
        'bias_correction': 'none', 'temporal_filtering': 'none', 'wall_constraint': 'none',
        'fusion': False, 'independent_accuracy_validation': False,
        'mean_xy_m': np.mean(xy, axis=0).tolist(),
        'std_xy_m': np.std(xy, axis=0).tolist(),
        'range_fit_rms_median_m': float(np.median(rms)),
        'range_fit_rms_p95_m': float(np.percentile(rms, 95)),
        'outside_nominal_rectangle_frames': int(np.sum((xy[:, 0] < 0) | (xy[:, 0] > 5.33) | (xy[:, 1] < 0) | (xy[:, 1] > 5.38))),
    }
    if reference is not None:
        diff = np.sqrt(np.sum((xy - np.array(reference)) ** 2, axis=1))
        result.update({'manual_reference_xy_m': list(reference),
                       'reference_difference_mean_m': float(np.mean(diff)),
                       'reference_difference_p95_m': float(np.percentile(diff, 95))})
    with open(os.path.join(out, 'summary.json'), 'w') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    stream = open(os.path.join(out, 'xy_estimates.csv'), 'wb' if sys.version_info[0] == 2 else 'w')
    with stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['bag_time_s', 'header_time_s', 'elapsed_s', 'x_m', 'y_m', 'fixed_z_m', 'range_fit_rms_m', 'reference_ids'])
        for i, row in enumerate(rows):
            writer.writerow([row[0], row[1], rel_t[i], xy[i, 0], xy[i, 1], height, rms[i], '|'.join(row[2])])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].plot([0, 5.33, 5.33, 0, 0], [0, 0, 5.38, 5.38, 0], 'k--', label='Nominal room')
    for key in ids:
        axes[0].plot(ANCHORS[key][0], ANCHORS[key][1], '^', color='black')
        axes[0].annotate(key, ANCHORS[key][:2], xytext=(5, 5), textcoords='offset points')
    axes[0].scatter(xy[:, 0], xy[:, 1], s=3, alpha=0.25, label='Per-frame XY')
    if reference is not None:
        axes[0].plot(reference[0], reference[1], 'rx', markersize=10, label='Manual reference')
    axes[0].set_aspect('equal', adjustable='datalim')
    axes[0].set_xlabel('x (m)')
    axes[0].set_ylabel('y (m)')
    axes[0].legend(loc='best', fontsize=8)
    axes[1].plot(rel_t, xy[:, 0], linewidth=0.7, label='x')
    axes[1].plot(rel_t, xy[:, 1], linewidth=0.7, label='y')
    axes[1].set_xlabel('Bag reception elapsed time (s)')
    axes[1].set_ylabel('Position (m)')
    axes[1].legend()
    for ax in axes:
        ax.grid(True, alpha=0.3)
    fig.suptitle(tag + ': fixed-height XY pilot; preliminary survey; no bias correction')
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(os.path.join(out, 'xy_pilot.png'), dpi=150)
    plt.close(fig)
    print('\n' + tag + ' | ' + os.path.basename(path))
    print('Solved: %d/%d (%.2f%%)' % (len(rows), total, result['solved_percent']))
    print('Mean XY: %.3f, %.3f m | XY std: %.3f, %.3f m' % tuple(result['mean_xy_m'] + result['std_xy_m']))
    print('Range-fit RMS median: %.3f m' % result['range_fit_rms_median_m'])
    if reference is not None:
        print('Difference from MANUAL reference: mean %.3f m, p95 %.3f m' %
              (result['reference_difference_mean_m'], result['reference_difference_p95_m']))
    print('Output: ' + out)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--data-dir', default='/home/wheeltec-client/uwb_field_tests/20261010')
    p.add_argument('--output-dir')
    p.add_argument('--bag', help='Optional mobile-node bag; otherwise analyze the three wall bags.')
    p.add_argument('--topic')
    p.add_argument('--tag-id')
    p.add_argument('--height-m', type=float)
    p.add_argument('--reference-xy', nargs=2, type=float)
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    out = a.output_dir or os.path.join(a.data_dir, 'fixed_height_xy_pilot')
    if a.bag:
        if a.topic is None or a.tag_id is None or a.height_m is None:
            p.error('--bag requires --topic, --tag-id and measured --height-m')
        if a.tag_id in ANCHORS:
            p.error('Mobile node must have a distinct ID; do not move a surveyed wall node.')
        analyze(a.bag, a.topic, a.tag_id, a.height_m, a.reference_xy, out)
    else:
        for name, topic, tag in RUNS:
            analyze(os.path.join(a.data_dir, name), topic, tag, ANCHORS[tag][2], ANCHORS[tag][:2], out)

if __name__ == '__main__':
    main()
