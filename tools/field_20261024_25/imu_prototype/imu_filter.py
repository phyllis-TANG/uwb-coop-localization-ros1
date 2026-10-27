"""Arrival-causal four-state/car motion and fixed independent/joint range EKF."""
from collections import Counter
import copy
import math
import numpy as np

from legacy import CARS, TAGS, WALLS, model
from configuration import IMU_MODES, mode_of, readiness, validate
from dynamics import transition, process_covariance, range_geometry, wrap
from io_utils import clean


def trace_row(row, measured):
    return dict(vehicle_id=row['vehicle_id'], source_file_sha256=row['source_file_sha256'], topic=row['topic'],
                record_index=row['record_index'], header_epoch_ns=row['header_epoch_ns'],
                receive_epoch_ns=row['receive_epoch_ns'], sample_epoch_ns=measured)


class LegacyAdapter:
    def __init__(self, method, config):
        validate(config)
        self.engine = model.Baseline(method, config)
        self.method, self.mode, self.config = method, 'legacy_odom_pose', copy.deepcopy(config)
        self.counts = Counter()
        self.last_receive = None

    def process(self, event):
        row = event['row']; receive = row['receive_epoch_ns']
        if self.last_receive is not None and receive < self.last_receive:
            raise ValueError('events must follow arrival order')
        self.last_receive = receive
        if event['kind'] == 'imu':
            detail = dict(kind='imu', vehicle_id=row['vehicle_id'], status='legacy_imu_not_used',
                          record_index=row['record_index'], header_epoch_ns=row['header_epoch_ns'], receive_epoch_ns=receive)
        else:
            detail = self.engine.process(event)
        self.counts[detail['status']] += 1
        return detail

    def snapshot(self, publication):
        return self.engine.snapshot(publication)

    def provenance(self, car):
        return dict(imu_mode_status='legacy_not_used', gyro_bias_rad_s=None, gyro_bias_variance=None,
                    last_imu=None, last_velocity=None, gyro_bias_estimated=False, unobserved_motion_gap=False)

    def full_trace(self):
        initialized = [c for c in CARS if c in self.engine.odom]
        complete = len(initialized) == 2
        return dict(state_dimension=6, initialized_vehicle_ids=initialized,
                    legacy_state_6d=self.engine.x.tolist() if complete else None,
                    legacy_covariance_6x6=self.engine.P.tolist() if complete else None,
                    augmented_state_8d=None, augmented_covariance_8x8=None)


class ImuFilter:
    def __init__(self, method, config):
        validate(config)
        if method not in ('independent', 'joint'):
            raise ValueError('only independent/fixed joint are implemented')
        self.config, self.method = copy.deepcopy(config), method
        self.proto = self.config['imu_prototype']; self.mode = mode_of(config)
        if self.mode == 'legacy_odom_pose':
            raise ValueError('legacy must be executed by LegacyAdapter')
        self.estimate_bias = self.mode == 'body_imu_bias'
        self.params = {name: item['value'] for name, item in self.proto['parameters'].items()}
        self.blocked = readiness(config, method)
        self.x, self.P = np.zeros(8), np.zeros((8, 8))
        self.times, self.controls, self.last_used = {}, {c: {} for c in CARS}, {c: {} for c in CARS}
        self.seen, self.last_source, self.link_time = set(), {}, {}
        self.counts, self.gap_counts = Counter(), Counter()
        self.failure, self.gap_wait = {}, {}
        self.last_receive = None
        self.wall_geometry = {}
        self.initial_records = {}
        self.observability_phi = {c: np.eye(4) for c in CARS}
        self.wall_gramian = {c: np.zeros((4, 4)) for c in CARS}
        self.geometry = {}
        if self.proto['ranges_enabled']:
            for car in CARS:
                if not self.blocked[car]:
                    cc = config['vehicles'][car]
                    self.geometry[car] = dict(lever_xy=model.antenna_offset_xy(cc), height=model.antenna_height(cc))

    def sl(self, car):
        i = 4 * CARS.index(car)
        return slice(i, i + 4)

    def _rate(self, car):
        return self.controls[car].get('odom_rate' if self.mode == 'body_odom_rate' else 'imu')

    def _support(self, car, target, range_check=False):
        if car not in self.times:
            return 'uninitialized:' + car
        velocity, rate = self.controls[car].get('velocity'), self._rate(car)
        if velocity is None or rate is None:
            return 'waiting_' + ('velocity' if velocity is None else 'imu') + ':' + car
        if target < self.times[car]:
            return 'measurement_before_state:' + car
        for control, name in ((velocity, 'velocity'), (rate, 'rate')):
            if control['trace']['sample_epoch_ns'] > self.times[car]:
                return 'control_after_state:' + car
            age = target - control['trace']['sample_epoch_ns']
            limit = min(self.params['max_control_hold_ns'], self.config['max_extrapolation_ns']) if range_check else self.params['max_control_hold_ns']
            if age > limit:
                return 'stale_' + name + '_support:' + car
        return None

    def _finite(self, x, P):
        return bool(np.isfinite(x).all() and np.isfinite(P).all() and np.linalg.eigvalsh((P + P.T) / 2).min() >= -1e-9)

    def _propagate(self, car, target, detail):
        start = self.times[car]
        if target == start:
            return True
        velocity, rate = self.controls[car]['velocity'], self._rate(car)
        if max(velocity['trace']['sample_epoch_ns'], rate['trace']['sample_epoch_ns']) > start:
            raise ValueError('future control endpoint attempted backward integration')
        dt = (target - start) / 1e9; sl = self.sl(car); before = self.x[sl].copy()
        after, F4 = transition(before, velocity['value'], rate['value'], dt, self.estimate_bias)
        Q4 = process_covariance(before, velocity['value'], rate['value'], dt, self.estimate_bias,
                                self.params['velocity_noise'], self.params['heading_noise'], self.params['bias_random_walk'])
        F = np.eye(8); F[sl, sl] = F4
        proposal = self.x.copy(); proposal[sl] = after
        covariance = F @ self.P @ F.T; covariance[sl, sl] += Q4
        covariance = (covariance + covariance.T) / 2
        if not self._finite(proposal, covariance):
            self.failure[car] = 'numerical_propagation_failed_hold'
            detail['numerical_failures'].append(dict(vehicle_id=car, status=self.failure[car]))
            return False
        self.x, self.P = proposal, covariance; self.times[car] = target
        self.observability_phi[car] = F4 @ self.observability_phi[car]
        self.last_used[car]['velocity'] = copy.deepcopy(velocity['trace'])
        self.last_used[car]['rate'] = copy.deepcopy(rate['trace'])
        self.failure.pop(car, None)
        detail['propagations'].append(dict(vehicle_id=car, from_epoch_ns=start, to_epoch_ns=target, dt_ns=target - start,
            velocity=copy.deepcopy(velocity['trace']), angular=copy.deepcopy(rate['trace']),
            rate_source='odom_rate' if self.mode == 'body_odom_rate' else 'imu', body_velocity_m_s=velocity['value'],
            observed_rate_rad_s=rate['value'], corrected_rate_rad_s=rate['value'] - before[3] if self.estimate_bias else rate['value'],
            state_before_4d=before.tolist(), state_after_4d=after.tolist(), jacobian_4x4=F4.tolist(), Q_4x4=Q4.tolist()))
        return True

    def _advance_old_controls(self, car, target, detail):
        if target == self.times[car]:
            return True
        velocity, rate = self.controls[car].get('velocity'), self._rate(car)
        if velocity is None or rate is None:
            self.gap_wait[car] = self.times[car]
            return False
        if max(velocity['trace']['sample_epoch_ns'], rate['trace']['sample_epoch_ns']) > self.times[car]:
            self.gap_wait[car] = self.times[car]
            return False
        stop = min(target, velocity['trace']['sample_epoch_ns'] + self.params['max_control_hold_ns'],
                   rate['trace']['sample_epoch_ns'] + self.params['max_control_hold_ns'])
        if stop > self.times[car] and not self._propagate(car, stop, detail):
            return False
        if stop < target:
            self.gap_wait[car] = self.times[car]
            return False
        return True

    def _resync(self, car, receive, detail):
        velocity, rate = self.controls[car].get('velocity'), self._rate(car)
        if velocity is None or rate is None:
            return
        target = max(self.times[car], velocity['trace']['sample_epoch_ns'], rate['trace']['sample_epoch_ns'])
        if target > receive:
            raise ValueError('future reanchor attempted')
        if any(target - c['trace']['sample_epoch_ns'] > self.params['max_control_hold_ns'] for c in (velocity, rate)):
            return
        if target > self.times[car]:
            start = self.times[car]; dt = (target - start) / 1e9; sl = self.sl(car)
            diagonal = np.array([self.params['gap_xy_noise']**2] * 2 + [self.params['gap_yaw_noise']**2,
                         self.params['bias_random_walk']**2 if self.estimate_bias else 0.]) * dt
            self.P[sl, sl] += np.diag(diagonal)
            self.P = (self.P + self.P.T) / 2; self.times[car] = target; self.gap_counts[car] += 1
            detail['gap_reanchors'].append(dict(vehicle_id=car, from_epoch_ns=start, to_epoch_ns=target,
                unknown_duration_ns=target - start, pose_mean_held=True, missing_motion_not_integrated=True,
                covariance_added_diagonal=diagonal.tolist(), recovery='controls_available_but_missing_displacement_not_recovered'))
        self.gap_wait.pop(car, None)

    def process(self, event):
        row, kind = event['row'], event['kind']; car = row['vehicle_id']; receive = row['receive_epoch_ns']
        if car not in CARS or kind not in ('odom', 'imu', 'range'):
            raise ValueError('unknown vehicle/event kind')
        if self.last_receive is not None and receive < self.last_receive:
            raise ValueError('events must be processed in arrival order')
        self.last_receive = receive
        detail = dict(kind=kind, vehicle_id=car, record_index=row['record_index'], header_epoch_ns=row['header_epoch_ns'],
                      receive_epoch_ns=receive, measurement_epoch_ns=None, propagations=[], gap_reanchors=[], numerical_failures=[])
        def result(status):
            detail['status'] = status; self.counts[status] += 1
            return detail
        identity = (kind, car, row['source_file_sha256'], row['record_index'], row.get('link_index', 0))
        if identity in self.seen:
            return result('duplicate_trace')
        self.seen.add(identity)
        if kind == 'imu' and self.mode == 'body_odom_rate':
            return result('imu_not_used_odom_rate_control')
        if self.blocked[car]:
            detail['blocked_reasons'] = self.blocked[car]
            return result('BLOCKED')
        if kind == 'range' and not self.proto['ranges_enabled']:
            return result('excluded_source_frame_ranges')
        clock = self.proto['vehicles'][car]['imu_clock'] if kind == 'imu' else self.config['vehicles'][car]['odom_clock' if kind == 'odom' else 'range_clock']
        try:
            measured = model.map_time(row, clock)
        except model.ClockIntervalError:
            return result('clock_outside_valid_interval')
        detail['measurement_epoch_ns'] = measured
        if measured > receive:
            return result('future_measurement_time')
        if receive - measured > (self.params['max_control_latency_ns'] if kind in ('odom', 'imu') else self.config['max_measurement_latency_ns']):
            return result('stale_measurement_on_arrival')
        if kind in ('odom', 'imu'):
            if (car, kind) in self.last_source and measured <= self.last_source[car, kind]:
                return result('duplicate_or_out_of_order_source_time')
            if car in self.times and measured < self.times[car]:
                return result('late_control_before_state_not_backfilled')
            if kind == 'odom':
                if row.get('frame_id') != car + '/odom' or row.get('child_frame_id') != car + '/base_footprint':
                    return result('invalid_velocity_frame')
                try:
                    velocity = [float(row['linear_x']), float(row['linear_y'])]
                    if not np.isfinite(velocity).all():
                        raise ValueError('nonfinite velocity')
                    rate = float(row['angular_z']) if self.mode == 'body_odom_rate' else None
                    if rate is not None and not math.isfinite(rate):
                        raise ValueError('nonfinite odom rate')
                except (ValueError, TypeError, KeyError):
                    return result('invalid_velocity_or_odom_rate')
                if car not in self.times:
                    cc = self.config['vehicles'][car]; binding = cc.get('initial_record_binding')
                    if binding is not None and not (binding.get('status') == 'provided' and bool(binding.get('source')) and all(str(row.get(k)) == str(binding.get(k)) for k in ('source_file_sha256', 'record_index', 'header_epoch_ns', 'receive_epoch_ns'))):
                        return result('initial_binding_mismatch')
                    try:
                        pose = model.pose_from_row(row) if self.proto['frame_mode'] == 'source_odometry_motion_only' else np.asarray(cc['initial_room_pose']['value'], dtype=float)
                    except (KeyError, TypeError, ValueError):
                        return result('invalid_initial_pose')
                    sl = self.sl(car); self.x[sl] = np.r_[pose, self.proto['vehicles'][car]['bias_initial']['value'] if self.estimate_bias else 0.]
                    diag = list(cc['initial_covariance_diagonal']['value']) + [self.proto['vehicles'][car]['bias_initial_sigma']['value']**2 if self.estimate_bias else 0.]
                    self.P[sl, sl] = np.diag(diag); self.times[car] = measured; status = 'initialized'
                    self.initial_records[car] = trace_row(row, measured)
                else:
                    self._advance_old_controls(car, measured, detail); status = 'velocity_control_accepted'
                trace = trace_row(row, measured); self.controls[car]['velocity'] = dict(trace=trace, value=velocity)
                if self.mode == 'body_odom_rate':
                    self.controls[car]['odom_rate'] = dict(trace=trace, value=rate)
            else:
                if row.get('frame_id') != self.proto['vehicles'][car]['imu_frame_id']['value']:
                    return result('invalid_imu_frame')
                if row.get('angular_velocity_units', 'rad/s') != 'rad/s':
                    return result('unsupported_gyro_units')
                try:
                    raw = np.array([float(row['angular_velocity_' + axis]) for axis in 'xyz'])
                    if not np.isfinite(raw).all():
                        raise ValueError('nonfinite gyro')
                except (ValueError, TypeError, KeyError):
                    return result('invalid_gyro_vector')
                if car in self.times:
                    self._advance_old_controls(car, measured, detail)
                mapped = float(raw @ np.asarray(self.proto['vehicles'][car]['gyro_axis_body_z_in_imu_frame']['value']))
                self.controls[car]['imu'] = dict(trace=trace_row(row, measured), value=mapped)
                status = 'imu_control_accepted' if car in self.times else 'imu_cached_waiting_initialization'
            self.last_source[car, kind] = measured
            if car in self.times:
                self._resync(car, receive, detail)
            return result('recovered_with_gap_uncertainty' if detail['gap_reanchors'] else status)
        # Range identity/primary/direction gates precede any state propagation.
        if row.get('tag_id') != TAGS[car]:
            return result('invalid_range_identity')
        if row.get('source') != 'raw' or str(row.get('primary_observation')) not in ('1', 'True'):
            return result('excluded_bridge_duplicate')
        if row.get('pairing_status') in ('ambiguous_header', 'paired_mismatch'):
            return result('excluded_ambiguous_or_mismatched_pair')
        try:
            value = float(row['range_m'])
            if isinstance(row['range_m'], bool) or not math.isfinite(value) or value <= 0 or str(row.get('valid')) not in ('1', 'True'):
                raise ValueError('invalid range')
        except (ValueError, TypeError, KeyError):
            return result('invalid_range')
        target = row.get('target_id'); peer = target == TAGS['car2' if car == 'car1' else 'car1']
        if not peer and target not in WALLS:
            return result('unknown_range_target')
        if peer and self.method == 'independent':
            return result('excluded_independent_peer')
        if peer and car != 'car1':
            return result('excluded_correlated_reverse_direction')
        involved = CARS if peer else (car,)
        for name in involved:
            reason = self._support(name, measured, True)
            if reason:
                return result(reason)
        key = car, target
        if key in self.link_time:
            delta = measured - self.link_time[key]
            if delta <= 0:
                return result('duplicate_or_out_of_order_link_time')
            if delta < self.config['min_range_spacing_ns']:
                return result('excluded_fixed_rate_thinning')
        for name in involved:
            if not self._propagate(name, measured, detail):
                return result('numerical_range_prediction_failed_hold')
        try:
            expected, H = range_geometry(self.x, self.geometry, self.config['anchors_xyz_m']['value'], car, target)
        except (ValueError, KeyError):
            return result('invalid_range_geometry')
        variance = self.config['weights']['peer_sigma_m' if peer else 'wall_sigma_m']['value']**2
        S = float(H @ self.P @ H + variance)
        if not math.isfinite(S) or S <= 0:
            for name in involved: self.failure[name] = 'numerical_range_failed_hold'
            return result('numerical_range_failed_hold')
        K = self.P @ H / S; prior = self.x.copy(); before_P = self.P.copy()
        proposal = prior + K * (value - expected); proposal[2], proposal[6] = wrap(proposal[2]), wrap(proposal[6])
        J = np.eye(8) - np.outer(K, H); covariance = J @ self.P @ J.T + np.outer(K, K) * variance; covariance = (covariance + covariance.T) / 2
        if not self._finite(proposal, covariance):
            for name in involved: self.failure[name] = 'numerical_range_failed_hold'
            return result('numerical_range_failed_hold')
        self.x, self.P = proposal, covariance; self.link_time[key] = measured
        for name in involved: self.failure.pop(name, None)
        if not peer:
            self.wall_geometry[car, target] = measured, H[self.sl(car)][:2].copy()
            initial_row = H[self.sl(car)] @ self.observability_phi[car]
            self.wall_gramian[car] += np.outer(initial_row, initial_row) / variance
        detail['range_update'] = dict(expected_range_m=expected, innovation_m=value - expected, variance_m2=variance,
            H_8d=H.tolist(), gain_8d=K.tolist(), prior_state_8d=prior.tolist(), prior_covariance_8x8=before_P.tolist(),
            posterior_state_8d=proposal.tolist(), posterior_covariance_8x8=covariance.tolist(),
            bias_direct_H_zero=True, covariance_semantics='uncalibrated_engineering_EKF_Joseph')
        return result('peer_updated' if peer else 'wall_updated')

    def provenance(self, car):
        initialized = car in self.times; sl = self.sl(car)
        used = self.last_used[car]
        gyro_used = used.get('rate') if self.mode in IMU_MODES else None
        rate = self._rate(car); velocity = self.controls[car].get('velocity')
        return dict(imu_mode_status='odom_rate_control' if self.mode == 'body_odom_rate' else 'waiting_imu' if rate is None else 'recovered_with_gap_uncertainty' if self.gap_counts[car] else 'imu_control_available',
            gyro_bias_rad_s=float(self.x[sl][3]) if initialized and self.mode in IMU_MODES else None,
            gyro_bias_variance=float(self.P[sl, sl][3, 3]) if initialized and self.mode in IMU_MODES else None,
            gyro_bias_estimated=self.estimate_bias, bias_semantics='uncalibrated_residual_bias_state' if self.estimate_bias else 'fixed_zero_by_design_not_measured_zero',
            last_imu=gyro_used, last_velocity=used.get('velocity'), latest_imu=self.controls[car].get('imu', {}).get('trace'),
            latest_velocity=velocity['trace'] if velocity else None, unobserved_motion_gap=bool(self.gap_counts[car]), gap_count=self.gap_counts[car])

    def snapshot(self, publication):
        if self.last_receive is not None and publication < self.last_receive:
            raise ValueError('publication before arrived input')
        result = {}
        for car in CARS:
            local = self.proto['frame_mode'] == 'source_odometry_motion_only'; prov = self.provenance(car)
            common = dict(frame_id=car + '/odom' if local else 'room', pose_reference_point='base_footprint', blocked_reasons=self.blocked[car], time_model_provided=not bool(self.blocked[car]))
            if self.blocked[car] or car not in self.times:
                result[car] = dict(common, pose=None, covariance=None, valid=False, fallback_status='BLOCKED' if self.blocked[car] else 'uninitialized', **prov)
                continue
            sl = self.sl(car); velocity = self.controls[car].get('velocity'); rate = self._rate(car)
            stale = rate is None or velocity is None or publication - min(c['trace']['sample_epoch_ns'] for c in (velocity, rate)) > self.params['max_control_hold_ns']
            measurement_age = publication - self.times[car]
            failed = car in self.failure
            rows = [v for (c, t), (stamp, v) in self.wall_geometry.items() if c == car and 0 <= publication - stamp <= self.config['geometry_window_ns']]
            rank = int(np.linalg.matrix_rank(np.asarray(rows), tol=1e-8)) if rows else 0
            degraded = self.proto['ranges_enabled'] and (len(rows) < 3 or rank < 2)
            finite = bool(np.isfinite(self.x[sl]).all() and np.isfinite(self.P[sl, sl]).all())
            status = 'numerical_failed_hold' if failed or not finite else 'control_gap_wait_hold' if stale else 'recovered_gap_uncertainty_retained' if self.gap_counts[car] else 'degraded_wall_geometry' if degraded else 'filtered_control_anchor_hold'
            source = self.last_used[car].get('velocity') or self.initial_records.get(car)
            result[car] = dict(common, pose=self.x[sl][:3].tolist(), covariance=self.P[sl, sl][:3, :3].tolist() if finite else None,
                valid=bool(not stale and not failed and finite and measurement_age <= self.config['max_publish_age_ns']), fallback_status=status,
                state_epoch_ns=self.times[car], source_header_epoch_ns=source['header_epoch_ns'] if source else None,
                source_receive_epoch_ns=source['receive_epoch_ns'] if source else None, source_record_index=source['record_index'] if source else None,
                receipt_age_ns=publication - source['receive_epoch_ns'] if source else None, measurement_age_ns=measurement_age,
                wall_xy_local_rank=rank, recent_wall_links=len(rows), geometry_degraded=bool(degraded),
                time_semantics='state at latest accepted physical integration/range epoch; held at publication; gaps explicitly reanchored', **prov)
        return result

    def full_trace(self):
        complete = len(self.times) == 2
        return dict(state_dimension=8, initialized_vehicle_ids=sorted(self.times), state_epoch_ns=dict(self.times),
            augmented_state_8d=self.x.tolist() if complete else None, augmented_covariance_8x8=self.P.tolist() if complete else None,
            partial_augmented={car: dict(state_4d=self.x[self.sl(car)].tolist(), covariance_4x4=self.P[self.sl(car), self.sl(car)].tolist()) if car in self.times else None for car in CARS},
            gap_count=dict(self.gap_counts), wall_only_initial_state_linearized_gramian={c: self.wall_gramian[c].tolist() for c in CARS},
            observability_caveat='wall-only finite-horizon local linearization; gaps/unknown slip invalidate global observability claims', covariance_semantics='engineering_noise_and_gap_model_not_calibrated_or_integrity_bound')


def make_filter(method, config):
    return LegacyAdapter(method, config) if mode_of(config) == 'legacy_odom_pose' else ImuFilter(method, config)
