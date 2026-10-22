#!/usr/bin/env python3
"""Frozen three-arm comparison of receipt-ordered single-car localization."""
from __future__ import annotations

import argparse
import collections
import csv
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

import numpy as np
import scipy

from run_single_car_sequential_baseline import checksum, endpoint, write_csv, write_json
from single_car_fixed_lag import FixedLagReplay
from single_car_sequential_replay import (
    ROOT, SOLVER_PATH, Event, SequentialReplay, antenna, bag_events, load_solver, predict, wrap)

DEFAULT_PROTOCOL = ROOT/'docs/field_tests/single_car_fixed_lag_20261022/protocol.json'
ARMS = ('legacy_cold_full_history', 'analytic_warm_full_history', 'analytic_warm_fixed_20s')


class TimedLegacy(SequentialReplay):
    """Instrument the untouched reference without changing factors or decisions."""
    def _emit(self, stamp, deadline):
        started = time.perf_counter()
        super()._emit(stamp, deadline)
        row = self._records[-1]
        row['update_wall_s'] = time.perf_counter()-started
        row['marginal_wall_s'] = 0.
        row['marginalizations'] = 0
        row['graph_time_span_s'] = self.times[-1]-self.times[0] if self.times else 0.
        if row['pose'] is not None:
            previous = next((r for r in reversed(self._records[:-1]) if r['pose'] is not None), None)
            prediction = row['aligned_odom_pose'] if previous is None else predict(
                np.asarray(previous['pose']), np.asarray(previous['local_odom']),
                np.asarray(row['local_odom']))
            row['position_correction_m'] = float(np.linalg.norm(np.asarray(row['pose'][:2])-prediction[:2]))
            row['yaw_correction_deg'] = math.degrees(abs(wrap(row['pose'][2]-prediction[2])))


def distribution(values, scale=1.):
    values = np.asarray(values, dtype=float)*scale
    if not len(values):
        return dict(samples=0, min=None, median=None, p95=None, max=None)
    return dict(samples=len(values), **{key: float(value) for key, value in zip(
        ['min', 'median', 'p95', 'max'], np.percentile(values, [0, 50, 95, 100]))})


def annotate_queue(rows):
    """Uniform virtual worker model using measured complete update durations."""
    finish = 0.
    for row in rows:
        start = max(row['availability_cutoff_s'], finish)
        finish = start+row['update_wall_s']
        row.update(estimated_worker_start_s=start, estimated_worker_finish_s=finish,
                   estimated_worker_queue_s=start-row['availability_cutoff_s'])


def published_csv(path, rows):
    output = []
    for r in rows:
        if r['pose'] is None:
            continue
        output.append(dict(
            state_time_s=r['state_time_s'], availability_cutoff_s=r['availability_cutoff_s'],
            status=r['status'], accepted_graph=r['accepted_graph'],
            base_x_m=r['pose'][0], base_y_m=r['pose'][1], yaw_rad=r['pose'][2],
            antenna_x_m=r['antenna_xy_m'][0], antenna_y_m=r['antenna_xy_m'][1],
            aligned_odom_antenna_x_m=r['aligned_odom_antenna_xy_m'][0],
            aligned_odom_antenna_y_m=r['aligned_odom_antenna_xy_m'][1],
            graph_states=r['graph_states'], graph_time_span_s=r['graph_time_span_s'],
            marginalizations=r['marginalizations'], solve_wall_s=r['solve_wall_s'],
            marginal_wall_s=r['marginal_wall_s'], update_wall_s=r['update_wall_s'],
            position_correction_m=r['position_correction_m'], yaw_correction_deg=r['yaw_correction_deg'],
            optimizer_nfev=r['optimizer'].get('optimizer_nfev'),
            dependency_receipt_max_s=r['dependency_receipt_max_s'],
            estimated_worker_queue_s=r['estimated_worker_queue_s'],
            range_medians_json=json.dumps(r['range_medians_m'], sort_keys=True),
            sample_counts_json=json.dumps(r['range_sample_counts'], sort_keys=True)))
    if not output:
        raise AssertionError('No valid publications')
    write_csv(path, output, list(output[0]))


def compare_frontend(reference, actual):
    if len(reference) != len(actual):
        raise AssertionError('Frontend output counts differ')
    maximum = 0.
    for a, b in zip(reference, actual):
        for key in ('state_time_s', 'availability_cutoff_s', 'range_medians_m', 'range_sample_counts'):
            if a.get(key) != b.get(key):
                raise AssertionError('Frontend inputs differ: '+key)
        if (a['pose'] is None) != (b['pose'] is None):
            raise AssertionError('Odom availability differs')
        if a['pose'] is not None:
            maximum = max(maximum, float(np.max(np.abs(np.asarray(a['local_odom'])-b['local_odom']))))
            if not np.allclose(a['aligned_odom_antenna_xy_m'], b['aligned_odom_antenna_xy_m'], atol=1e-12, rtol=0):
                raise AssertionError('Aligned Odom reference differs')
    if maximum > 1e-12:
        raise AssertionError('Interpolated Odom differs')
    return dict(passed=True, outputs_checked=len(actual), max_local_component_delta=maximum)


def compare_estimates(reference, actual):
    deltas = [float(np.linalg.norm(np.asarray(a['antenna_xy_m'])-b['antenna_xy_m']))
              for a, b in zip(reference, actual) if a['pose'] is not None and b['pose'] is not None]
    return distribution(deltas)


def prefix_guard(bag, protocol, complete):
    cutoff = protocol['evaluation_only']['prefix_guard_cutoff_s']
    rows = []
    replay = FixedLagReplay(protocol['model'], protocol['replay'], rows.append,
                            lag_s=protocol['fixed_lag_s'], max_nfev=protocol['optimizer']['max_nfev'],
                            max_sensor_samples=protocol['frontend']['max_sensor_samples_per_stream'])
    for event in bag_events(bag):
        if event.received_s > cutoff:
            break
        replay.ingest(event)
    replay.ingest(Event(cutoff, 'clock'))
    replay.finish()
    expected = [r for r in complete if r['availability_cutoff_s'] <= cutoff]
    compare_frontend(expected, rows)
    maximum = 0.
    for old, row in zip(expected, rows):
        for key in ('status', 'accepted_graph', 'marginalizations', 'graph_states'):
            if old[key] != row[key]:
                raise AssertionError('Future truncation changed past decisions: '+key)
        if row['pose'] is not None:
            maximum = max(maximum, float(np.max(np.abs(np.asarray(row['pose'])-old['pose']))))
    if maximum > protocol['evaluation_only']['prefix_invariance_tolerance']:
        raise AssertionError('Future truncation changed past estimates')
    if replay.graph.marginalizations < 1:
        raise AssertionError('Prefix guard did not exercise marginalization')
    return dict(passed=True, cutoff_s=cutoff, outputs_checked=len(rows),
                marginalizations=replay.graph.marginalizations, max_pose_component_delta=maximum)


def run_arm(bag, protocol, arm, out, case):
    print(f"Starting {case['id']} / {arm}", flush=True)
    rows, diagnostics = [], {}
    if arm == ARMS[0]:
        replay = TimedLegacy(protocol['model'], protocol['replay'], load_solver())
    else:
        replay = FixedLagReplay(protocol['model'], protocol['replay'], rows.append,
            lag_s=None if arm == ARMS[1] else protocol['fixed_lag_s'],
            max_nfev=protocol['optimizer']['max_nfev'],
            max_sensor_samples=protocol['frontend']['max_sensor_samples_per_stream'])
    started = time.perf_counter()
    for event in bag_events(bag, diagnostics):
        replay.ingest(event)
    returned = replay.finish()
    if arm == ARMS[0]:
        rows = returned
        active_times, active_states = replay.final_graph_times, replay.final_graph
        peak_solve = peak_transient = len(replay.times)
        sensor_peaks = dict(odom=len(replay.odom), uwb=len(replay.ranges))
        prior = None
    else:
        graph = replay.graph
        active_times, active_states = graph.times, np.asarray(graph.states)
        peak_solve, peak_transient = graph.peak_solve_states, graph.peak_transient_states
        sensor_peaks = replay.sensor_peaks
        prior = dict(point=graph.prior.point.tolist(), matrix=graph.prior.matrix.tolist(),
                     offset=graph.prior.offset.tolist(), discarded_constant=graph.eliminated_constant)
    replay_wall = time.perf_counter()-started
    annotate_queue(rows)
    write_json(out/'updates.json', rows)
    write_json(out/'input_diagnostics.json', diagnostics)
    published_csv(out/'published.csv', rows)
    active = []
    for stamp, pose in zip(active_times, active_states):
        xy = antenna(pose, protocol['model']['base_to_antenna_body_xy_m'])
        active.append(dict(state_time_s=float(stamp), base_x_m=float(pose[0]), base_y_m=float(pose[1]),
                           yaw_rad=float(pose[2]), antenna_x_m=float(xy[0]), antenna_y_m=float(xy[1])))
    write_csv(out/'final_active_states.csv', active, list(active[0]))
    write_json(out/'final_boundary_prior.json', prior)
    valid = [r for r in rows if r['pose'] is not None]
    solved = [r for r in valid if r['graph_states'] >= 3]
    accepted = [r for r in valid if r['accepted_graph']]
    # Initialization is a distinct correction; regular corrections start later.
    regular = accepted[1:]
    dependencies_ok = all(r['dependency_receipt_max_s'] is None or
                          r['dependency_receipt_max_s'] <= r['availability_cutoff_s'] for r in rows)
    if not dependencies_ok:
        raise AssertionError('A published estimate used a future receipt')
    times = [r['state_time_s'] for r in valid]
    result = dict(
        records=len(rows), graph_outputs=len(accepted),
        status_counts=dict(collections.Counter(r['status'] for r in rows)),
        solver_failures=sum(r['status'].startswith('predict_only_solver_') for r in rows),
        counters=dict(replay.counters), peak_solve_states=peak_solve,
        peak_transient_states=peak_transient, sensor_buffer_peaks=sensor_peaks,
        final_retained_states=len(active), marginalizations=rows[-1]['marginalizations'],
        replay_wall_s=replay_wall,
        solve_wall_ms=distribution([r['solve_wall_s'] for r in solved], 1000),
        marginal_wall_ms=distribution([r['marginal_wall_s'] for r in solved], 1000),
        complete_update_wall_ms=distribution([r['update_wall_s'] for r in solved], 1000),
        complete_updates_over_1s=sum(r['update_wall_s'] > 1. for r in rows),
        estimated_worker_queue_max_s=max(r['estimated_worker_queue_s'] for r in rows),
        initialization_correction_m=accepted[0]['position_correction_m'] if accepted else None,
        regular_position_correction_m=distribution([r['position_correction_m'] for r in regular]),
        regular_yaw_correction_deg=distribution([r['yaw_correction_deg'] for r in regular]),
        published_endpoint=endpoint(times, [r['antenna_xy_m'] for r in valid],
            case['evaluation_window_s'], case['end_antenna_xyz_m'], [r['accepted_graph'] for r in valid]),
        aligned_odom_endpoint=endpoint(times, [r['aligned_odom_antenna_xy_m'] for r in valid],
            case['evaluation_window_s'], case['end_antenna_xyz_m']),
        verification=dict(all_dependencies_available=dependencies_ok))
    write_json(out/'comparison.json', result)
    print(json.dumps(dict(case=case['id'], arm=arm, endpoint_m=result['published_endpoint']['difference_m'],
                         update_max_ms=result['complete_update_wall_ms']['max'],
                         failures=result['solver_failures'], states=peak_solve), ensure_ascii=False), flush=True)
    return rows, result


def run_case(case, protocol, out):
    bag = ROOT/case['bag']
    if checksum(bag) != case['sha256']:
        raise ValueError('Dataset SHA256 mismatch: '+case['bag'])
    all_rows, results = {}, {}
    for arm in ARMS:
        target = out/arm
        target.mkdir()
        all_rows[arm], results[arm] = run_arm(bag, protocol, arm, target, case)
    legacy, control, fixed = (all_rows[arm] for arm in ARMS)
    frontend = {arm: compare_frontend(legacy, all_rows[arm]) for arm in ARMS[1:]}
    archived = ROOT/'docs/field_tests/single_car_sequential_replay_20261022/results'/case['id']/'published.csv'
    with archived.open(newline='') as stream:
        old = list(csv.DictReader(stream))
    if len(old) != len(legacy):
        raise AssertionError('Archived baseline publication count differs')
    for row, before in zip(legacy, old):
        if row['state_time_s'] != float(before['state_time_s']) or row['status'] != before['status']:
            raise AssertionError('Archived baseline time grid or decisions differ')
    old_delta = max(float(np.linalg.norm(np.asarray(row['antenna_xy_m'])-
                    [float(before['antenna_x_m']), float(before['antenna_y_m'])]))
                    for row, before in zip(legacy, old))
    if old_delta > protocol['evaluation_only']['baseline_reproduction_tolerance_m']:
        raise AssertionError('Untouched baseline failed numerical reproduction')
    before_margin = [(a, b) for a, b in zip(control, fixed) if b['marginalizations'] == 0]
    before_delta = max(float(np.max(np.abs(np.asarray(a['pose'])-b['pose'])))
                       for a, b in before_margin if a['pose'] is not None)
    if before_delta > protocol['evaluation_only']['before_first_marginalization_tolerance']:
        raise AssertionError('Fixed and control differ before any marginalization')
    checks = dict(frontend_equivalence=frontend,
                  archived_baseline_max_antenna_delta_m=old_delta,
                  before_first_marginalization=dict(outputs_checked=len(before_margin),
                      max_pose_component_delta=before_delta, passed=True),
                  fixed_window_future_truncation=prefix_guard(bag, protocol, fixed))
    for arm in ARMS[1:]:
        checks[arm+'_vs_legacy_antenna_displacement_m'] = compare_estimates(legacy, all_rows[arm])
    checks['fixed_vs_warm_full_antenna_displacement_m'] = compare_estimates(control, fixed)
    # This is a numerical convergence diagnostic on the SAME full objective.
    with (out/ARMS[0]/'final_active_states.csv').open(newline='') as stream:
        a = list(csv.DictReader(stream))
    with (out/ARMS[1]/'final_active_states.csv').open(newline='') as stream:
        b = list(csv.DictReader(stream))
    checks['warm_full_vs_legacy_final_state_max_component_delta'] = max(
        abs(float(x[key])-float(y[key])) for x, y in zip(a, b) for key in ['base_x_m', 'base_y_m', 'yaw_rad'])
    checks['warm_full_final_cost'] = control[-1]['optimizer']['optimizer_cost']
    checks['legacy_final_cost'] = legacy[-1]['optimizer']['cost']
    result = dict(case=case['id'], role=case['role'], bag=case['bag'], sha256=case['sha256'],
                  evaluation_window_s=case['evaluation_window_s'], arms=results, verification=checks)
    write_json(out/'comparison.json', result)
    return result


def report(results):
    lines = ['# 单车固定窗口顺序回放结果', '',
        '冻结 20 s 窗口、模型权重、P1 测距修正、起点和原终点评价窗；未加入独立 IMU 因子。', '',
        '| 包 | 方法 | 发布终点差/cm | 求解 p95/ms | 完整更新最大/ms | 求解状态上限 | 常规修正最大/cm |',
        '|---|---|---:|---:|---:|---:|---:|']
    labels = ['原版全历史冷启动', '全历史解析导数＋热启动', '20 s 固定窗口＋边缘化']
    for case in results:
        for arm, label in zip(ARMS, labels):
            r = case['arms'][arm]
            value = r['published_endpoint']['difference_m']
            text = '不可用' if value is None else f'{100*value:.3f}'
            lines.append(f"| {case['case']} | {label} | {text} | {r['solve_wall_ms']['p95']:.3f} | "
                         f"{r['complete_update_wall_ms']['max']:.3f} | {r['peak_solve_states']} | "
                         f"{100*r['regular_position_correction_m']['max']:.3f} |")
    lines += ['', '常规修正 = 本次发布位置与上次发布位置经 Odom 推进后的差；首次图初始化单独统计。',
        '它衡量更新连续性，不能充当真实轨迹误差。终点差是既有停止窗内成功图输出的中位数与手工参考点之差。',
        '旧状态因子压缩为线性化高斯先验；保留仿射残差，不重复计入窗口内观测。历史非线性不再重线性化。',
        '保留完整历史的解析导数＋热启动对照用于区分求解器改动和窗口截断的影响。',
        '21 个求解状态覆盖含两端点的 20 s 窗口；加入新状态后、消元前短暂保留 22 个状态。',
        '完整更新耗时含统计窗构建、求解、边缘化和缓存裁剪，不含外部日志回调、逐消息输入成本和 ROS 通信。',
        '耗时来自同一机器、单线程、串行未限速回放；队列为虚拟 1 Hz 工作者估计。1 s 数据等待仍保留。',
        '状态数、样本容量和迭代预算有界，不等于操作系统上的硬实时截止期保证。',
        '估计器缓存有界；离线 bag 读取诊断和外部日志档案会随文件长度增长。',
        '没有连续真值；两个包已用于开发；几何中心与 Odom 参考点是否一致仍待实车核实。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dependency-path', type=Path, help='Optional directory containing rosbags; appended after NumPy/SciPy imports')
    args = parser.parse_args()
    if args.dependency_path:
        sys.path.append(str(args.dependency_path.resolve()))
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS'):
        if os.environ.get(name) != '1':
            raise ValueError(name+' must be 1 for this frozen comparison')
    protocol = json.loads(args.protocol.read_text())
    if tuple(protocol['arms']) != ARMS:
        raise ValueError('Unexpected comparison arms')
    if checksum(ROOT/protocol['baseline_protocol']) != protocol['baseline_protocol_sha256']:
        raise ValueError('Frozen baseline protocol changed')
    sources = [Path(__file__), ROOT/'tools/single_car_fixed_lag.py',
               ROOT/'tools/single_car_sequential_replay.py', ROOT/'tools/run_single_car_sequential_baseline.py',
               ROOT/'tools/test_single_car_fixed_lag.py', ROOT/'tools/test_single_car_sequential_replay.py',
               ROOT/'tools/plot_single_car_fixed_lag.py', SOLVER_PATH]
    before = {str(p.relative_to(ROOT)): checksum(p) for p in sources}
    protocol_hash = checksum(args.protocol)
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/'protocol.json', protocol)
    results = []
    for case in protocol['cases']:
        target = args.output/case['id']
        target.mkdir()
        results.append(run_case(case, protocol, target))
    after = {str(p.relative_to(ROOT)): checksum(p) for p in sources}
    if before != after or protocol_hash != checksum(args.protocol):
        raise AssertionError('Source or protocol changed during the experiment')
    write_json(args.output/'input_manifest.json', dict(
        base_main_sha=protocol['base_main_sha'], python=platform.python_version(),
        numpy=np.__version__, scipy=scipy.__version__, rosbags=importlib.metadata.version('rosbags'),
        platform=platform.platform(), thread_environment={key: os.environ.get(key) for key in
            ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS']}, protocol_sha256=protocol_hash,
        source_files=before, data_files={case['bag']: case['sha256'] for case in protocol['cases']},
        source_and_protocol_unchanged_during_run=True))
    write_json(args.output/'summary.json', dict(cases=results, limitations=protocol['assumptions'],
        continuous_trajectory_truth=False, imu_factors=0, live_or_hard_real_time_accepted=False))
    (args.output/'REPORT.md').write_text(report(results))
    print('Completed all three arms and causality/reproduction checks', flush=True)


if __name__ == '__main__':
    main()
