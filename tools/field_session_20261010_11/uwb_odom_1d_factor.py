from __future__ import print_function
import csv
import math
import sys
from collections import defaultdict

import numpy as np
from scipy.optimize import least_squares, leastsq
from scipy.sparse import lil_matrix

ANCHORS = {
    'node_8': (0.10, 2.38, 2.22),
    'node_10': (3.27, 0.10, 2.35),
    'node_3': (5.23, 2.91, 2.33),
    'node_2': (5.23, 5.12, 2.88),
}
BIAS = {
    'node_8': 0.447, 'node_10': 0.488,
    'node_3': 0.339, 'node_2': 0.308,
}
IDS = sorted(ANCHORS)
X_FIXED, Z_FIXED = 2.00, 0.20
PRIOR_SIGMA, ODOM_SIGMA, RANGE_SIGMA = 0.20, 0.03, 0.20

def initial_xy(ranges):
    def errors(xy):
        return np.asarray([
            math.sqrt((xy[0]-ANCHORS[k][0])**2 +
                      (xy[1]-ANCHORS[k][1])**2 +
                      (Z_FIXED-ANCHORS[k][2])**2)
            - ranges[k] + BIAS[k] for k in IDS])
    xy, status = leastsq(errors, [2.0, 2.5])
    if status not in (1, 2, 3, 4):
        raise ValueError('initial XY solve failed')
    return xy

def optimize_incrementally(deltas, observations, prior_y):
    total = len(deltas) + 1
    latest = np.zeros(total)
    solution = np.asarray([prior_y], dtype=float)

    index = np.asarray([o[0] for o in observations], dtype=int)
    ax = np.asarray([ANCHORS[o[1]][0] for o in observations])
    ay = np.asarray([ANCHORS[o[1]][1] for o in observations])
    az = np.asarray([ANCHORS[o[1]][2] for o in observations])
    measured = np.asarray([
        o[2] - BIAS[o[1]] for o in observations])

    for n in range(1, total + 1):
        if n > 1:
            solution = np.append(
                solution, solution[-1] + deltas[n-2])

        selected = index < n
        ki = index[selected]
        a_x, a_y, a_z = ax[selected], ay[selected], az[selected]
        rr = measured[selected]
        count = len(ki)

        def residual(y):
            parts = [np.asarray([(y[0]-prior_y)/PRIOR_SIGMA])]
            if n > 1:
                parts.append(
                    (np.diff(y)-deltas[:n-1])/ODOM_SIGMA)
            if count:
                geometry = np.sqrt(
                    (X_FIXED-a_x)**2 + (y[ki]-a_y)**2 +
                    (Z_FIXED-a_z)**2)
                parts.append((geometry-rr)/RANGE_SIGMA)
            return np.concatenate(parts)

        sparsity = lil_matrix((n+count, n), dtype=int)
        sparsity[0, 0] = 1
        for j in range(1, n):
            sparsity[j, j-1] = 1
            sparsity[j, j] = 1
        for row, k in enumerate(ki):
            sparsity[n+row, int(k)] = 1

        result = least_squares(
            residual, solution,
            jac_sparsity=sparsity,
            loss='soft_l1', f_scale=1.0,
            max_nfev=80)
        if not result.success:
            raise ValueError(
                'graph failed at keyframe %d: %s' %
                (n, result.message))
        solution = result.x
        latest[n-1] = solution[-1]

    return solution, latest

def run_bag(path, reference, output_csv):
    import rosbag

    odom, uwb, turns = [], [], []
    with rosbag.Bag(path, 'r') as bag:
        start = bag.get_start_time()
        duration = bag.get_end_time() - start
        for topic, msg, stamp in bag.read_messages():
            t = stamp.to_sec() - start
            if topic == '/car2/odom':
                odom.append(
                    (t, float(msg.pose.pose.position.x)))
            elif (topic == '/car2/uwb/ranges' and
                  msg.tag_id == 'node_0'):
                ranges = {}
                for r in msg.ranges:
                    value = float(r.range)
                    if (r.anchor_id in ANCHORS and
                            np.isfinite(value) and value > 0):
                        ranges[r.anchor_id] = value
                uwb.append((t, ranges))
            elif (topic == '/car2/cmd_vel' and
                  abs(msg.angular.z) > 0.01):
                turns.append(t)

    # Exclude the late turn in forward experiment 1.
    stop = min(duration, min(turns)-3.0) if turns else duration
    if stop < 15 or len(odom) < 10 or len(uwb) < 10:
        raise ValueError('insufficient data')

    start_values = defaultdict(list)
    for t, ranges in uwb:
        if 0 <= t < 5:
            for key, value in ranges.items():
                start_values[key].append(value)
    if any(len(start_values[k]) < 10 for k in IDS):
        raise ValueError('missing initial anchor observations')
    start_ranges = {
        k: float(np.median(start_values[k])) for k in IDS}
    prior_y = float(initial_xy(start_ranges)[1])

    times = np.arange(5.0, stop-1.999, 1.0)
    if len(times) < 10:
        raise ValueError('too few keyframes')
    odom_t = np.asarray([t for t, x in odom])
    odom_x = np.asarray([x for t, x in odom])
    odom_at_times = np.interp(times, odom_t, odom_x)
    deltas = np.diff(odom_at_times)

    observations = []
    uwb_y = []
    for index, key_time in enumerate(times):
        values = defaultdict(list)
        for t, ranges in uwb:
            if abs(t-key_time) <= 0.4:
                for key, value in ranges.items():
                    values[key].append(value)

        medians = {}
        for key in IDS:
            if len(values[key]) >= 5:
                median = float(np.median(values[key]))
                medians[key] = median
                observations.append((index, key, median))
        uwb_y.append(
            float(initial_xy(medians)[1])
            if len(medians) == 4 else float('nan'))

    graph, latest = optimize_incrementally(
        deltas, observations, prior_y)

    with open(output_csv, 'wb') as handle:
        writer = csv.writer(handle)
        writer.writerow([
            'time_s', 'odom_y_m', 'corrected_uwb_y_m',
            'graph_smoothed_y_m', 'incremental_latest_y_m'])
        for k, t in enumerate(times):
            writer.writerow([
                '%.3f' % t,
                '%.5f' % (
                    prior_y+odom_at_times[k]-odom_at_times[0]),
                '%.5f' % uwb_y[k],
                '%.5f' % graph[k],
                '%.5f' % latest[k]])

    print('bag: %s' % path)
    print('reference: %.3f m; keyframes: %d; '
          'range factors: %d; last time: %.1f s' %
          (reference, len(times), len(observations), times[-1]))
    for label, displacement in (
            ('Odom', odom_at_times[-1]-odom_at_times[0]),
            ('corrected UWB 1D', uwb_y[-1]-uwb_y[0]),
            ('factor graph 1D', graph[-1]-graph[0])):
        print('%s: signed=%+.3f m, absolute error=%.3f m' %
              (label, displacement,
               abs(abs(displacement)-reference)))
    print('model: fixed x=2.00, z=0.20 m; '
          'prior/Odom/UWB sigma=0.20/0.03/0.20 m')
    print('method: append factors, re-optimize full graph; '
          'not iSAM2')
    print('CSV: %s' % output_csv)

def self_test():
    truth = np.linspace(2.0, 3.0, 12)
    observations = []
    for index, y in enumerate(truth):
        for key in IDS:
            ax, ay, az = ANCHORS[key]
            value = math.sqrt(
                (X_FIXED-ax)**2 + (y-ay)**2 +
                (Z_FIXED-az)**2) + BIAS[key]
            observations.append((index, key, value))
    graph, latest = optimize_incrementally(
        np.diff(truth), observations, 2.0)
    error = abs(graph[-1]-graph[0]-1.0)
    if error > 0.01:
        raise ValueError('self-test failed: %.4f m' % error)
    print('PASS synthetic 1D graph; error=%.6f m' % error)

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--self-test':
        self_test()
    elif len(sys.argv) == 4:
        run_bag(sys.argv[1], float(sys.argv[2]), sys.argv[3])
    else:
        raise SystemExit(
            'usage: python2 SCRIPT --self-test | BAG REF_M CSV')
