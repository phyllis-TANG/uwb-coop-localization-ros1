#!/usr/bin/env python3
"""Fixed-lag SE(2) replay with analytic factors and square-root marginalization.

The residual definitions match the frozen single-car reference. Old nonlinear
factors are linearized once and eliminated into a Gaussian boundary prior.
No IMU factors, clock correction, new range gates or hardware interfaces.
"""
from __future__ import annotations
import bisect
import collections
import copy
from dataclasses import dataclass
import math
import time
import numpy as np
from scipy.optimize import least_squares
from single_car_sequential_replay import antenna, predict, rotation, wrap


@dataclass
class BoundaryPrior:
    point: np.ndarray
    matrix: np.ndarray
    offset: np.ndarray

    def __post_init__(self):
        self.point = np.asarray(self.point, dtype=float).copy()
        self.matrix = np.asarray(self.matrix, dtype=float).copy()
        self.offset = np.asarray(self.offset, dtype=float).copy()
        if self.point.shape != (3,) or self.matrix.shape != (3, 3) or self.offset.shape != (3,):
            raise ValueError('Invalid boundary prior shape')
        if not all(np.isfinite(x).all() for x in (self.point, self.matrix, self.offset)):
            raise ValueError('Nonfinite boundary prior')

    def residual(self, state):
        delta = np.asarray(state)-self.point
        delta[2] = wrap(delta[2])
        return self.matrix @ delta + self.offset


def initial_prior(model):
    heading = math.radians(model['initial_heading_deg'])
    xy = np.asarray(model['start_antenna_xyz_m'][:2])-rotation(heading)@np.asarray(
        model['base_to_antenna_body_xy_m'])
    p = model['graph_parameters']
    sigmas = [p['prior_position_sigma_m'], p['prior_position_sigma_m'],
              math.radians(p['prior_heading_sigma_deg'])]
    return BoundaryPrior(np.r_[xy, heading], np.diag(1./np.asarray(sigmas)), np.zeros(3))


class Objective:
    """Prior, body-frame Odom increments, signed pseudo-Huber range residuals."""
    def __init__(self, times, local, observations, model, prior):
        self.times = np.asarray(times, dtype=float)
        self.local = np.asarray(local, dtype=float)
        self.n = len(self.times)
        if self.n < 1 or self.local.shape != (self.n, 3) or len(observations) != self.n:
            raise ValueError('Inconsistent graph inputs')
        dt = np.diff(self.times)
        if np.any(dt <= 0):
            raise ValueError('Graph times must increase')
        p = model['graph_parameters']
        self.sigma_xy = p['odom_translation_sigma_m']*np.sqrt(dt)
        self.sigma_yaw = math.radians(p['odom_yaw_sigma_deg'])*np.sqrt(dt)
        dlo = np.diff(self.local[:, :2], axis=0)
        co, si = np.cos(self.local[:-1, 2]), np.sin(self.local[:-1, 2])
        self.measured_body = np.column_stack((co*dlo[:, 0]+si*dlo[:, 1],
                                             -si*dlo[:, 0]+co*dlo[:, 1]))
        self.measured_yaw = np.arctan2(np.sin(np.diff(self.local[:, 2])),
                                      np.cos(np.diff(self.local[:, 2])))
        samples = [(i, key, raw-model['range_bias_m'][key])
                   for i, row in enumerate(observations) for key, raw in sorted(row.items())]
        self.index = np.asarray([s[0] for s in samples], dtype=int)
        self.refs = np.asarray([model['anchors_xyz_m'][s[1]] for s in samples]).reshape(-1, 3)
        self.measured = np.asarray([s[2] for s in samples])
        if np.any(self.measured <= 0):
            raise ValueError('Nonpositive corrected range')
        self.height = float(model['antenna_height_m'])
        self.lever = np.asarray(model['base_to_antenna_body_xy_m'])
        self.sigma_range = float(p['range_sigma_m'])
        self.prior = prior
        self._x = None

    def evaluate(self, flat):
        flat = np.asarray(flat)
        if self._x is not None and np.array_equal(flat, self._x):
            return self._r, self._jac
        states = flat.reshape(self.n, 3)
        count = 3*self.n+len(self.index)
        residual = np.zeros(count)
        jac = np.zeros((count, 3*self.n))
        residual[:3] = self.prior.residual(states[0])
        jac[:3, :3] = self.prior.matrix
        if self.n > 1:
            delta = np.diff(states[:, :2], axis=0)
            co, si = np.cos(states[:-1, 2]), np.sin(states[:-1, 2])
            body = np.column_stack((co*delta[:, 0]+si*delta[:, 1],
                                    -si*delta[:, 0]+co*delta[:, 1]))
            angle_error = np.diff(states[:, 2])-self.measured_yaw
            between = np.column_stack(((body-self.measured_body)/self.sigma_xy[:, None],
                np.arctan2(np.sin(angle_error), np.cos(angle_error))/self.sigma_yaw))
            residual[3:3*self.n] = between.ravel()
            for i in range(self.n-1):
                row, left, right = 3+3*i, 3*i, 3*(i+1)
                invrot = np.array([[co[i], si[i]], [-si[i], co[i]]])/self.sigma_xy[i]
                jac[row:row+2, left:left+2] = -invrot
                jac[row:row+2, right:right+2] = invrot
                jac[row:row+2, left+2] = [body[i, 1]/self.sigma_xy[i], -body[i, 0]/self.sigma_xy[i]]
                jac[row+2, left+2] = -1/self.sigma_yaw[i]
                jac[row+2, right+2] = 1/self.sigma_yaw[i]
        if len(self.index):
            pose = states[self.index]
            co, si = np.cos(pose[:, 2]), np.sin(pose[:, 2])
            lx, ly = self.lever
            arm = np.column_stack((co*lx-si*ly, si*lx+co*ly))
            delta = pose[:, :2]+arm-self.refs[:, :2]
            distance = np.sqrt(np.sum(delta*delta, axis=1)+(self.height-self.refs[:, 2])**2)
            if np.any(distance <= 1e-12):
                raise ValueError('Degenerate zero antenna-anchor distance')
            error = (distance-self.measured)/self.sigma_range
            s = np.sqrt(1+error*error)
            residual[3*self.n:] = error*np.sqrt(2/(s+1))
            # Exact derivative of the legacy signed pseudo-Huber transform.
            derivative = np.sqrt((s+1)/2)/s/self.sigma_range
            unit = delta/distance[:, None]
            arm_derivative = np.column_stack((-si*lx-co*ly, co*lx-si*ly))
            theta_derivative = np.sum(unit*arm_derivative, axis=1)
            for k, index in enumerate(self.index):
                jac[3*self.n+k, 3*index:3*index+3] = derivative[k]*np.r_[unit[k], theta_derivative[k]]
        self._x, self._r, self._jac = flat.copy(), residual, jac
        return residual, jac

    def fun(self, x):
        return self.evaluate(x)[0].copy()

    def jac(self, x):
        return self.evaluate(x)[1].copy()


def eliminate_oldest(states, times, local, observations, model, prior):
    """Consume ONLY incident old factors; retained-state factors stay explicit.

    QR eliminates the old 3-vector and compresses the remaining linear system.
    Both square-root information and its residual offset are preserved.
    """
    objective = Objective(times[:2], local[:2], [observations[0], {}], model, prior)
    r, jac = objective.evaluate(np.asarray(states[:2]).ravel())
    old, boundary = jac[:, :3], jac[:, 3:6]
    if np.linalg.matrix_rank(old) != 3:
        raise ValueError('Rank-deficient old-state elimination')
    if np.linalg.matrix_rank(jac) != 6:
        raise ValueError('Rank-deficient joint information; boundary is not fully constrained')
    q, _ = np.linalg.qr(old, mode='complete')
    projected_jac = q[:, 3:].T @ boundary
    projected_r = q[:, 3:].T @ r
    q2, matrix = np.linalg.qr(projected_jac, mode='reduced')
    offset = q2.T @ projected_r
    if matrix.shape != (3, 3) or np.linalg.matrix_rank(matrix) != 3:
        raise ValueError('Rank-deficient boundary prior')
    sign = np.where(np.diag(matrix) < 0, -1., 1.)
    matrix, offset = sign[:, None]*matrix, sign*offset
    constant = max(0., float(projected_r@projected_r-offset@offset))
    return BoundaryPrior(np.asarray(states[1]), matrix, offset), constant


class WindowGraph:
    def __init__(self, model, lag_s=20., max_nfev=50):
        self.model = copy.deepcopy(model)
        self.minimum_step = float(model['graph_parameters'].get('keyframe_step_s', 1.))
        if self.minimum_step <= 0:
            raise ValueError('Invalid minimum keyframe spacing')
        if lag_s is not None and (not np.isfinite(lag_s) or lag_s < 2*self.minimum_step):
            raise ValueError('Invalid lag')
        self.lag_s, self.max_nfev = lag_s, int(max_nfev)
        if self.max_nfev < 1:
            raise ValueError('Invalid solver evaluation budget')
        self.prior = initial_prior(model)
        self.times, self.local, self.observations, self.states = [], [], [], []
        self.marginalizations = 0
        self.eliminated_constant = 0.
        self.peak_solve_states = self.peak_transient_states = 0
        self.total_keyframes = 0

    def update(self, stamp, local, observations):
        local = np.asarray(local, dtype=float).copy()
        if self.times and stamp-self.times[-1] < self.minimum_step-1e-9:
            raise ValueError('Graph keyframes violate the minimum spacing')
        if local.shape != (3,) or not np.isfinite(local).all():
            raise ValueError('Invalid local Odom state')
        guess = self.prior.point.copy() if not self.states else predict(
            self.states[-1], self.local[-1], local)
        self.times.append(float(stamp)); self.local.append(local)
        self.observations.append(dict(observations)); self.states.append(guess)
        self.total_keyframes += 1
        self.peak_transient_states = max(self.peak_transient_states, len(self.times))
        started = time.perf_counter()
        while self.lag_s is not None and self.times[-1]-self.times[0] > self.lag_s+1e-12:
            self.prior, constant = eliminate_oldest(
                self.states, self.times, self.local, self.observations, self.model, self.prior)
            self.eliminated_constant += constant
            for seq in (self.times, self.local, self.observations, self.states):
                del seq[0]
            self.marginalizations += 1
        marginal_wall = time.perf_counter()-started
        n = len(self.times)
        self.peak_solve_states = max(self.peak_solve_states, n)
        accepted, status = False, 'predict_only_warmup'
        info, candidate = {}, None
        started = time.perf_counter()
        if n >= 3:
            try:
                objective = Objective(self.times, self.local, self.observations, self.model, self.prior)
                result = least_squares(objective.fun, np.asarray(self.states).ravel(),
                    jac=objective.jac, method='trf', tr_solver='exact', loss='linear',
                    max_nfev=self.max_nfev, ftol=1e-7, xtol=1e-7, gtol=1e-7)
                if np.isfinite(result.x).all():
                    candidate = result.x.reshape(n, 3)[-1].tolist()
                accepted = bool(result.success and candidate is not None)
                info = dict(optimizer_success=bool(result.success), optimizer_status=int(result.status),
                            optimizer_nfev=int(result.nfev), optimizer_njev=int(result.njev),
                            optimizer_cost=float(result.cost), optimizer_optimality=float(result.optimality),
                            optimizer_message=str(result.message))
                if accepted:
                    self.states = [p.copy() for p in result.x.reshape(n, 3)]
                    status = 'graph' if observations else 'graph_no_current_ranges'
                else:
                    status = 'predict_only_solver_failed'
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
                status = 'predict_only_solver_error'
                info = dict(error=type(error).__name__+': '+str(error))
        solve_wall = time.perf_counter()-started
        return dict(pose=self.states[-1].tolist(), accepted_graph=accepted, status=status,
                    candidate_pose=candidate, optimizer=info, graph_states=n,
                    graph_time_span_s=self.times[-1]-self.times[0],
                    marginalizations=self.marginalizations, marginal_wall_s=marginal_wall,
                    solve_wall_s=solve_wall, prior_matrix=self.prior.matrix.tolist(),
                    prior_offset=self.prior.offset.tolist(), prior_point=self.prior.point.tolist())


class FixedLagReplay:
    """Bounded estimator buffers. Full output history belongs to an external sink.

    Receipt availability and closed-bin policies match SequentialReplay. A
    source timing fault that exceeds the explicit sample capacity fails loudly.
    """
    def __init__(self, model, policy, on_output, lag_s=20., max_nfev=50, max_sensor_samples=512):
        self.model, self.policy = copy.deepcopy(model), copy.deepcopy(policy)
        self.step = float(policy['keyframe_step_s'])
        self.half = float(policy['range_bin_half_width_s'])
        self.delay = float(policy['release_delay_s'])
        self.margin = float(policy['first_keyframe_margin_s'])
        self.minimum = int(policy['minimum_samples_per_link'])
        if not (self.step > 0 and 0 <= self.half < self.step/2 and self.delay >= self.half
                and self.minimum >= 1 and max_sensor_samples >= 2):
            raise ValueError('Invalid frontend policy')
        self.graph = WindowGraph(model, lag_s, max_nfev)
        if abs(self.step-self.graph.minimum_step) > 1e-12:
            raise ValueError('Frontend and graph keyframe spacing differ')
        self.on_output = on_output
        self.max_samples = int(max_sensor_samples)
        self.odom, self.ranges = [], []
        self.first, self.latest_header = {}, {}
        self.first_state = self.next_state = self.last_closed_state = None
        self.now = -math.inf
        self.first_local = None
        self.previous_pose = self.previous_local = None
        self.dependency_max = -math.inf
        self.worker_finish = 0.
        self.output_count = 0
        self.counters = collections.Counter()
        self.sensor_peaks = {'odom': 0, 'uwb': 0}

    def ingest(self, event):
        if not np.isfinite(event.received_s) or event.received_s < self.now:
            raise ValueError('Receipt time must be finite and nondecreasing')
        self._advance(event.received_s, inclusive=False)
        self.now = float(event.received_s)
        self.counters[event.kind+'_events'] += 1
        if event.kind not in ('odom', 'uwb'):
            return
        stamp = float(event.header_s)
        if not np.isfinite(stamp):
            raise ValueError('Invalid header timestamp')
        if event.kind in self.latest_header and stamp <= self.latest_header[event.kind]:
            raise ValueError('Nonincreasing '+event.kind+' header; no silent reordering')
        self.latest_header[event.kind] = stamp
        self.first.setdefault(event.kind, stamp)
        if event.kind == 'odom':
            value = np.asarray(event.value, dtype=float).copy()
            if value.shape != (3,) or not np.isfinite(value).all():
                raise ValueError('Invalid Odom pose')
            if self.odom:
                value[2] = self.odom[-1][1][2]+wrap(value[2]-self.odom[-1][1][2])
            self.odom.append((stamp, value, self.now))
        else:
            values = {}
            for key, raw in event.value.items():
                if key not in self.model['anchors_xyz_m']:
                    continue
                if not np.isfinite(raw) or raw <= 0:
                    self.counters['invalid_raw_ranges'] += 1
                elif raw-self.model['range_bias_m'][key] <= 0:
                    self.counters['nonpositive_corrected_ranges'] += 1
                else:
                    values[key] = float(raw)
            self.ranges.append((stamp, values, self.now))
            if self.last_closed_state is not None:
                candidate = self.first_state+round((stamp-self.first_state)/self.step)*self.step
                if (self.first_state <= candidate <= self.last_closed_state
                        and abs(stamp-candidate) <= self.half and self.now > candidate+self.delay):
                    self.counters['late_packets_for_closed_bins'] += 1
        if self.next_state is None and 'odom' in self.first and 'uwb' in self.first:
            self.next_state = float(math.ceil(max(self.first.values())+self.margin))
            if self.next_state+self.delay < self.now:
                skipped = int(math.ceil((self.now-self.next_state-self.delay)/self.step))
                self.next_state += skipped*self.step
                self.counters['bootstrap_skipped_deadlines'] += skipped
            self.first_state = self.next_state
        self._prune(self.next_state)

    def finish(self):
        if np.isfinite(self.now):
            self._advance(self.now, inclusive=True)

    def _advance(self, until, inclusive):
        while self.next_state is not None:
            deadline = self.next_state+self.delay
            if not (deadline < until or (inclusive and deadline <= until)):
                break
            self._emit(self.next_state, deadline)
            self.next_state += self.step

    def _prune(self, next_state):
        if next_state is not None:
            self.ranges = [r for r in self.ranges if r[0] >= next_state-self.half]
            before = bisect.bisect_right([r[0] for r in self.odom], next_state)-1
            if before > 0:
                del self.odom[:before]  # Retain the one earlier interpolation endpoint.
        for key, rows in [('odom', self.odom), ('uwb', self.ranges)]:
            if len(rows) > self.max_samples:
                raise BufferError(key+' source buffer capacity exceeded; inspect source clocks/gaps')
            self.sensor_peaks[key] = max(self.sensor_peaks[key], len(rows))

    def _interpolate(self, stamp):
        times = [r[0] for r in self.odom]
        i = bisect.bisect_left(times, stamp)
        if i < len(times) and times[i] == stamp:
            return self.odom[i][1].copy(), self.odom[i][2]
        if i == 0 or i == len(times):
            return None, None
        a,b = self.odom[i-1], self.odom[i]
        ratio = (stamp-a[0])/(b[0]-a[0])
        return a[1]+ratio*(b[1]-a[1]), max(a[2],b[2])

    def _emit(self, stamp, deadline):
        started = time.perf_counter()
        self.last_closed_state = stamp
        local, receipt = self._interpolate(stamp)
        if local is None:
            self.counters['missing_odom_bracket'] += 1
            record = dict(state_time_s=stamp, availability_cutoff_s=deadline,
                          status='missing_odom_bracket', accepted_graph=False, pose=None,
                          antenna_xy_m=None, graph_states=len(self.graph.times),
                          dependency_receipt_max_s=None, solve_wall_s=0., marginal_wall_s=0.)
        else:
            grouped = collections.defaultdict(list)
            receipts = [receipt]
            for header, values, received in self.ranges:
                if abs(header-stamp) <= self.half:
                    for key, raw in values.items():
                        grouped[key].append(raw)
                    if values:
                        receipts.append(received)
            observations = {key: float(np.median(values)) for key,values in sorted(grouped.items())
                            if len(values) >= self.minimum}
            self.dependency_max = max(self.dependency_max, max(receipts))
            if self.dependency_max > deadline:
                raise AssertionError('A dependency arrived after its output cutoff')
            if self.first_local is None:
                self.first_local = local.copy()
            heading = math.radians(self.model['initial_heading_deg'])
            angle = heading-self.first_local[2]
            aligned = np.r_[rotation(angle)@(local[:2]-self.first_local[:2])+initial_prior(self.model).point[:2],
                            local[2]+angle]
            prediction = aligned if self.previous_pose is None else predict(
                self.previous_pose, self.previous_local, local)
            graph_result = self.graph.update(stamp, local, observations)
            pose = np.asarray(graph_result['pose'])
            self.previous_pose, self.previous_local = pose.copy(), local.copy()
            record = dict(graph_result, state_time_s=stamp, availability_cutoff_s=deadline,
                          antenna_xy_m=antenna(pose,self.model['base_to_antenna_body_xy_m']).tolist(),
                          local_odom=local.tolist(), aligned_odom_pose=aligned.tolist(),
                          aligned_odom_antenna_xy_m=antenna(aligned,self.model['base_to_antenna_body_xy_m']).tolist(),
                          range_medians_m=observations,
                          range_sample_counts={key: len(grouped[key]) for key in sorted(self.model['anchors_xyz_m'])},
                          dependency_receipt_max_s=self.dependency_max,
                          position_correction_m=float(np.linalg.norm(pose[:2]-prediction[:2])),
                          yaw_correction_deg=float(math.degrees(abs(wrap(pose[2]-prediction[2])))))
        self._prune(stamp+self.step)
        record['sensor_buffer_counts'] = dict(odom=len(self.odom), uwb=len(self.ranges))
        duration = time.perf_counter()-started
        worker_start = max(deadline,self.worker_finish)
        self.worker_finish = worker_start+duration
        record.update(update_wall_s=duration, estimated_worker_start_s=worker_start,
                      estimated_worker_finish_s=self.worker_finish, estimated_worker_queue_s=worker_start-deadline)
        self.output_count += 1
        self.on_output(copy.deepcopy(record))
