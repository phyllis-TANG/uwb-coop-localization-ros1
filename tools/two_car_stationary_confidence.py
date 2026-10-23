#!/usr/bin/env python3
"""Optional covariance policies on the frozen PR38 full-bag two-car model.

No endpoint, stationary-car label, command, or absolute stationary-position
factor enters the optimizer. Range means and pseudo-Huber loss are unchanged.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
import time

import numpy as np
from scipy.optimize import least_squares

from single_car_sequential_replay import rotation
from two_car_updated_comparison import CARS, JointObjective, sha256


def read_odom_motion(path, expected_sha256):
    """Additional receipt-time pose/twist channel; preserve the old frontend."""
    from rosbags.highlevel import AnyReader
    if sha256(path) != expected_sha256:
        raise ValueError('Dataset SHA256 mismatch: '+str(path))
    rows = {car: [] for car in CARS}
    with AnyReader([Path(path)]) as reader:
        connections = [c for c in reader.connections if c.topic in
                       {'/'+car+'/odom' for car in CARS}]
        for connection, ns, raw in reader.messages(connections=connections):
            msg = reader.deserialize(raw, connection.msgtype)
            p, q = msg.pose.pose.position, msg.pose.pose.orientation
            quat = np.asarray([q.x, q.y, q.z, q.w], dtype=float)
            norm = np.linalg.norm(quat)
            if not np.isfinite(norm) or not .5 <= norm <= 1.5:
                raise ValueError('Invalid Odom quaternion')
            x, y, z, w = quat/norm
            yaw = math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
            twist = msg.twist.twist
            row = [ns*1e-9-reader.start_time*1e-9, p.x, p.y, yaw,
                   twist.linear.x, twist.linear.y, twist.angular.z]
            if not np.isfinite(row).all():
                raise ValueError('Nonfinite Odom pose/twist')
            rows[connection.topic.split('/')[1]].append(row)
    return {car: np.asarray(values, dtype=float) for car, values in rows.items()}


def near_zero_edges(rows, times, policy):
    """Past-only conservative candidates for existing relative Odom factors.

    A row before the window's left edge is included to check coverage and the
    crossing pose increment. A short startup window never qualifies.
    """
    rows, times = np.asarray(rows, dtype=float), np.asarray(times, dtype=float)
    if rows.ndim != 2 or rows.shape[1] != 7 or len(rows) < 2 or not np.isfinite(rows).all():
        raise ValueError('Expected finite receipt,x,y,yaw,vx,vy,wz rows')
    if np.any(np.diff(rows[:, 0]) <= 0) or np.any(np.diff(times) <= 0):
        raise ValueError('Motion/grid times must increase')
    output, diagnostics = [], []
    for start, end in zip(times[:-1], times[1:]):
        left = end-policy['lookback_s']
        lo = max(0, int(np.searchsorted(rows[:, 0], left, side='right'))-1)
        hi = int(np.searchsorted(rows[:, 0], end, side='right'))
        window = rows[lo:hi]
        info = dict(edge_start_s=float(start), edge_end_s=float(end),
                    lookback_start_s=float(left), samples=len(window), candidate=False)
        if len(window) < policy['minimum_samples']:
            info['reason'] = 'insufficient_samples'
        elif window[0, 0] > left+1e-9 or window[-1, 0] < end-policy['max_gap_s']:
            info['reason'] = 'incomplete_lookback_or_stale'
        elif start < left-1e-9:
            info['reason'] = 'edge_exceeds_lookback'
        else:
            dt = np.diff(window[:, 0])
            speed = np.linalg.norm(np.diff(window[:, 1:3], axis=0), axis=1)/dt
            dyaw = np.diff(window[:, 3])
            yaw_rate = np.abs(np.arctan2(np.sin(dyaw), np.cos(dyaw)))/dt
            metrics = dict(max_gap_s=float(max(np.max(dt), end-window[-1, 0])),
                pose_speed_max_mps=float(np.max(speed)),
                pose_yaw_rate_max_degps=float(np.degrees(np.max(yaw_rate))),
                twist_speed_max_mps=float(np.max(np.linalg.norm(window[:, 4:6], axis=1))),
                twist_yaw_rate_max_radps=float(np.max(np.abs(window[:, 6]))))
            info.update(metrics)
            info['candidate'] = all(value <= policy[key] for key, value in metrics.items())
            info['reason'] = 'near_zero_candidate' if info['candidate'] else 'motion_or_gap'
        output.append(info['candidate']); diagnostics.append(info)
    return np.asarray(output, dtype=bool), diagnostics


def confidence_scales(records, wall_floor_m, peer_floor_m):
    """Only predeclared static training records; caller owns train/validation split."""
    if not records or wall_floor_m <= 0 or peer_floor_m <= 0:
        raise ValueError('Empty training records or nonpositive scale floor')
    keys = set(records[0]['wall_errors_m']['car1'])
    wall = {}
    for car in CARS:
        if any(set(row['wall_errors_m'][car]) != keys for row in records):
            raise ValueError('Incomplete static link records')
        wall[car] = {key: float(np.hypot(wall_floor_m, max(
            abs(row['wall_errors_m'][car][key]) for row in records))) for key in sorted(keys)}
    peer = float(np.hypot(peer_floor_m, max(abs(r['peer_error_m']) for r in records)))
    if not all(np.isfinite(x) for x in [peer]+[x for c in wall.values() for x in c.values()]):
        raise ValueError('Nonfinite confidence scale')
    return dict(wall_sigma_m=wall, peer_sigma_m=peer)


class PolicyObjective(JointObjective):
    """Same factors and means, optional relative-motion and range covariances."""
    def __init__(self, inputs, joint, configuration, masks, scales, detector):
        effective = copy.deepcopy(inputs)
        if configuration['range_confidence']:
            effective['peer_sigma_m'] = scales['peer_sigma_m']
        super().__init__(effective, joint)
        multiplier = float(detector['odom_sigma_multiplier'])
        if not 0 < multiplier <= 1:
            raise ValueError('Invalid Odom covariance multiplier')
        for car, part in zip(CARS, self.parts):
            mask = np.asarray(masks[car], dtype=bool)
            if mask.shape != (self.n-1,):
                raise ValueError('Motion candidate shape mismatch')
            if configuration['stationary_covariance']:
                part.sigma_xy[mask] *= multiplier
                part.sigma_yaw[mask] *= multiplier
            if configuration['range_confidence']:
                keys = [key for row in effective['cars'][car]['observations'] for key in sorted(row)]
                # Objective supports elementwise range scales in its existing
                # signed pseudo-Huber residual and exact analytic derivative.
                part.sigma_range = np.asarray([scales['wall_sigma_m'][car][key] for key in keys])


def solve_policy(inputs, joint, configuration, masks, scales, detector, optimizer):
    objective = PolicyObjective(inputs, joint, configuration, masks, scales, detector)
    initial = np.stack([inputs['cars'][car]['initial'] for car in CARS])
    started, cpu = time.perf_counter(), time.process_time()
    result = least_squares(objective.fun, initial.ravel(), jac=objective.jac,
        method='trf', tr_solver='exact', loss='linear', max_nfev=optimizer['max_nfev'],
        ftol=optimizer['ftol'], xtol=optimizer['xtol'], gtol=optimizer['gtol'])
    elapsed, cpu_elapsed = time.perf_counter()-started, time.process_time()-cpu
    if not result.success or not np.isfinite(result.x).all():
        raise RuntimeError('Unaccepted optimization: '+str(result.message))
    states = result.x.reshape(2, len(inputs['times']), 3)
    antenna = np.asarray([states[ci, :, :2]+np.asarray([rotation(th)@np.asarray(
        inputs['cars'][car]['model']['base_to_antenna_body_xy_m']) for th in states[ci, :, 2]])
        for ci, car in enumerate(CARS)])
    return dict(states=states, antenna_xy=antenna, optimizer=dict(success=bool(result.success),
        status=int(result.status), message=str(result.message), nfev=int(result.nfev),
        njev=int(result.njev), cost=float(result.cost), optimality=float(result.optimality),
        solve_wall_s=elapsed, solve_cpu_s=cpu_elapsed), wall_factor_count=objective.wall_factor_count,
        peer_factor_count=len(objective.peer_indices)), objective
