#!/usr/bin/env python3
"""Run frozen two-bag sequential reference and independent after-EOF checks."""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import subprocess
import time
import numpy as np
import scipy
from single_car_sequential_replay import (
    ROOT, Event, SequentialReplay, antenna, bag_events, load_solver, rotation)

DEFAULT_PROTOCOL = ROOT / 'docs/field_tests/single_car_sequential_replay_20261022/protocol.json'


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def write_csv(path, rows, fields):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def batch_inputs(path, model, policy):
    """Independent, deliberately noncausal baseline built only after replay."""
    odom, ranges = [], []
    for event in bag_events(path):
        if event.kind == 'odom':
            odom.append([event.header_s, *event.value])
        elif event.kind == 'uwb':
            ranges.append((event.header_s, event.value))
    odom = np.asarray(odom, dtype=float)
    odom[:, 3] = np.unwrap(odom[:, 3])
    low = max(odom[0, 0], ranges[0][0])
    high = min(odom[-1, 0], ranges[-1][0])
    times = np.arange(math.ceil(low+policy['first_keyframe_margin_s']),
                      math.floor(high), policy['keyframe_step_s'])
    local = np.column_stack([np.interp(times, odom[:, 0], odom[:, j]) for j in [1, 2, 3]])
    observations = []
    for t in times:
        row = {}
        for key in sorted(model['anchors_xyz_m']):
            values = [raw[key] for stamp, raw in ranges
                      if abs(stamp-t) <= policy['range_bin_half_width_s'] and key in raw
                      and np.isfinite(raw[key]) and raw[key] > 0
                      and raw[key]-model['range_bias_m'][key] > 0]
            if len(values) >= policy['minimum_samples_per_link']:
                row[key] = float(np.median(values))
        observations.append(row)
    return times, local, observations


def endpoint(times, xy, window, target, accepted=None):
    mask = (np.asarray(times) >= window[0]) & (np.asarray(times) < window[1])
    expected = int(mask.sum())
    if accepted is not None:
        mask &= np.asarray(accepted, dtype=bool)
    if not mask.any():
        return dict(samples=0, window_keyframes=expected, difference_m=None)
    values = np.asarray(xy)[mask]
    median = np.median(values, axis=0)
    return dict(samples=len(values), window_keyframes=expected,
                median_antenna_xy_m=median.tolist(),
                difference_m=float(np.linalg.norm(median-np.asarray(target[:2]))),
                first_last_displacement_m=float(np.linalg.norm(values[-1]-values[0])))


def check_prefix(path, protocol, solver, complete):
    cutoff = protocol['evaluation_only']['prefix_guard_cutoff_s']
    replay = SequentialReplay(protocol['model'], protocol['replay'], solver)
    for event in bag_events(path):
        if event.received_s > cutoff:
            break
        replay.ingest(event)
    replay.ingest(Event(cutoff, 'clock'))
    rows = replay.finish()
    expected = [r for r in complete if r['availability_cutoff_s'] <= cutoff]
    if len(rows) != len(expected):
        raise AssertionError('Future truncation changed the number of past outputs')
    maximum = 0.
    for actual, old in zip(rows, expected):
        for key in ['state_time_s', 'availability_cutoff_s', 'status', 'accepted_graph',
                    'range_sample_counts', 'range_medians_m']:
            if actual.get(key) != old.get(key):
                raise AssertionError('Past output changed after truncation: '+key)
        if actual['pose'] is not None:
            maximum = max(maximum, float(np.max(np.abs(np.asarray(actual['pose'])-old['pose']))))
    if maximum > protocol['evaluation_only']['prefix_invariance_tolerance']:
        raise AssertionError('Past pose changed after truncating the future')
    return dict(cutoff_s=cutoff, outputs_checked=len(rows), max_pose_component_delta=maximum, passed=True)


def case_report(case, protocol, out, solver):
    bag = ROOT / case['bag']
    actual_hash = checksum(bag)
    if actual_hash != case['sha256']:
        raise ValueError('Dataset hash mismatch: '+case['bag'])
    diagnostics = {}
    replay = SequentialReplay(protocol['model'], protocol['replay'], solver)
    started = time.perf_counter()
    for event in bag_events(bag, diagnostics):
        replay.ingest(event)
    updates = replay.finish()
    replay_wall = time.perf_counter()-started
    write_json(out/'updates.json', updates)
    write_json(out/'input_diagnostics.json', diagnostics)
    valid = [r for r in updates if r['pose'] is not None]
    if not valid:
        raise AssertionError('No localization outputs')
    published = []
    for r in valid:
        published.append(dict(
            state_time_s=r['state_time_s'], availability_cutoff_s=r['availability_cutoff_s'],
            status=r['status'], accepted_graph=r['accepted_graph'],
            base_x_m=r['pose'][0], base_y_m=r['pose'][1], yaw_rad=r['pose'][2],
            antenna_x_m=r['antenna_xy_m'][0], antenna_y_m=r['antenna_xy_m'][1],
            aligned_odom_antenna_x_m=r['aligned_odom_antenna_xy_m'][0],
            aligned_odom_antenna_y_m=r['aligned_odom_antenna_xy_m'][1],
            graph_states=r['graph_states'], dependency_receipt_max_s=r['dependency_receipt_max_s'],
            solve_wall_s=r['solve_wall_s'], estimated_worker_queue_s=r['estimated_worker_queue_s'],
            range_medians_json=json.dumps(r['range_medians_m'], sort_keys=True),
            sample_counts_json=json.dumps(r['range_sample_counts'], sort_keys=True)))
    write_csv(out/'published.csv', published, list(published[0]))
    write_json(out/'frozen_keyframe_inputs.json', dict(
        times_s=replay.times, local_odom=np.asarray(replay.local).tolist(),
        raw_range_medians_m=replay.observations))

    # These future-dependent comparisons cannot supply any data to the replay.
    model, policy = protocol['model'], protocol['replay']
    times, local, observations = batch_inputs(bag, model, policy)
    if len(times) != len(replay.times) or not np.array_equal(times, replay.times):
        raise AssertionError('Frozen online frontend did not reproduce the batch time grid')
    input_delta = float(np.max(np.abs(local-np.asarray(replay.local))))
    if input_delta > 1e-9 or observations != replay.observations:
        raise AssertionError('Frozen online bins/Odom differ from independent batch inputs')
    heading = math.radians(model['initial_heading_deg'])
    base_start = np.asarray(model['start_antenna_xyz_m'][:2])-rotation(heading)@np.asarray(
        model['base_to_antenna_body_xy_m'])
    batch_graph, batch_info = solver.optimize_graph(
        local, observations, model['anchors_xyz_m'], model['range_bias_m'],
        model['antenna_height_m'], base_start, heading, times, model['graph_parameters'],
        tag_to_base_lever_xy_m=model['base_to_antenna_body_xy_m'], raise_on_failure=False)
    if not batch_info['optimizer_success']:
        raise AssertionError('Independent after-EOF batch comparison did not converge')
    if replay.final_graph is None or replay.final_graph_times != times.tolist():
        raise AssertionError('Final successful prefix does not cover the full comparison grid')
    final_delta = float(np.max(np.abs(replay.final_graph-batch_graph)))
    if final_delta > protocol['evaluation_only']['final_state_equivalence_tolerance']:
        raise AssertionError('Identical-input final prefix and batch solve disagree')

    def trajectory_csv(name, poses):
        rows = []
        for t, p in zip(times, poses):
            xy = antenna(p, model['base_to_antenna_body_xy_m'])
            rows.append(dict(state_time_s=float(t), base_x_m=float(p[0]), base_y_m=float(p[1]),
                             yaw_rad=float(p[2]), antenna_x_m=float(xy[0]), antenna_y_m=float(xy[1])))
        write_csv(out/name, rows, list(rows[0]))
    trajectory_csv('final_smoothed.csv', replay.final_graph)
    trajectory_csv('offline_batch.csv', batch_graph)
    batch_xy = np.array([antenna(p, model['base_to_antenna_body_xy_m']) for p in batch_graph])
    valid_times = np.array([r['state_time_s'] for r in valid])
    evaluation = dict(
        published_graph=endpoint(valid_times, [r['antenna_xy_m'] for r in valid],
                                 case['evaluation_window_s'], case['end_antenna_xyz_m'],
                                 [r['accepted_graph'] for r in valid]),
        offline_batch=endpoint(times, batch_xy, case['evaluation_window_s'], case['end_antenna_xyz_m']),
        aligned_odom=endpoint(valid_times, [r['aligned_odom_antenna_xy_m'] for r in valid],
                              case['evaluation_window_s'], case['end_antenna_xyz_m']))
    archived_delta = abs(evaluation['offline_batch']['difference_m']-case['archived_batch_endpoint_difference_m'])
    if len(times) != case['archived_batch_keyframes'] or archived_delta > protocol[
            'evaluation_only']['archived_endpoint_reproduction_tolerance_m']:
        raise AssertionError('Archived batch endpoint/keyframes were not reproduced')
    guard = check_prefix(bag, protocol, solver, updates)
    dependency_ok = all(r['dependency_receipt_max_s'] is None or
                        r['dependency_receipt_max_s'] <= r['availability_cutoff_s'] for r in updates)
    if not dependency_ok:
        raise AssertionError('Published update used a later receipt')
    durations = np.array([r['solve_wall_s'] for r in valid if r['graph_states'] >= 3])
    result = dict(
        case=case['id'], role=case['role'], bag=case['bag'], sha256=actual_hash,
        records=len(updates), graph_outputs=sum(r['accepted_graph'] for r in updates),
        prediction_only_outputs=sum(r['pose'] is not None and not r['accepted_graph'] for r in updates),
        missing_odom_outputs=sum(r['pose'] is None for r in updates),
        status_counts={s: sum(r['status']==s for r in updates) for s in sorted({r['status'] for r in updates})},
        counters=dict(replay.counters), first_state_time_s=valid[0]['state_time_s'],
        first_graph_state_time_s=next((r['state_time_s'] for r in valid if r['accepted_graph']), None),
        graph_states_max=len(replay.times), graph_size_bounded=False, replay_wall_s=replay_wall,
        solve_wall_ms={key: float(value) for key, value in zip(
            ['min', 'median', 'p95', 'max'], 1000*np.percentile(durations, [0, 50, 95, 100]))},
        estimated_single_worker_queue_max_s=max(r.get('estimated_worker_queue_s', 0) for r in updates),
        timing_note='Virtual deadlines plus measured solver wall time; queue is estimated. Unpaced replay, not a ROS or hardware real-time test.',
        evaluation_window_s=case['evaluation_window_s'], endpoint_evaluation=evaluation,
        verification=dict(all_dependencies_available=dependency_ok, future_truncation=guard,
                          frontend_matches_after_eof_batch=True, max_local_odom_component_delta=input_delta,
                          final_prefix_matches_batch=True, max_final_state_component_delta=final_delta,
                          archived_endpoint_reproduction_delta_m=archived_delta),
        imu_factors=0, independent_trajectory_accuracy_claimed=False, live_or_hard_real_time_accepted=False)
    write_json(out/'comparison.json', result)
    return result


def make_report(results):
    rows = ['# 单车 Python 顺序回放基准', '',
            '沿用冻结的 Odom＋UWB 模型，按记录接收时间持续更新；IMU 没有独立因子。',
            '本实现保留全部历史，每次重新求解；没有固定窗口或实车实时性能验收。', '',
            '| 包 | 当时发布终点差/cm | 整包离线终点差/cm | 对齐 Odom 终点差/cm | 图输出/全部 | 求解p95/ms |',
            '|---|---:|---:|---:|---:|---:|']
    for r in results:
        e = r['endpoint_evaluation']
        value = e['published_graph']['difference_m']
        value_text = '不可用' if value is None else f'{100*value:.3f}'
        rows.append(f"| {r['case']} | {value_text} | {100*e['offline_batch']['difference_m']:.3f} | "
                    f"{100*e['aligned_odom']['difference_m']:.3f} | {r['graph_outputs']}/{r['records']} | "
                    f"{r['solve_wall_ms']['p95']:.3f} |")
    rows += ['', '评价使用原协议冻结的停止后 [2,7) 窗；终点只用于回放完成后的评价。',
             'published.csv 保存当时发布的位置；final_smoothed.csv 是整包结束后的历史修正。',
             'release_delay_s=1 是继承原 ±0.4s 统计窗的设计等待值，不是实测网络延迟。',
             '时钟不作事后拟合，关闭的统计窗不被迟到消息重写。',
             '没有连续轨迹真值；近似底盘几何中心与 Odom 参考点相同仍是假设。',
             '计算统计来自本次机器上的未限速回放，不能替代车载计算机上的实时测速。',
             '两个包已经用于开发，不属于独立未见测试集。', '']
    return '\n'.join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/'protocol.json', protocol)
    solver, results = load_solver(), []
    for case in protocol['cases']:
        print('Starting case '+case['id'], flush=True)
        target = args.output/case['id']
        target.mkdir()
        results.append(case_report(case, protocol, target, solver))
        print(json.dumps(results[-1], ensure_ascii=False, allow_nan=False), flush=True)
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    manifest = dict(
        base_main_sha=protocol['base_main_sha'], runtime_commit_sha=git.stdout.strip() if git.returncode==0 else None,
        python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
        rosbags=importlib.metadata.version('rosbags'), platform=platform.platform(),
        protocol_sha256=checksum(args.protocol),
        source_files={str(p.relative_to(ROOT)): checksum(p) for p in [Path(__file__),
                      ROOT/'tools/single_car_sequential_replay.py', ROOT/protocol['source_solver']['path']]},
        data_files={case['bag']: case['sha256'] for case in protocol['cases']})
    write_json(args.output/'input_manifest.json', manifest)
    write_json(args.output/'summary.json', dict(cases=results, limitations=protocol['assumptions']))
    (args.output/'REPORT.md').write_text(make_report(results))


if __name__ == '__main__':
    main()
