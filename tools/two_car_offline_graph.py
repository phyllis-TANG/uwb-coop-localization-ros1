#!/usr/bin/env python3
"""Reproducible, offline two-car batch graph for the 2026-10-18 archive.

The two solutions use identical priors, odometry, and wall ranges. The joint
solution adds one (not two) median inter-car range per keyframe. No endpoint or
tape measurement enters optimization. No ROS node or hardware is used.
"""
import argparse
import bisect
import csv
import hashlib
import io
import json
import math
import tarfile
from pathlib import Path

import numpy as np
from rosbags.highlevel import AnyReader
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix


BAGS = {
    'L': 'TWO_CAR_C1_static_C2_auto_L_20261018_015334.bag',
    'straight': 'TWO_CAR_C2_static_C1_auto_straight_aligned_20261018_033248.bag',
    'static_020151': 'TWO_CAR_C1_1p5_4_C2_end_2p95_3p04_static_20261018_020151.bag',
}
ANCHORS = Path(__file__).resolve().parents[1] / 'docs/field_tests/20261017/session_config.json'
HEIGHT = {'car1': 0.17, 'car2': 0.20}
LEVER = {'car1': np.array([0.08, -0.06]), 'car2': np.array([0.12, -0.08])}
TAG = {'car1': 'node_1', 'car2': 'node_0'}
PEER = {'car1': 'node_0', 'car2': 'node_1'}
START = {'L': {'car1': [1.50, 4.00], 'car2': [2.00, 2.00]},
         'straight': {'car1': [1.50, 4.00], 'car2': [2.95, 3.04]}}
END = {'L': {'car1': [1.50, 4.00], 'car2': [2.95, 3.04]},
       'straight': {'car1': [1.45, 2.98], 'car2': [2.95, 3.04]}}
TAPE = {'L': 1.743, 'straight': 1.54}
# These are placement hypotheses, not surveyed orientations. Endpoint locations
# are deliberately absent from the initial-heading calculation.
HEADING_DEG = {'L': {'car1': 0., 'car2': 90.},
               'straight': {'car1': -90., 'car2': 0.}}
PARAM = {'step_s': 1., 'bin_half_width_s': 0.4,
         'odom_translation_sigma_m': 0.03, 'odom_yaw_sigma_deg': 2.,
         'prior_position_sigma_m': 0.2, 'prior_heading_sigma_deg': 5.,
         'wall_sigma_m': 0.2, 'peer_sigma_m': 0.2}


class MemoryBag:
    """Read a bag directly from the tar member without extracting it."""
    def __init__(self, name, data):
        self.name, self.data, self.suffix = name, data, '.bag'

    def exists(self):
        return True

    def open(self, mode='rb'):
        if mode != 'rb':
            raise ValueError('read-only bag')
        return io.BytesIO(self.data)

    def __str__(self):
        return self.name


def yaw(q):
    return math.atan2(2*(q.w*q.z + q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))


def read_run(archive, name):
    with tarfile.open(archive, 'r:gz') as tar:
        member = '20261018/' + BAGS[name]
        raw = tar.extractfile(member).read()
        checksum = tar.extractfile('20261018/BAG_SHA256SUMS.txt').read().decode()
        expected = [line.split()[0] for line in checksum.splitlines()
                    if BAGS[name] in line]
        actual = hashlib.sha256(raw).hexdigest()
        if len(expected) != 1 or actual != expected[0]:
            raise ValueError('bag SHA-256 does not match archive manifest: ' + member)
    odom = {'car1': [], 'car2': []}
    uwb = {'car1': [], 'car2': []}
    peer_stamps = {'car1': [], 'car2': []}
    with AnyReader([MemoryBag(BAGS[name], raw)]) as reader:
        first = reader.start_time * 1e-9
        duration = reader.duration * 1e-9
        for connection, ns, buffer in reader.messages():
            topic = connection.topic
            if topic not in ('/car1/odom', '/car2/odom',
                             '/car1/uwb/ranges', '/car2/uwb/ranges'):
                continue
            car = topic.split('/')[1]
            msg = reader.deserialize(buffer, connection.msgtype)
            t = ns*1e-9-first  # common bag receipt clock, NOT unsynchronised headers
            if topic.endswith('/odom'):
                p = msg.pose.pose.position
                odom[car].append((t, p.x, p.y, yaw(msg.pose.pose.orientation)))
            else:
                if msg.tag_id != TAG[car]:
                    raise ValueError('unexpected UWB tag in ' + topic)
                grouped = {}
                for item in msg.ranges:
                    grouped.setdefault(item.anchor_id, []).append(float(item.range))
                valid = {k: v[0] for k, v in grouped.items()
                         if len(v) == 1 and np.isfinite(v[0]) and v[0] > 0}
                uwb[car].append((t, valid))
                if PEER[car] in valid:
                    stamp = msg.header.stamp
                    header = stamp.sec + stamp.nanosec*1e-9-first
                    peer_stamps[car].append((t, header))
    for car in odom:
        if len(odom[car]) < 10 or len(uwb[car]) < 10:
            raise ValueError('missing odom or UWB: ' + car)
    # Receipt-time pairing is diagnostic only: matched messages need not have
    # been acquired simultaneously at their physically different sensors.
    candidates = []
    a, b = peer_stamps['car1'], peer_stamps['car2']
    b_times = [x[0] for x in b]
    for i, (t, _) in enumerate(a):
        k = bisect.bisect_left(b_times, t)
        for j in range(max(0, k-2), min(len(b), k+2)):
            delta = abs(b[j][0]-t)
            if delta <= .03:
                candidates.append((delta, i, j))
    matched = []
    used_a, used_b = set(), set()
    for delta, i, j in sorted(candidates):
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            matched.append((delta, b[j][1]-a[i][1]))
    timing = {'paired_peer_frames_within_30ms': len(matched),
              'median_abs_receipt_gap_ms': float(np.median([x[0] for x in matched]))*1000,
              'median_header_car2_minus_car1_ms': float(np.median([x[1] for x in matched]))*1000}
    coverage = {}
    for car in odom:
        rows = uwb[car]
        coverage[car] = {'uwb_frames': len(rows),
                         'wall_valid_frames': {key: sum(key in x[1] for x in rows)
                                               for key in ('node_2', 'node_3', 'node_8', 'node_10')},
                         'peer_valid_frames': sum(PEER[car] in x[1] for x in rows)}
    return {'name': name, 'sha256': actual, 'duration_s': duration,
            'odom': odom, 'uwb': uwb, 'timing': timing, 'coverage': coverage}


def rot(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.stack((np.stack((c, -s), axis=-1),
                     np.stack((s, c), axis=-1)), axis=-2)


def wrap(a):
    return np.arctan2(np.sin(a), np.cos(a))


def odom_between(local):
    """Body-frame SE(2) increments; invariant to an odom-frame rigid transform."""
    dp = np.diff(local[:, :2], axis=0)
    th = local[:-1, 2]
    body = np.column_stack((np.cos(th)*dp[:, 0]+np.sin(th)*dp[:, 1],
                            -np.sin(th)*dp[:, 0]+np.cos(th)*dp[:, 1]))
    return body, wrap(np.diff(local[:, 2]))


def antenna(states, lever):
    theta = states[:, 2]
    c, s = np.cos(theta), np.sin(theta)
    return states[:, :2] + np.column_stack((c*lever[0]-s*lever[1],
                                            s*lever[0]+c*lever[1]))


def build_inputs(run, anchors, scenario):
    # All keyframes are in the common bag-receipt clock. The +/-0.4 s bins
    # mirror the existing single-car pilot and are held fixed across models.
    params = dict(PARAM)
    for key in ('odom_translation_sigma_m', 'prior_position_sigma_m',
                'wall_sigma_m', 'peer_sigma_m'):
        if key in scenario:
            params[key] = scenario[key]
    n = int(math.floor(run['duration_s']))-1
    times = np.arange(1., n+1., params['step_s'])
    cars = {}
    for car in ('car1', 'car2'):
        rows = np.asarray(run['odom'][car], dtype=float)
        if not np.all(np.diff(rows[:, 0]) > 0):
            raise ValueError('non-monotonic odom receive time')
        rows[:, 3] = np.unwrap(rows[:, 3])
        local = np.column_stack([np.interp(times, rows[:, 0], rows[:, i])
                                 for i in (1, 2, 3)])
        heading = math.radians(HEADING_DEG[run['name']][car] +
                               (scenario['heading_delta_deg'] if car == scenario['moving']
                                else scenario['static_heading_delta_deg']))
        lever = LEVER[car].copy() * scenario['lever_scale']
        angle = heading-local[0, 2]
        initial = np.column_stack((
            (local[:, :2]-local[0, :2])@rot(angle).T, local[:, 2]+angle))
        initial[:, :2] += np.asarray(START[run['name']][car])-antenna(initial[:1], lever)[0]
        observations = []
        raw_counts = {key: 0 for key in anchors}
        for center in times:
            vals = {key: [] for key in anchors}
            for t, ranges in run['uwb'][car]:
                if abs(t-center) <= params['bin_half_width_s']:
                    for key in anchors:
                        if key in ranges:
                            vals[key].append(ranges[key])
            observations.append({key: float(np.median(v)) for key, v in vals.items()
                                 if len(v) >= 5})
            for key, v in vals.items():
                raw_counts[key] += len(v)
        cars[car] = {'local': local, 'heading': heading, 'lever': lever,
                     'initial': initial, 'walls': observations,
                     'wall_raw_counts': raw_counts}
    peers = []
    for center in times:
        directions = []
        counts = []
        for car in ('car1', 'car2'):
            shift = scenario['peer_car2_shift_s'] if car == 'car2' else 0.
            vals = [r[PEER[car]] for t, r in run['uwb'][car]
                    if PEER[car] in r and abs(t+shift-center) <= params['bin_half_width_s']]
            counts.append(len(vals))
            directions.append(float(np.median(vals)) if len(vals) >= 5 else None)
        corrected = [value-bias for value, bias in zip(directions, scenario['peer_bias_m'])
                     if value is not None]
        peers.append({'range_m': float(np.mean(corrected)) if corrected else None,
                      'directions_m': directions, 'direction_counts': counts})
    return {'times': times, 'cars': cars, 'peers': peers, 'parameters': params,
            'anchors': anchors, 'scenario': scenario}


def graph(inputs, joint):
    n = len(inputs['times'])
    cars = inputs['cars']
    refs = inputs['anchors']
    scenario = inputs['scenario']
    params = inputs['parameters']
    wall = [(ci, i, key, value-scenario['wall_bias_car2_m'].get(key, 0.)*(ci == 1))
            for ci, car in enumerate(('car1', 'car2'))
            for i, row in enumerate(cars[car]['walls'])
            for key, value in sorted(row.items())]
    peer = [(i, entry['range_m']) for i, entry in enumerate(inputs['peers'])
            if entry['range_m'] is not None] if joint else []
    wall_ci = np.array([x[0] for x in wall], dtype=int)
    wall_i = np.array([x[1] for x in wall], dtype=int)
    wall_xyz = np.array([refs[x[2]] for x in wall])
    wall_z = np.array([HEIGHT['car1'] if x[0] == 0 else HEIGHT['car2'] for x in wall])
    wall_meas = np.array([x[3] for x in wall])
    peer_i = np.array([x[0] for x in peer], dtype=int)
    peer_meas = np.array([x[1] for x in peer])
    local = [cars[c]['local'] for c in ('car1', 'car2')]
    body_delta = []
    yaw_delta = []
    for x in local:
        body, turn = odom_between(x)
        body_delta.append(body)
        yaw_delta.append(turn)
    dt = np.diff(inputs['times'])
    sx = params['odom_translation_sigma_m']*np.sqrt(dt)
    sa = np.radians(params['odom_yaw_sigma_deg'])*np.sqrt(dt)
    initial = np.stack([cars[c]['initial'] for c in ('car1', 'car2')])

    def robust(error):
        return error*np.sqrt(2/(np.sqrt(1+error*error)+1))

    def residual(flat):
        state = flat.reshape(2, n, 3)
        ant = np.stack([antenna(state[j], cars[c]['lever'])
                        for j, c in enumerate(('car1', 'car2'))])
        prior = []
        between = []
        for j, c in enumerate(('car1', 'car2')):
            prior.extend((ant[j, 0]-START[inputs['scenario']['run']][c])/
                         params['prior_position_sigma_m'])
            prior.append(float(wrap(state[j, 0, 2]-cars[c]['heading'])/
                               np.radians(params['prior_heading_sigma_deg'])))
            d = np.diff(state[j, :, :2], axis=0)
            th = state[j, :-1, 2]
            body = np.column_stack((np.cos(th)*d[:, 0]+np.sin(th)*d[:, 1],
                                    -np.sin(th)*d[:, 0]+np.cos(th)*d[:, 1]))
            between.append(np.column_stack(((body-body_delta[j])/sx[:, None],
                                             wrap(np.diff(state[j, :, 2])-yaw_delta[j])/sa)).ravel())
        wxy = ant[wall_ci, wall_i]
        wr = np.sqrt(np.sum((wxy-wall_xyz[:, :2])**2, axis=1)+
                     (wall_z-wall_xyz[:, 2])**2)
        result = [np.asarray(prior), *between,
                  robust((wr-wall_meas)/params['wall_sigma_m'])]
        if joint:
            dr = ant[0, peer_i]-ant[1, peer_i]
            pr = np.sqrt(np.sum(dr*dr, axis=1)+(HEIGHT['car1']-HEIGHT['car2'])**2)
            result.append(robust((pr-peer_meas)/params['peer_sigma_m']))
        return np.concatenate(result)

    rows = 6+6*(n-1)+len(wall)+len(peer)
    sparse = lil_matrix((rows, 6*n), dtype=np.int8)
    sparse[:3, :3] = 1
    sparse[3:6, 3*n:3*n+3] = 1
    row = 6
    for j in range(2):
        for i in range(n-1):
            sparse[row:row+3, 3*(j*n+i):3*(j*n+i+2)] = 1
            row += 3
    for ci, i, _, _ in wall:
        sparse[row, 3*(ci*n+i):3*(ci*n+i)+3] = 1
        row += 1
    for i, _ in peer:
        sparse[row, 3*i:3*i+3] = 1
        sparse[row, 3*(n+i):3*(n+i)+3] = 1
        row += 1
    assert row == rows
    fit = least_squares(residual, initial.ravel(), jac_sparsity=sparse,
                        max_nfev=100, ftol=1e-6, xtol=1e-6, gtol=1e-6)
    if not fit.success:
        raise RuntimeError('graph optimization failed: ' + fit.message)
    state = fit.x.reshape(2, n, 3)
    ant = np.stack([antenna(state[j], cars[c]['lever'])
                    for j, c in enumerate(('car1', 'car2'))])
    odom_diagnostics = {}
    for ci, car in enumerate(('car1', 'car2')):
        xy = state[ci, :, :2]
        d = np.diff(xy, axis=0)
        th = state[ci, :-1, 2]
        estimated_body_delta = np.column_stack((
            np.cos(th)*d[:, 0]+np.sin(th)*d[:, 1],
            -np.sin(th)*d[:, 0]+np.cos(th)*d[:, 1]))
        translation_error = np.linalg.norm(estimated_body_delta-body_delta[ci], axis=1)
        yaw_error = wrap(np.diff(state[ci, :, 2])-yaw_delta[ci])
        odom_diagnostics[car] = {
            'interpolated_odom_path_m': float(np.sum(np.linalg.norm(
                np.diff(local[ci][:, :2], axis=0), axis=1))),
            'estimated_base_path_m': float(np.sum(np.linalg.norm(d, axis=1))),
            'estimated_antenna_path_m': float(np.sum(np.linalg.norm(
                np.diff(ant[ci], axis=0), axis=1))),
            'odom_between_translation_error_median_m': float(np.median(translation_error)),
            'odom_between_translation_error_rms_m': float(np.sqrt(np.mean(translation_error**2))),
            'odom_between_translation_error_max_m': float(np.max(translation_error)),
            'odom_between_translation_weighted_squared_sum': float(np.sum(
                (translation_error/sx)**2)),
            'odom_between_yaw_error_rms_deg': float(np.degrees(np.sqrt(np.mean(yaw_error**2)))),
            'start_antenna_prior_displacement_m': float(np.linalg.norm(
                ant[ci, 0]-START[inputs['scenario']['run']][car])),
            'start_heading_prior_error_deg': float(np.degrees(wrap(
                state[ci, 0, 2]-cars[car]['heading']))),
        }
    wall_residual = {'car1': [], 'car2': []}
    for ci, i, key, measured in wall:
        point = np.r_[ant[ci, i], HEIGHT['car1'] if ci == 0 else HEIGHT['car2']]
        wall_residual[('car1', 'car2')[ci]].append(float(np.linalg.norm(point-refs[key])-measured))
    peer_residual = []
    for i, measurement in [(i, entry['range_m']) for i, entry in enumerate(inputs['peers'])
                           if entry['range_m'] is not None]:
        prediction = np.linalg.norm(np.r_[ant[0, i]-ant[1, i], HEIGHT['car1']-HEIGHT['car2']])
        peer_residual.append(float(prediction-measurement))
    return {'states': state, 'antenna_xy': ant, 'nfev': fit.nfev,
            'cost': fit.cost, 'wall_residual_m': wall_residual,
            'peer_residual_m': peer_residual,
            'odom_diagnostics': odom_diagnostics,
            'wall_factor_count': len(wall), 'peer_factor_count': len(peer)}


def metrics(run, inputs, fit):
    ant = fit['antenna_xy']
    n = len(inputs['times'])
    end = np.stack([np.asarray(END[run['name']][c]) for c in ('car1', 'car2')])
    # Last five available keyframes are stationary in these two bags.
    estimate = np.median(ant[:, -5:, :], axis=1)
    start_estimate = np.median(ant[:, :4, :], axis=1)
    distance = float(np.linalg.norm(np.r_[estimate[0]-estimate[1],
                                           HEIGHT['car1']-HEIGHT['car2']]))
    trajectory = {}
    for ci, car in enumerate(('car1', 'car2')):
        xy = ant[ci]
        trajectory[car] = {'path_m': float(np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1))),
                           'net_displacement_m': float(np.linalg.norm(xy[-1]-xy[0]))}
    def summary(v):
        v = np.asarray(v)
        return {'count': len(v), 'median_m': float(np.median(v)),
                'median_abs_m': float(np.median(np.abs(v))),
                'rms_m': float(np.sqrt(np.mean(v*v)))} if len(v) else None
    return {'keyframes': n, 'first_last_keyframe_s': [float(inputs['times'][0]),
                                                     float(inputs['times'][-1])],
            'end_antenna_xy_m': {'car1': estimate[0].tolist(), 'car2': estimate[1].tolist()},
            'start_antenna_xy_m': {'car1': start_estimate[0].tolist(),
                                   'car2': start_estimate[1].tolist()},
            'manual_end_xy_error_m': {'car1': float(np.linalg.norm(estimate[0]-end[0])),
                                      'car2': float(np.linalg.norm(estimate[1]-end[1]))},
            'end_intercar_distance_m': distance,
            'end_distance_minus_tape_m': distance-TAPE[run['name']],
            'antenna_trajectory': trajectory,
            'odom_diagnostics': fit['odom_diagnostics'],
            'wall_residual': {c: summary(v) for c, v in fit['wall_residual_m'].items()},
            'peer_residual': summary(fit['peer_residual_m']),
            'wall_factors': fit['wall_factor_count'],
            'peer_factors': fit['peer_factor_count'],
            'peer_bin_coverage': fit['peer_factor_count']/n if fit['peer_factor_count'] else 0.,
            'parameters': inputs['parameters'],
            'optimizer_nfev': fit['nfev'], 'optimizer_cost': float(fit['cost'])}


def scenarios(run, car2_wall_bias=None):
    moving = 'car2' if run == 'L' else 'car1'
    base = {'run': run, 'moving': moving, 'heading_delta_deg': 0.,
            'static_heading_delta_deg': 0.,
            'lever_scale': 1., 'peer_car2_shift_s': 0.,
            'peer_bias_m': [0., 0.], 'wall_bias_car2_m': {}}
    variants = {'primary': {}, 'heading_plus_15deg': {'heading_delta_deg': 15.},
                'heading_minus_15deg': {'heading_delta_deg': -15.},
                'static_heading_plus_90deg': {'static_heading_delta_deg': 90.},
                'static_heading_minus_90deg': {'static_heading_delta_deg': -90.},
                'zero_lever_arm': {'lever_scale': 0.},
                'stronger_odom_0p01m': {'odom_translation_sigma_m': 0.01},
                'stronger_start_prior_0p05m': {'prior_position_sigma_m': 0.05},
                'weaker_wall_0p4m': {'wall_sigma_m': 0.4},
                'weaker_peer_0p4m': {'peer_sigma_m': 0.4},
                'peer_car2_plus_0p1s': {'peer_car2_shift_s': 0.1},
                'peer_car2_minus_0p1s': {'peer_car2_shift_s': -0.1},
                'static_A_peer_bias': {'peer_bias_m': [0.007, 0.057]},
                'car2_P1_wall_bias_only': {'wall_bias_car2_m': car2_wall_bias or {}}}
    return {key: dict(base, **value) for key, value in variants.items()}


def static_crosscheck(run):
    """Report the independent static bag, without using it in the graph."""
    result = {'bag_sha256': run['sha256'], 'duration_s': run['duration_s'],
              'named_antenna_xy_m': {'car1': [1.50, 4.00], 'car2': [2.95, 3.04]},
              'tape_reference_from_L_note_m': TAPE['L'], 'cars': {}}
    for car in ('car1', 'car2'):
        odom = np.asarray(run['odom'][car])
        ranges = [row[1][PEER[car]] for row in run['uwb'][car]
                  if PEER[car] in row[1]]
        result['cars'][car] = {
            'odom_path_m': float(np.sum(np.linalg.norm(np.diff(odom[:, 1:3], axis=0), axis=1))),
            'peer_valid_frames': len(ranges),
            'uwb_frames': len(run['uwb'][car]),
            'peer_median_m': float(np.median(ranges)),
            'peer_median_minus_L_tape_m': float(np.median(ranges)-TAPE['L']),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--primary-only', action='store_true')
    args = parser.parse_args()
    config = json.loads(ANCHORS.read_text())
    anchors = config['anchors_xyz_m']
    report = {'archive_sha256': hashlib.sha256(args.archive.read_bytes()).hexdigest(),
              'anchors_source': str(ANCHORS), 'anchors_xyz_m': anchors,
              'heights_m': HEIGHT, 'lever_xy_m': {k: v.tolist() for k, v in LEVER.items()},
              'parameters': PARAM, 'runs': {}}
    report['static_crosscheck_020151'] = static_crosscheck(
        read_run(args.archive, 'static_020151'))
    trajectories = []
    for name in ('L', 'straight'):
        run = read_run(args.archive, name)
        variants = scenarios(name, config['calibration']['frozen_bias_m'])
        if args.primary_only:
            variants = {'primary': variants['primary']}
        record = {'bag_sha256': run['sha256'], 'duration_s': run['duration_s'],
                  'timing': run['timing'], 'raw_coverage': run['coverage'],
                  'manual_start_xy_m': START[name], 'manual_end_xy_m': END[name],
                  'direct_tape_endpoint_distance_m': TAPE[name],
                  'initial_heading_hypotheses_deg': HEADING_DEG[name], 'scenarios': {}}
        for label, scenario in variants.items():
            inputs = build_inputs(run, anchors, scenario)
            solo = graph(inputs, joint=False)
            joint = graph(inputs, joint=True)
            record['scenarios'][label] = {'inputs': scenario,
                                          'independent': metrics(run, inputs, solo),
                                          'joint': metrics(run, inputs, joint)}
            if label == 'primary':
                for method, fit in [('independent', solo), ('joint', joint)]:
                    for ci, car in enumerate(('car1', 'car2')):
                        for i, t in enumerate(inputs['times']):
                            pose = fit['states'][ci, i]
                            xy = fit['antenna_xy'][ci, i]
                            trajectories.append((name, method, car, float(t),
                                                 float(pose[0]), float(pose[1]),
                                                 float(pose[2]), float(xy[0]), float(xy[1])))
            print(name, label, 'independent/joint end distance',
                  round(record['scenarios'][label]['independent']['end_intercar_distance_m'], 4),
                  round(record['scenarios'][label]['joint']['end_intercar_distance_m'], 4),
                  flush=True)
        report['runs'][name] = record
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'two_car_graph_summary.json').write_text(json.dumps(report, indent=2)+'\n')
    with (args.output/'two_car_graph_trajectories.csv').open('w') as stream:
        stream.write('run,method,car,elapsed_s,base_x_m,base_y_m,base_yaw_rad,antenna_x_m,antenna_y_m\n')
        for row in trajectories:
            stream.write(','.join(map(str, row))+'\n')
    with (args.output/'two_car_graph_sensitivity.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(('run', 'scenario', 'method', 'car1_end_error_m',
                         'car2_end_error_m', 'stationary_car', 'stationary_path_m',
                         'stationary_net_drift_m', 'end_intercar_distance_m',
                         'end_distance_minus_tape_m', 'car1_wall_median_abs_residual_m',
                         'car2_wall_median_abs_residual_m', 'peer_median_abs_residual_m',
                         'car1_start_prior_displacement_m',
                         'car2_start_prior_displacement_m'))
        for name, run in report['runs'].items():
            static = 'car1' if name == 'L' else 'car2'
            for scenario, result in run['scenarios'].items():
                for method in ('independent', 'joint'):
                    x = result[method]
                    writer.writerow((name, scenario, method,
                                     x['manual_end_xy_error_m']['car1'],
                                     x['manual_end_xy_error_m']['car2'], static,
                                     x['antenna_trajectory'][static]['path_m'],
                                     x['antenna_trajectory'][static]['net_displacement_m'],
                                     x['end_intercar_distance_m'],
                                     x['end_distance_minus_tape_m'],
                                     x['wall_residual']['car1']['median_abs_m'],
                                     x['wall_residual']['car2']['median_abs_m'],
                                     x['peer_residual']['median_abs_m'],
                                     x['odom_diagnostics']['car1']['start_antenna_prior_displacement_m'],
                                     x['odom_diagnostics']['car2']['start_antenna_prior_displacement_m']))


if __name__ == '__main__':
    main()
