#!/usr/bin/env python3
"""Matched offline two-car factors using the merged single-car residual model.

No endpoints, tape distances or stationary-pose constraints enter this module's
optimizer. It is a full-bag batch comparison, not a streaming estimator.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import math
from pathlib import Path
import time

import numpy as np
from scipy.optimize import least_squares

from single_car_fixed_lag import Objective, initial_prior
from single_car_sequential_replay import rotation

CARS = ('car1', 'car2')
TAGS = dict(car1='node_1', car2='node_0')
PEERS = dict(car1='node_0', car2='node_1')


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def unique_positive_ranges(entries):
    grouped = collections.defaultdict(list)
    for key, value in entries:
        grouped[key].append(float(value))
    valid = {key: values[0] for key, values in grouped.items()
             if len(values) == 1 and np.isfinite(values[0]) and values[0] > 0}
    return valid, sum(len(values) != 1 for values in grouped.values())


def read_bag(path, expected_sha256):
    """Use embedded ROS definitions, common receipt clock, and unmodified data."""
    from rosbags.highlevel import AnyReader
    actual = sha256(path)
    if actual != expected_sha256:
        raise ValueError('Dataset SHA256 mismatch: '+str(path))
    odom, uwb = {c: [] for c in CARS}, {c: [] for c in CARS}
    timing, frames = collections.defaultdict(list), collections.defaultdict(set)
    counts, duplicates = collections.Counter(), collections.Counter()
    with AnyReader([Path(path)]) as reader:
        origin = reader.start_time
        duration = reader.duration*1e-9
        for connection, ns, raw in reader.messages():
            topic = connection.topic
            counts[topic] += 1
            parts = topic.split('/')
            if len(parts) < 3 or parts[1] not in CARS or topic not in {
                    '/'+c+'/'+suffix for c in CARS for suffix in ['odom', 'uwb/ranges']}:
                continue
            car = parts[1]
            msg = reader.deserialize(raw, connection.msgtype)
            # Preserve the archived frontend's arithmetic for exact bin reproduction.
            received = ns*1e-9-origin*1e-9
            header = msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9-origin*1e-9
            timing[topic].append((received, header))
            frames[topic].add(msg.header.frame_id)
            if topic.endswith('/odom'):
                point, q = msg.pose.pose.position, msg.pose.pose.orientation
                quaternion = np.asarray([q.x, q.y, q.z, q.w], dtype=float)
                norm = np.linalg.norm(quaternion)
                if not np.isfinite(norm) or not .5 <= norm <= 1.5:
                    raise ValueError('Invalid quaternion in '+topic)
                x, y, z, w = quaternion/norm
                yaw = math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
                if not np.isfinite([point.x, point.y, yaw]).all():
                    raise ValueError('Nonfinite Odom pose')
                odom[car].append((received, point.x, point.y, yaw))
                frames[topic+' child'].add(msg.child_frame_id)
            else:
                if msg.tag_id != TAGS[car]:
                    raise ValueError('Unexpected tag in '+topic)
                values, duplicate = unique_positive_ranges((x.anchor_id, x.range) for x in msg.ranges)
                duplicates[car] += duplicate
                uwb[car].append((received, values))
    for car in CARS:
        if len(odom[car]) < 2 or not uwb[car]:
            raise ValueError('Missing Odom/UWB: '+car)
        if np.any(np.diff(np.asarray(odom[car])[:, 0]) <= 0):
            raise ValueError('Nonincreasing Odom receipt times: '+car)
    timing_report = {}
    for topic, rows in timing.items():
        values = np.asarray(rows)
        gap = values[:, 0]-values[:, 1]
        timing_report[topic] = dict(
            header_nonincreasing_steps=int(np.sum(np.diff(values[:, 1]) <= 0)),
            receipt_minus_header_ms={key: float(value) for key, value in zip(
                ['min', 'median', 'p95', 'max'], 1000*np.percentile(gap, [0, 50, 95, 100]))})
    return dict(sha256=actual, duration_s=duration, odom=odom, uwb=uwb,
                diagnostics=dict(origin_receipt_ns=origin, topic_counts=dict(counts),
                    duplicate_uwb_id_groups=dict(duplicates), frames={k: sorted(v) for k,v in frames.items()},
                    timing=timing_report, imu_factors=0,
                    receipt_clock_note='Inherited common bag receipt-time association; clock differences are not network latency or proof of synchronized acquisition.'))


def fit_static_wall_bias(run, car, reference_xyz, anchors):
    """One independent static calibration; no evaluation endpoints are accepted."""
    output = {}
    for key, xyz in sorted(anchors.items()):
        values = np.asarray([row[key] for _, row in run['uwb'][car] if key in row])
        if len(values) < 5:
            raise ValueError('Insufficient calibration samples: '+car+'/'+key)
        geometry = float(np.linalg.norm(np.asarray(reference_xyz)-xyz))
        median = float(np.median(values))
        output[key] = dict(samples=len(values), raw_median_m=median,
            geometry_m=geometry, bias_m=median-geometry,
            raw_iqr_m=float(np.percentile(values, 75)-np.percentile(values, 25)))
    return output


def build_inputs(run, model_case, protocol, configuration, calibrated_biases):
    """Create immutable paired inputs; model_case deliberately excludes endpoints."""
    step = float(protocol['graph_parameters']['keyframe_step_s'])
    times = np.arange(1., int(math.floor(run['duration_s'])), step)
    if len(times) < 3:
        raise ValueError('Recording too short for three keyframes')
    half = protocol['time_association']['range_bin_half_width_s']
    minimum = protocol['time_association']['minimum_samples_per_link']
    cars = {}
    for car in CARS:
        rows = np.asarray(run['odom'][car], dtype=float).copy()
        if rows[0, 0] > times[0] or rows[-1, 0] < times[-1]:
            raise ValueError('Frozen keyframes lack Odom brackets: '+car)
        rows[:, 3] = np.unwrap(rows[:, 3])
        local = np.column_stack([np.interp(times, rows[:, 0], rows[:, j]) for j in [1, 2, 3]])
        bias = {key: 0. for key in protocol['anchors_xyz_m']}
        if configuration['correction'] == 'per_car' or (
                configuration['correction'] == 'car2_only' and car == 'car2'):
            bias.update(calibrated_biases[car])
        model = dict(anchors_xyz_m=copy.deepcopy(protocol['anchors_xyz_m']), range_bias_m=bias,
            start_antenna_xyz_m=list(model_case['start_antenna_xyz_m'][car]),
            initial_heading_deg=model_case['initial_heading_deg'][car],
            base_to_antenna_body_xy_m=list(protocol['mounts'][car]['lever_xy_m']),
            antenna_height_m=protocol['mounts'][car]['height_m'],
            graph_parameters=copy.deepcopy(protocol['graph_parameters']))
        prior = initial_prior(model)
        angle = prior.point[2]-local[0, 2]
        initial = np.column_stack(((local[:, :2]-local[0, :2])@rotation(angle).T+prior.point[:2],
                                   local[:, 2]+angle))
        observations, support, rejected = [], [], 0
        for center in times:
            row, count = {}, {}
            for key in sorted(model['anchors_xyz_m']):
                values = [values[key] for t,values in run['uwb'][car]
                          if abs(t-center) <= half and key in values and values[key]-bias[key] > 0]
                rejected += sum(key in values and abs(t-center) <= half and values[key]-bias[key] <= 0
                                for t, values in run['uwb'][car])
                count[key] = len(values)
                if len(values) >= minimum:
                    row[key] = float(np.median(values))
            observations.append(row if configuration['withheld_wall_car'] != car else {})
            support.append(count)
        cars[car] = dict(model=model, local=local, initial=initial, observations=observations,
                         range_sample_counts=support, nonpositive_corrected_samples=rejected)
    peers = []
    for center in times:
        values, counts = [], []
        for car in CARS:
            shift = configuration['car2_peer_shift_s'] if car == 'car2' else 0.
            samples = [row[PEERS[car]] for t,row in run['uwb'][car]
                       if PEERS[car] in row and abs(t+shift-center) <= half]
            counts.append(len(samples))
            values.append(float(np.median(samples)) if len(samples) >= minimum else None)
        available = [x for x in values if x is not None]
        peers.append(dict(range_m=float(np.mean(available)) if available else None,
                          directions_m=values, direction_counts=counts))
    return dict(times=times, cars=cars, peers=peers, peer_sigma_m=configuration['peer_sigma_m'])


class JointObjective:
    """Two frozen single-car objectives plus zero/one peer residual per epoch."""
    def __init__(self, inputs, joint, antenna_prior=False):
        self.inputs, self.n, self.joint = inputs, len(inputs['times']), joint
        self.antenna_prior = antenna_prior  # Compatibility verification only.
        self.parts = []
        for car in CARS:
            c = inputs['cars'][car]
            self.parts.append(Objective(inputs['times'], c['local'], c['observations'],
                                        c['model'], initial_prior(c['model'])))
        self.peer_indices = np.asarray([i for i,p in enumerate(inputs['peers'])
                                       if joint and p['range_m'] is not None], dtype=int)
        self.peer_measurements = np.asarray([inputs['peers'][i]['range_m'] for i in self.peer_indices])
        self.wall_factor_count = sum(len(p.index) for p in self.parts)
        self.rows = sum(3*self.n+len(p.index) for p in self.parts)+len(self.peer_indices)
        self._x = None

    def evaluate(self, flat):
        flat = np.asarray(flat, dtype=float)
        if self._x is not None and np.array_equal(flat, self._x):
            return self._r, self._jac
        states = flat.reshape(2, self.n, 3)
        residual, jac = np.zeros(self.rows), np.zeros((self.rows, 6*self.n))
        row = 0
        for ci, (car, objective) in enumerate(zip(CARS, self.parts)):
            r, j = objective.evaluate(states[ci].ravel())
            size, col = len(r), 3*self.n*ci
            residual[row:row+size], jac[row:row+size, col:col+3*self.n] = r, j
            if self.antenna_prior:
                model = self.inputs['cars'][car]['model']
                sigma = model['graph_parameters']['prior_position_sigma_m']
                theta = states[ci, 0, 2]
                lever = np.asarray(model['base_to_antenna_body_xy_m'])
                arm = rotation(theta)@lever
                residual[row:row+2] = (states[ci, 0, :2]+arm-model['start_antenna_xyz_m'][:2])/sigma
                jac[row:row+2, col+2] = [-arm[1]/sigma, arm[0]/sigma]
            row += size
        if len(self.peer_indices):
            poses = [states[ci, self.peer_indices] for ci in range(2)]
            arms, arm_derivatives = [], []
            for pose, car in zip(poses, CARS):
                lx,ly = self.inputs['cars'][car]['model']['base_to_antenna_body_xy_m']
                co,si = np.cos(pose[:, 2]), np.sin(pose[:, 2])
                arms.append(np.column_stack((co*lx-si*ly, si*lx+co*ly)))
                arm_derivatives.append(np.column_stack((-si*lx-co*ly, co*lx-si*ly)))
            delta = poses[0][:, :2]+arms[0]-poses[1][:, :2]-arms[1]
            height_delta = (self.inputs['cars']['car1']['model']['antenna_height_m']-
                            self.inputs['cars']['car2']['model']['antenna_height_m'])
            distance = np.sqrt(np.sum(delta*delta, axis=1)+height_delta**2)
            if np.any(distance <= 1e-12):
                raise ValueError('Degenerate zero peer distance')
            sigma = self.inputs['peer_sigma_m']
            error = (distance-self.peer_measurements)/sigma
            s = np.sqrt(1+error*error)
            residual[row:] = error*np.sqrt(2/(s+1))
            derivative = np.sqrt((s+1)/2)/s/sigma
            unit = delta/distance[:, None]
            for k,index in enumerate(self.peer_indices):
                for ci, sign in [(0, 1.), (1, -1.)]:
                    col = 3*(ci*self.n+index)
                    jac[row+k, col:col+3] = sign*derivative[k]*np.r_[
                        unit[k], np.dot(unit[k], arm_derivatives[ci][k])]
        self._x, self._r, self._jac = flat.copy(), residual, jac
        return residual, jac

    def fun(self, flat):
        return self.evaluate(flat)[0].copy()

    def jac(self, flat):
        return self.evaluate(flat)[1].copy()


def solve(inputs, joint, optimizer):
    objective = JointObjective(inputs, joint)
    initial = np.stack([inputs['cars'][car]['initial'] for car in CARS])
    started, cpu_started = time.perf_counter(), time.process_time()
    result = least_squares(objective.fun, initial.ravel(), jac=objective.jac, method='trf',
        tr_solver='exact', loss='linear', max_nfev=optimizer['max_nfev'],
        ftol=optimizer['ftol'], xtol=optimizer['xtol'], gtol=optimizer['gtol'])
    wall, cpu = time.perf_counter()-started, time.process_time()-cpu_started
    if not result.success or not np.isfinite(result.x).all():
        raise RuntimeError('Unaccepted optimization: '+str(result.message))
    states = result.x.reshape(2, len(inputs['times']), 3)
    antenna = []
    for ci,car in enumerate(CARS):
        lever = inputs['cars'][car]['model']['base_to_antenna_body_xy_m']
        antenna.append(states[ci, :, :2]+np.array([rotation(theta)@lever for theta in states[ci, :, 2]]))
    return dict(states=states, antenna_xy=np.asarray(antenna), optimizer=dict(
        success=bool(result.success), status=int(result.status), message=str(result.message),
        nfev=int(result.nfev), njev=int(result.njev), cost=float(result.cost),
        optimality=float(result.optimality), solve_wall_s=wall, solve_cpu_s=cpu),
        wall_factor_count=objective.wall_factor_count, peer_factor_count=len(objective.peer_indices))
