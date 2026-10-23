#!/usr/bin/env python3
"""Receipt-ordered reference replay; archived batch factors, no ROS/IMU factors.

Growing prefixes are intentional. Virtual availability deadlines, immutable
published poses and final retrospective smoothing are separate products.
"""
from __future__ import annotations

import bisect
import collections
import copy
from dataclasses import dataclass
import hashlib
import importlib.util
import math
from pathlib import Path
import time
from typing import Any
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOLVER_PATH = ROOT / 'docs/field_tests/single_car_historical_L_20261021/results/evidence/new_graph.py'
SOLVER_SHA256 = 'cc8934e0ee34eabddd46ed09e0de1ca69e9a74b00e93147f7d99f5a04d77e903'


@dataclass(frozen=True)
class Event:
    received_s: float
    kind: str
    header_s: float | None = None
    value: Any = None


def load_solver():
    if hashlib.sha256(SOLVER_PATH.read_bytes()).hexdigest() != SOLVER_SHA256:
        raise ValueError('Archived solver source hash mismatch')
    spec = importlib.util.spec_from_file_location('single_car_archived_graph', SOLVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rotation(theta):
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, -s], [s, c]])


def wrap(theta):
    return math.atan2(math.sin(theta), math.cos(theta))


def antenna(pose, lever):
    return np.asarray(pose[:2]) + rotation(float(pose[2])) @ np.asarray(lever)


def predict(previous_pose, previous_local, local):
    delta = rotation(-previous_local[2]) @ (np.asarray(local[:2]) - previous_local[:2])
    xy = np.asarray(previous_pose[:2]) + rotation(previous_pose[2]) @ delta
    return np.r_[xy, previous_pose[2] + wrap(local[2] - previous_local[2])]


class SequentialReplay:
    """Data become visible only through ingest(). Equal-deadline receipts count.

    Closed bins remain immutable. finish() never advances beyond recorded EOF.
    The full arrived graph is re-solved from the inherited Odom initial guess.
    """
    def __init__(self, model, replay, solver=None):
        self.model, self.policy = copy.deepcopy(model), copy.deepcopy(replay)
        self.solver = load_solver() if solver is None else solver
        self.step = float(replay['keyframe_step_s'])
        self.half = float(replay['range_bin_half_width_s'])
        self.delay = float(replay['release_delay_s'])
        self.startup = float(replay['first_keyframe_margin_s'])
        self.minimum = int(replay['minimum_samples_per_link'])
        if not (self.step > 0 and 0 <= self.half < self.step / 2
                and self.delay >= self.half and self.minimum >= 1):
            raise ValueError('Invalid replay timing or bin policy')
        self.heading = math.radians(float(model['initial_heading_deg']))
        self.lever = np.asarray(model['base_to_antenna_body_xy_m'], dtype=float)
        self.start_xy = np.asarray(model['start_antenna_xyz_m'][:2], dtype=float)
        self.base_start = self.start_xy - rotation(self.heading) @ self.lever
        self.anchor_ids = set(model['anchors_xyz_m'])
        self.now = -math.inf
        self.next_state = None
        self.odom, self.ranges, self.times, self.local, self.observations = [], [], [], [], []
        self.first, self.latest_header = {}, {}
        self._records, self.closed_bins = [], []
        self.counters = collections.Counter()
        self.final_graph, self.final_graph_times = None, []
        self.worker_finish = 0.

    @property
    def records(self):
        return copy.deepcopy(self._records)

    def ingest(self, event):
        if not np.isfinite(event.received_s) or event.received_s < self.now:
            raise ValueError('Receipt time must be finite and nondecreasing')
        # A later event's payload is not exposed before earlier deadlines close.
        self._advance(event.received_s, inclusive=False)
        self.now = float(event.received_s)
        self.counters[event.kind + '_events'] += 1
        if event.kind not in ('odom', 'uwb'):
            return
        stamp = float(event.header_s)
        if not np.isfinite(stamp):
            raise ValueError('Invalid header timestamp')
        if event.kind in self.latest_header and stamp <= self.latest_header[event.kind]:
            raise ValueError('Nonincreasing ' + event.kind + ' header; no silent reordering')
        self.latest_header[event.kind] = stamp
        self.first.setdefault(event.kind, stamp)
        if event.kind == 'odom':
            value = np.asarray(event.value, dtype=float)
            if value.shape != (3,) or not np.isfinite(value).all():
                raise ValueError('Invalid Odom pose')
            if self.odom:
                value[2] = self.odom[-1][1][2] + wrap(value[2] - self.odom[-1][1][2])
            self.odom.append((stamp, value.copy(), self.now))
        else:
            values = {}
            for key, raw in event.value.items():
                if key not in self.anchor_ids:
                    continue
                if not np.isfinite(raw) or raw <= 0:
                    self.counters['invalid_raw_ranges'] += 1
                elif raw - self.model['range_bias_m'][key] <= 0:
                    self.counters['nonpositive_corrected_ranges'] += 1
                else:
                    values[key] = float(raw)
            self.ranges.append((stamp, values, self.now))
            for state_time, deadline in self.closed_bins:
                if abs(stamp - state_time) <= self.half and self.now > deadline:
                    self.counters['late_packets_for_closed_bins'] += 1
        if self.next_state is None and 'odom' in self.first and 'uwb' in self.first:
            self.next_state = float(math.ceil(max(self.first.values()) + self.startup))
            if self.next_state + self.delay < self.now:
                skipped = int(math.ceil((self.now - self.next_state - self.delay) / self.step))
                self.next_state += skipped * self.step
                self.counters['bootstrap_skipped_deadlines'] += skipped

    def finish(self):
        if np.isfinite(self.now):
            self._advance(self.now, inclusive=True)
        return self.records

    def _advance(self, until, inclusive):
        while self.next_state is not None:
            deadline = self.next_state + self.delay
            if not (deadline < until or (inclusive and deadline <= until)):
                break
            self._emit(self.next_state, deadline)
            self.next_state += self.step

    def _interpolate_odom(self, state_time):
        stamps = [r[0] for r in self.odom]
        index = bisect.bisect_left(stamps, state_time)
        if index < len(stamps) and stamps[index] == state_time:
            return self.odom[index][1].copy(), self.odom[index][2]
        if index == 0 or index == len(stamps):
            return None, None  # Do not silently extrapolate or take a future message.
        left, right = self.odom[index - 1], self.odom[index]
        fraction = (state_time - left[0]) / (right[0] - left[0])
        return left[1] + fraction * (right[1] - left[1]), max(left[2], right[2])

    def _emit(self, state_time, deadline):
        local, odom_receipt = self._interpolate_odom(state_time)
        self.closed_bins.append((state_time, deadline))
        if local is None:
            self.counters['missing_odom_bracket'] += 1
            self._records.append(dict(
                state_time_s=state_time, availability_cutoff_s=deadline,
                status='missing_odom_bracket', accepted_graph=False, pose=None,
                antenna_xy_m=None, solve_wall_s=0., graph_states=len(self.times),
                dependency_receipt_max_s=None))
            return
        grouped = collections.defaultdict(list)
        receipts = [odom_receipt]
        for stamp, values, received in self.ranges:
            if abs(stamp - state_time) <= self.half:
                for key, raw in values.items():
                    grouped[key].append(raw)
                if values:
                    receipts.append(received)
        observations = {key: float(np.median(values))
                        for key, values in sorted(grouped.items()) if len(values) >= self.minimum}
        supports = {key: len(grouped[key]) for key in sorted(self.anchor_ids)}
        self.times.append(float(state_time))
        self.local.append(local.copy())
        self.observations.append(observations)
        dependency_max = float(max(receipts))
        if dependency_max > deadline:
            raise AssertionError('A factor used a message received after its deadline')
        n = len(self.times)
        initial = self.solver.align_odom(
            np.asarray(self.local), list(self.base_start) + [self.model['antenna_height_m']], self.heading)
        previous = next((r for r in reversed(self._records) if r['pose'] is not None), None)
        pose = initial[-1].copy() if previous is None else predict(
            np.asarray(previous['pose']), np.asarray(previous['local_odom']), local)
        status, accepted, optimizer, candidate = 'predict_only_warmup', False, {}, None
        started = time.perf_counter()
        if n >= 3 and sum(map(len, self.observations)) >= n:
            try:
                graph, optimizer = self.solver.optimize_graph(
                    np.asarray(self.local), self.observations, self.model['anchors_xyz_m'],
                    self.model['range_bias_m'], self.model['antenna_height_m'],
                    self.base_start, self.heading, np.asarray(self.times),
                    self.model['graph_parameters'], tag_to_base_lever_xy_m=self.lever,
                    raise_on_failure=False)
                if np.isfinite(graph).all():
                    candidate = graph[-1].tolist()
                accepted = bool(optimizer['optimizer_success'] and candidate is not None)
                if accepted:
                    pose = graph[-1].copy()
                    self.final_graph, self.final_graph_times = graph.copy(), list(self.times)
                    status = 'graph'
                else:
                    status = 'predict_only_solver_failed'
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
                status = 'predict_only_solver_error'
                optimizer = {'error': type(error).__name__ + ': ' + str(error)}
        elif n >= 3:
            status = 'predict_only_insufficient_ranges'
        duration = time.perf_counter() - started
        worker_start = max(deadline, self.worker_finish)
        self.worker_finish = worker_start + duration
        self._records.append(dict(
            state_time_s=state_time, availability_cutoff_s=deadline, status=status,
            accepted_graph=accepted, pose=pose.tolist(),
            antenna_xy_m=antenna(pose, self.lever).tolist(), local_odom=local.tolist(),
            aligned_odom_pose=initial[-1].tolist(),
            aligned_odom_antenna_xy_m=antenna(initial[-1], self.lever).tolist(),
            range_medians_m=observations, range_sample_counts=supports, graph_states=n,
            dependency_receipt_max_s=dependency_max, solve_wall_s=duration,
            estimated_worker_start_s=worker_start, estimated_worker_finish_s=self.worker_finish,
            estimated_worker_queue_s=worker_start-deadline, candidate_pose=candidate,
            optimizer=copy.deepcopy(optimizer)))


def bag_events(path, diagnostics=None):
    """Yield recorded receipt order using message definitions embedded in ROS1 bags."""
    from rosbags.highlevel import AnyReader
    diag = {} if diagnostics is None else diagnostics
    counts, timing = collections.Counter(), collections.defaultdict(list)
    duplicates, origin = 0, None
    with AnyReader([Path(path)]) as reader:
        for connection, receipt_ns, raw in reader.messages():
            if origin is None:
                origin = receipt_ns
            received = (receipt_ns - origin) / 1e9
            msg = reader.deserialize(raw, connection.msgtype)
            topic = connection.topic
            counts[topic] += 1
            stamp = None
            if hasattr(msg, 'header'):
                header_ns = int(msg.header.stamp.sec)*10**9 + int(msg.header.stamp.nanosec)
                if header_ns <= 0:
                    raise ValueError('Nonpositive sensor header in ' + topic)
                stamp = (header_ns - origin) / 1e9
                timing[topic].append((stamp, (receipt_ns-header_ns)/1e9))
            if topic == '/car2/odom':
                if msg.header.frame_id != 'car2/odom_combined' or msg.child_frame_id != 'base_footprint':
                    raise ValueError('Unexpected Odom frames; document any model change explicitly')
                p, q = msg.pose.pose.position, msg.pose.pose.orientation
                norm = math.sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w)
                if not np.isfinite(norm) or not .5 <= norm <= 1.5:
                    raise ValueError('Invalid Odom quaternion')
                x, y, z, w = q.x/norm, q.y/norm, q.z/norm, q.w/norm
                yaw = math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
                yield Event(received, 'odom', stamp, (p.x, p.y, yaw))
            elif topic == '/car2/uwb/ranges' and msg.tag_id == 'node_0':
                groups = collections.defaultdict(list)
                for entry in msg.ranges:
                    groups[entry.anchor_id].append(float(entry.range))
                duplicates += sum(len(values) != 1 for values in groups.values())
                values = {key: value[0] for key, value in groups.items() if len(value) == 1}
                yield Event(received, 'uwb', stamp, values)
            elif topic == '/car2/imu':
                yield Event(received, 'imu')  # No IMU measurement enters the graph.
            else:
                yield Event(received, 'other')
    diag.update(dict(
        origin_bag_receipt_ns=origin, topic_counts=dict(counts),
        duplicate_uwb_id_groups=duplicates, imu_factors=0,
        timing={topic: {
            'header_nonincreasing_steps': int(np.sum(np.diff(np.asarray(rows)[:, 0]) <= 0)),
            'receipt_minus_header_s': {key: float(value) for key, value in zip(
                ['min', 'median', 'p95', 'p99', 'max'],
                np.percentile(np.asarray(rows)[:, 1], [0, 50, 95, 99, 100]))}}
            for topic, rows in timing.items()},
        clock_note='Receipt and source-header clocks retained without fitted correction; their difference is not a measured network latency.'))
