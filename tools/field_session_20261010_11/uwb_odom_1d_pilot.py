from __future__ import print_function

import csv
import math
import sys
from collections import defaultdict

import numpy as np
import rosbag
from scipy.optimize import leastsq

ANCHORS = {
    'node_8': (0.10, 2.38, 2.22),
    'node_10': (3.27, 0.10, 2.35),
    'node_3': (5.23, 2.91, 2.33),
    'node_2': (5.23, 5.12, 2.88),
}
BIAS = {
    'node_8': 0.447,
    'node_10': 0.488,
    'node_3': 0.339,
    'node_2': 0.308,
}
IDS = sorted(ANCHORS)
HEIGHT = 0.20

def solve(ranges):
    def residual(xy):
        errors = []
        for key in IDS:
            ax, ay, az = ANCHORS[key]
            geometric = math.sqrt(
                (xy[0] - ax)**2 +
                (xy[1] - ay)**2 +
                (HEIGHT - az)**2)
            errors.append(geometric - ranges[key] + BIAS[key])
        return np.asarray(errors)

    xy, cov, info, message, status = leastsq(
        residual, [2.0, 2.5], full_output=True)
    if status not in (1, 2, 3, 4):
        raise ValueError(message)
    rms = math.sqrt(float(np.mean(residual(xy)**2)))
    return xy, rms

def main(bag_path, reference_m, output_csv):
    odom, uwb, turns, gyro = [], [], [], []

    with rosbag.Bag(bag_path, 'r') as bag:
        t0 = bag.get_start_time()
        duration = bag.get_end_time() - t0

        for topic, msg, stamp in bag.read_messages():
            t = stamp.to_sec() - t0
            if topic == '/car2/odom':
                odom.append((t, float(msg.pose.pose.position.x)))
            elif topic == '/car2/uwb/ranges' and msg.tag_id == 'node_0':
                ranges = {}
                for item in msg.ranges:
                    value = float(item.range)
                    if (item.anchor_id in ANCHORS and
                            np.isfinite(value) and value > 0):
                        ranges[item.anchor_id] = value
                uwb.append((t, ranges))
            elif topic == '/car2/cmd_vel' and abs(msg.angular.z) > 0.01:
                turns.append(t)
            elif topic == '/car2/imu':
                gyro.append(abs(float(msg.angular_velocity.z)))

    # End the first run before its late turn; retain a stationary end window.
    stop = min(duration, min(turns) - 3.0) if turns else duration
    if stop < 15 or len(odom) < 10 or len(uwb) < 10:
        raise ValueError('Insufficient data or stationary windows')

    median_ranges = {}
    for label, low, high in (
            ('start', 0, 5), ('end', stop - 5, stop)):
        values = defaultdict(list)
        for t, ranges in uwb:
            if low <= t < high:
                for key, value in ranges.items():
                    values[key].append(value)
        if any(len(values[key]) < 10 for key in IDS):
            raise ValueError('Missing anchors in ' + label)
        median_ranges[label] = {
            key: float(np.median(values[key])) for key in IDS}

    start_xy, start_rms = solve(median_ranges['start'])
    end_xy, end_rms = solve(median_ranges['end'])

    first_odom = [x for t, x in odom if t <= 5]
    last_odom = [x for t, x in odom if stop - 5 <= t <= stop]
    if not first_odom or not last_odom:
        raise ValueError('Missing Odom in stationary windows')
    odom_window_dx = float(
        np.median(last_odom) - np.median(first_odom))

    previous_odom_x = first_odom[-1]
    odom_dx = 0.0
    fused_y = float(start_xy[1])
    initial_y = fused_y
    variance = 0.15**2
    last_uwb_time = 5.0
    accepted = fit_rejected = innovation_rejected = 0

    events = (
        [(t, 0, x) for t, x in odom if 5 < t <= stop] +
        [(t, 1, ranges) for t, ranges in uwb if 5 < t <= stop])
    events.sort(key=lambda event: (event[0], event[1]))

    with open(output_csv, 'wb') as handle:
        writer = csv.writer(handle)
        writer.writerow([
            'time_s', 'odom_y_m', 'uwb_y_m', 'fused_y_m',
            'fit_rms_m', 'uwb_accepted'])

        for t, kind, value in events:
            if kind == 0:
                dx = value - previous_odom_x
                previous_odom_x = value
                odom_dx += dx
                fused_y += dx
                variance += 0.002**2 + (0.03 * abs(dx))**2
                writer.writerow([
                    '%.3f' % t, '%.5f' % (initial_y + odom_dx),
                    '', '%.5f' % fused_y, '', ''])
            elif t - last_uwb_time >= 1.0 and len(value) == 4:
                last_uwb_time = t
                try:
                    xy, fit_rms = solve(value)
                except ValueError:
                    fit_rejected += 1
                    continue

                used = 0
                if fit_rms > 0.20:
                    fit_rejected += 1
                else:
                    measurement_variance = 0.15**2 + fit_rms**2
                    innovation = float(xy[1]) - fused_y
                    limit = 3 * math.sqrt(
                        variance + measurement_variance)
                    if abs(innovation) > limit:
                        innovation_rejected += 1
                    else:
                        gain = variance / (
                            variance + measurement_variance)
                        fused_y += gain * innovation
                        variance *= 1 - gain
                        accepted += 1
                        used = 1

                writer.writerow([
                    '%.3f' % t, '', '%.5f' % xy[1],
                    '%.5f' % fused_y, '%.5f' % fit_rms, used])

    uwb_delta = float(end_xy[1] - start_xy[1])
    fused_delta = fused_y - initial_y

    print('bag: %s' % bag_path)
    print('analysis end: %.2f s; turn commands: %d' %
          (stop, len(turns)))
    print('abs IMU gyro-z median/max: %.4f / %.4f rad/s' %
          (float(np.median(gyro)), max(gyro)))
    print('UWB updates: accepted=%d, fit_rejected=%d, '
          'innovation_rejected=%d' %
          (accepted, fit_rejected, innovation_rejected))
    print('corrected UWB start XY=(%.3f, %.3f), RMS=%.3f m' %
          (start_xy[0], start_xy[1], start_rms))
    print('corrected UWB end XY=(%.3f, %.3f), RMS=%.3f m' %
          (end_xy[0], end_xy[1], end_rms))
    print('reference displacement: %.3f m' % reference_m)

    for label, displacement in (
            ('Odom', odom_window_dx),
            ('corrected UWB 1D', uwb_delta),
            ('fused 1D', fused_delta)):
        print('%s: signed=%+.3f m, absolute error=%.3f m' %
              (label, displacement,
               abs(abs(displacement) - reference_m)))

    print('trajectory CSV: %s' % output_csv)

if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(
            'usage: python2 SCRIPT BAG REFERENCE_M OUTPUT_CSV')
    main(sys.argv[1], float(sys.argv[2]), sys.argv[3])
