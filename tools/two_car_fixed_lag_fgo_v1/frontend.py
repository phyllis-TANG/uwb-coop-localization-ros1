"""F0 receive-prefix binning; joint closure never exposes a future payload."""
import bisect
import collections
import copy
import math
import time
import numpy as np
from legacy import CARS, Event, FixedLagReplay, antenna
from graph import WindowGraph


class Binner(FixedLagReplay):
    """Reuse original ingest/interpolate/prune, replace only graph/output sink."""
    def _emit(self, stamp, deadline):
        self.last_closed_state = stamp
        local, receipt = self._interpolate(stamp)
        grouped = collections.defaultdict(list); receipts = [] if receipt is None else [receipt]
        for header, values, received in self.ranges:
            if abs(header-stamp) <= self.half:
                for key, raw in values.items(): grouped[key].append(raw)
                if values: receipts.append(received)
        observations = {k: float(np.median(v)) for k, v in sorted(grouped.items()) if len(v) >= self.minimum}
        if receipts: self.dependency_max = max(self.dependency_max, max(receipts))
        if self.dependency_max > deadline: raise AssertionError('Future F0 dependency')
        row = dict(state_time_s=stamp, availability_cutoff_s=deadline,
                   local_odom=None if local is None else local.tolist(), observations=observations,
                   sample_counts={k: len(grouped[k]) for k in sorted(self.model['anchors_xyz_m'])},
                   dependency_receipt_max_s=None if not np.isfinite(self.dependency_max) else self.dependency_max)
        if local is None: self.counters['missing_odom_bracket'] += 1
        self._prune(stamp+self.step)
        row['sensor_buffer_counts'] = dict(odom=len(self.odom), uwb=len(self.ranges))
        self.output_count += 1; self.on_output(row)


class JointReplay:
    def __init__(self, config, arm, on_output, origin_ns):
        if arm not in ('D0', 'D1'): raise ValueError('Unknown arm')
        self.config = copy.deepcopy(config); self.arm = arm; self.origin_ns = origin_ns
        self.graph = WindowGraph(config, arm == 'D1'); self.on_output = on_output
        self.pending = {}; self.peers = {c: [] for c in CARS}; self.counters = collections.Counter()
        self.binners = {c: Binner(config['models'][c], config['replay'],
            lambda row, c=c: self._bin(c, row), lag_s=config['fixed_lag_s'],
            max_nfev=config['optimizer']['max_nfev'],
            max_sensor_samples=config['frontend']['max_sensor_samples_per_stream']) for c in CARS}
        self.now_ns = None; self.case_id = None; self.last_index = None
        self.last_headers = {}; self.recent_ids = {c: collections.OrderedDict() for c in CARS}
        self.worker_finish = 0.; self.output_count = 0; self.peer_peak = 0; self.pending_peak = 0

    def _bin(self, car, row):
        stamp = row['state_time_s']; self.pending.setdefault(stamp, {})[car] = row
        self.pending_peak = max(self.pending_peak, len(self.pending))
        if len(self.pending) > 2: raise ValueError('BLOCKED: unmatched two-car keyframe grids')
        if len(self.pending[stamp]) == 2:
            bins = self.pending.pop(stamp); self._emit(stamp, bins)

    def ingest(self, raw):
        # Reject label leakage at any nesting depth.
        def check_labels(value):
            if isinstance(value, dict):
                if {'truth', 'fault_label', 'true_pose', 'true_bias', 'fault_labels'} & value.keys():
                    raise ValueError('Truth/fault labels prohibited in estimator input')
                for v in value.values(): check_labels(v)
            elif isinstance(value, list):
                for v in value: check_labels(v)
        check_labels(raw)
        for k in ('receive_epoch_ns', 'record_index'):
            if type(raw.get(k)) is not int: raise ValueError('Exact integer required: ' + k)
        ns = raw['receive_epoch_ns']; index = raw['record_index']; kind = raw['kind']
        if self.now_ns is not None and (ns < self.now_ns or index <= self.last_index):
            raise ValueError('Nonmonotonic receive order or record identity')
        if not isinstance(raw.get('case_id'), str) or not raw['case_id'].startswith('synthetic_'):
            raise ValueError('BLOCKED: only explicitly synthetic cases accepted; field/holdouts excluded')
        if self.case_id not in (None, raw['case_id']): raise ValueError('One identified case required')
        self.case_id = raw['case_id']; self.now_ns = ns; self.last_index = index
        if kind not in ('odom', 'uwb', 'imu', 'clock', 'other'): raise ValueError('Unsupported event kind')
        car = raw.get('vehicle_id'); sensor = kind in ('odom', 'uwb', 'imu')
        if sensor:
            if car not in CARS or type(raw.get('header_epoch_ns')) is not int: raise ValueError('Missing car/header')
            if not raw.get('source_file_sha256') or not raw.get('topic'): raise ValueError('Missing source identity')
        received = (ns-self.origin_ns)/1e9
        header = (raw['header_epoch_ns']-self.origin_ns)/1e9 if sensor else None
        ingest = sensor and kind in ('odom', 'uwb')
        reason = 'accepted' if ingest else 'diagnostic_ignored'
        if kind == 'uwb':
            if raw.get('representation') != 'bridge': ingest = False; reason = 'noncanonical_raw_ignored'
            else:
                identity = raw.get('source_observation_id')
                if not identity: raise ValueError('Missing canonical source_observation_id')
                if identity in self.recent_ids[car] or header == self.last_headers.get((car, kind)):
                    ingest = False; reason = 'duplicate_canonical_ignored'
                else:
                    self.recent_ids[car][identity] = header
                    if len(self.recent_ids[car]) > self.config['frontend']['max_sensor_samples_per_stream']:
                        self.recent_ids[car].popitem(last=False)
        # Advancing ALL clocks first prevents one vehicle from seeing the current payload early.
        for c in CARS: self.binners[c]._advance(received, inclusive=False)
        if ingest:
            if (car, kind) in self.last_headers and header <= self.last_headers[(car, kind)]:
                raise ValueError('Nonincreasing sensor header; no offline reorder')
            self.last_headers[(car, kind)] = header
        for c in CARS:
            event = Event(received, kind, header,
                raw['value']['pose'] if kind == 'odom' and ingest else raw.get('value')) if c == car and ingest else Event(received, 'clock')
            self.binners[c].ingest(event)
        if kind == 'uwb' and ingest:
            peer_key = 'node_0' if car == 'car1' else 'node_1'
            value = raw['value'].get(peer_key)
            if value is not None and isinstance(value, (int, float)) and np.isfinite(value) and value > 0:
                self.peers[car].append(dict(header_s=header, received_s=received, range_m=float(value),
                    identity={k: raw.get(k) for k in ('record_index', 'source_file_sha256', 'topic',
                        'header_epoch_ns', 'receive_epoch_ns', 'source_observation_id')}))
            else: self.counters['missing_or_invalid_peer_'+car] += 1
        for c in CARS:
            next_state = self.binners[c].next_state
            if next_state is not None:
                self.peers[c] = [p for p in self.peers[c] if p['header_s'] >= next_state-self.binners[c].half]
            if len(self.peers[c]) > self.config['frontend']['max_sensor_samples_per_stream']:
                raise BufferError('peer source buffer capacity exceeded')
            self.peer_peak = max(self.peer_peak, len(self.peers[c]))
        a, b = [self.binners[c].first_state for c in CARS]
        if a is not None and b is not None and abs(a-b) > 1e-9:
            raise ValueError('BLOCKED: first keyframe grids differ')
        self.counters[reason] += 1
        return reason

    def _emit(self, stamp, bins):
        started = time.perf_counter(); deadline = stamp+self.config['replay']['release_delay_s']
        half = self.config['replay']['range_bin_half_width_s']
        available = {c: [p for p in self.peers[c] if abs(p['header_s']-stamp) <= half] for c in CARS}
        for values in available.values():
            if any(p['received_s'] > deadline for p in values): raise AssertionError('Future peer dependency')
        minimum = self.config['peer']['minimum_samples']
        medians = {c: float(np.median([p['range_m'] for p in available[c]])) if len(available[c]) >= minimum else None for c in CARS}
        receipts = [b['dependency_receipt_max_s'] for b in bins.values() if b['dependency_receipt_max_s'] is not None]
        if self.arm == 'D1': receipts += [p['received_s'] for p in available['car1']]
        dependency = max(receipts) if receipts else None
        if dependency is not None and dependency > deadline: raise AssertionError('Future joint dependency')
        if any(b['local_odom'] is None for b in bins.values()):
            result = dict(pose=None, prediction_pose=None, accepted_graph=False, status='missing_odom_bracket',
                graph_states=len(self.graph.times), marginalizations=self.graph.marginalizations,
                solve_wall_s=0., marginal_wall_s=0., marginalization_details=[])
        else:
            result = self.graph.update(stamp, [bins[c]['local_odom'] for c in CARS],
                {c: bins[c]['observations'] for c in CARS}, medians['car1'])
        elapsed = time.perf_counter()-started; worker_start = max(deadline, self.worker_finish)
        self.worker_finish = worker_start+elapsed
        record = dict(result, schema_version=1, method_id=self.arm, state_time_s=stamp,
            state_epoch_ns=self.origin_ns+round(stamp*1e9), availability_cutoff_s=deadline,
            availability_cutoff_epoch_ns=self.origin_ns+round(deadline*1e9), timing_mode='virtual',
            bins=bins, peer_median_m=medians['car1'], reverse_peer_median_m=medians['car2'],
            peer_sample_count=len(available['car1']), reverse_peer_sample_count=len(available['car2']),
            peer_factor_used=bool(self.arm == 'D1' and medians['car1'] is not None and stamp in self.graph.times),
            peer_dependencies=available['car1'], reverse_diagnostic_dependencies=available['car2'],
            dependency_receipt_max_s=dependency, update_wall_s=elapsed,
            estimated_worker_finish_s=self.worker_finish, estimated_worker_queue_s=worker_start-deadline,
            scalar_variables=6*result['graph_states'], snapshot=self.graph.snapshot())
        self.output_count += 1; self.on_output(copy.deepcopy(record))

    def finish(self):
        for c in CARS: self.binners[c].finish()
        if self.pending: raise ValueError('BLOCKED: unmatched final keyframe outputs')
