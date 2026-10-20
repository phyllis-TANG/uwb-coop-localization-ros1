#!/usr/bin/env python3
"""重建分析: Oct 18 single-car review, offline only; no endpoint in fitting.

Stages are explicit and refuse to overwrite completed stage outputs. Raw bags
are read from a verified tar archive in memory. No ROS nodes are initialized.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import io
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

import numpy as np
import scipy
from rosbags.highlevel import AnyReader
from importlib.metadata import version

import analyze_october_field_session as legacy

REPO = Path(__file__).resolve().parents[1]
EXPECTED_ARCHIVE = 'c743dc90f3534812fc76073fdc0c594cb0e6cdd33ab82521d8c913fc4c90fcf9'
EXPECTED_INDEX = '371193a0bb542aa55a34486103058619b9adfd07a1c25b7dc2ced522a3d0d7ad'
BAGS = {'004023': 'CAR2_auto_Lshape_repeat_20261018_004023.bag',
        '005135': 'CAR2_auto_Lshape_repeat2_20261018_005135.bag'}
ENDPOINTS = {'004023': [2.97, 3.11, .20], '005135': [2.93, 3.04, .20]}
HISTORICAL = {'004023': [.285499, .558392, .558126],
              '005135': [.245666, .642774, .642761]}


def checksum(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0])
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def git(*args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    return subprocess.check_output(['git', '-C', str(REPO), *args], env=env, text=True)


class MemoryBag:
    suffix = '.bag'

    def __init__(self, name, data):
        self.name, self.data = name, data

    def exists(self):
        return True

    def open(self, mode='rb'):
        if mode != 'rb':
            raise ValueError('read-only input')
        return io.BytesIO(self.data)

    def __str__(self):
        return self.name


def command_bounds(commands):
    """Explicit first non-forward message ends each positive-forward episode."""
    forward, begin = [], None
    for i, row in enumerate(commands):
        active = row[1] > .005
        if active and begin is None:
            begin = i
        elif not active and begin is not None:
            forward.append({'start_s': commands[begin][0], 'end_s': row[0],
                            'last_forward_s': commands[i-1][0],
                            'first_index': begin, 'stop_index': i,
                            'max_command_gap_s': max(np.diff([r[0] for r in commands[begin:i+1]]))})
            begin = None
    if begin is not None or len(forward) != 2:
        raise ValueError('Expected exactly two explicitly ended positive-forward episodes')
    if any(x['max_command_gap_s'] > .5 for x in forward):
        raise ValueError('Command continuity exceeds frozen 0.5 s hold limit')
    turn = [r for r in commands if forward[0]['end_s'] <= r[0] < forward[1]['start_s']
            and abs(r[1]) <= .005 and abs(r[3]) > .04]
    if not turn:
        raise ValueError('Missing main turn')
    turn_end = next(r[0] for r in commands if r[0] > turn[-1][0] and abs(r[3]) <= .04)
    stop = forward[-1]['end_s']
    return {'forward': forward, 'turn_start_s': turn[0][0], 'turn_end_s': turn_end,
            'evaluation_window_s': [stop+2., stop+7.],
            'evaluation_interval': '[start, end)',
            'boundary_clock': 'cmd_vel bag reception, seconds from first bag record'}


def phase_windows(bounds, duration):
    a, b = bounds['forward']
    edges = [0., a['start_s'], a['end_s'], bounds['turn_start_s'],
             bounds['turn_end_s'], b['start_s'], b['end_s'], duration]
    names = ['pre_motion', 'forward_1', 'command_idle_1', 'main_turn',
             'command_idle_2', 'forward_2', 'post_motion']
    return [dict(phase=n, start_s=lo, end_s=hi) for n, lo, hi in zip(names, edges[:-1], edges[1:])]


def phase_at(t, phases):
    return next((p['phase'] for p in phases if p['start_s'] <= t < p['end_s']), 'outside')


def parse_bag(raw, name, anchors):
    data = {'odom': [], 'imu': [], 'cmd': [], 'uwb': [], 'timing': {}}
    frames, children, tags = collections.defaultdict(set), set(), collections.Counter()
    with AnyReader([MemoryBag(name, raw)]) as reader:
        origin = reader.start_time
        end_ns = origin
        for conn, ns, buf in reader.messages():
            end_ns = max(end_ns, ns)
            msg = reader.deserialize(buf, conn.msgtype)
            received = (ns-origin)/1e9
            ht = None
            if hasattr(msg, 'header'):
                st = msg.header.stamp
                header_ns = int(st.sec)*10**9+int(st.nanosec)
                if header_ns <= 0:
                    raise ValueError('Invalid header timestamp')
                ht = (header_ns-origin)/1e9
                frames[conn.topic].add(msg.header.frame_id)
            data['timing'].setdefault(conn.topic, []).append([received, ht])
            if conn.topic == '/car2/odom':
                p, q = msg.pose.pose.position, msg.pose.pose.orientation
                norm = math.sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w)
                if not math.isfinite(norm) or not .5 < norm < 1.5:
                    raise ValueError('Invalid quaternion')
                x, y, z, w = q.x/norm, q.y/norm, q.z/norm, q.w/norm
                yaw = math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
                data['odom'].append([ht, p.x, p.y, yaw, received])
                children.add(msg.child_frame_id)
            elif conn.topic == '/car2/imu':
                data['imu'].append([ht, msg.angular_velocity.z, received])
            elif conn.topic == '/car2/cmd_vel':
                data['cmd'].append([received, msg.linear.x, msg.linear.y, msg.angular.z])
            elif conn.topic == '/car2/uwb/ranges':
                if msg.tag_id != 'node_0':
                    raise ValueError('Unexpected UWB tag')
                tags[msg.tag_id] += 1
                groups = collections.defaultdict(list)
                for r in msg.ranges:
                    groups[str(r.anchor_id)].append(float(r.range))
                data['uwb'].append({'header_s': ht, 'receive_s': received,
                                    'ranges': dict(groups)})
    data['origin_ns'] = origin
    data['duration_s'] = (end_ns-origin)/1e9
    data['frames'] = {k: sorted(v) for k, v in frames.items()}
    data['odom_child_frames'] = sorted(children)
    data['tags'] = dict(tags)
    for topic, rows in data['timing'].items():
        h = [r[1] for r in rows if r[1] is not None]
        if h and (not np.isfinite(h).all() or np.any(np.diff(h) <= 0)):
            raise ValueError('Non-monotonic/nonfinite header in '+topic)
    if data['odom_child_frames'] != ['base_footprint']:
        raise ValueError('Unexpected odom child frame')
    if not np.isfinite(np.asarray(data['odom'])).all():
        raise ValueError('Invalid odometry')
    return data


def valid_value(raw):
    if not raw:
        return None, 'missing'
    if len(raw) != 1:
        return None, 'duplicate'
    if not math.isfinite(raw[0]):
        return None, 'nonfinite'
    if raw[0] <= 0:
        return None, 'nonpositive'
    return raw[0], 'valid'


def prepare(args):
    out = args.output
    if out.exists():
        raise FileExistsError('Refusing to overwrite analysis directory: '+str(out))
    assert checksum(args.archive) == EXPECTED_ARCHIVE
    assert checksum(args.index) == EXPECTED_INDEX
    supplied = {line.split(maxsplit=1)[1].strip().lstrip('*'): line.split()[0]
                for line in args.sums.read_text(encoding='utf-8-sig').splitlines() if line.strip()}
    assert supplied['field_tests_20261018.tar.gz'] == EXPECTED_ARCHIVE
    assert supplied['uwb_data_index_20261020.zip'] == EXPECTED_INDEX
    initial = {'repo': str(REPO), 'branch': git('branch', '--show-current').strip(),
               'head': git('rev-parse', 'HEAD').strip(),
               'status_porcelain': git('status', '--porcelain=v1', '--untracked-files=all'),
               'worktrees': git('worktree', 'list', '--porcelain')}
    out.mkdir(parents=True)
    with zipfile.ZipFile(args.index) as z:
        assert z.testzip() is None
        for item in z.infolist():
            p = PurePosixPath(item.filename)
            assert not p.is_absolute() and '..' not in p.parts
            if not item.is_dir():
                dest = out/'evidence/index'/Path(*p.parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(item))
    shutil.copy2(args.sums, out/'evidence/cloud_inputs_SHA256SUMS.txt')
    original = REPO/'docs/field_tests/20261017/session_config.json'
    shutil.copy2(original, out/'evidence/oct17_session_config.json')
    old = read_json(original)
    config = {'analysis_label': '重建分析', 'schema_version': 1,
              'source_method': 'existing single-car fixed-height SE(2) batch graph with minimal rotating lever-arm adaptation',
              'anchors_xyz_m': old['anchors_xyz_m'], 'graph_parameters': old['graph_parameters'],
              'range_bias_m': {k: 0. for k in old['anchors_xyz_m']},
              'candidate_start_antenna_xyz_m': [2., 2., .2], 'initial_heading_deg': 90.,
              'base_to_antenna_body_xy_m': [.12, -.08], 'antenna_height_m': .2,
              'reference_assumption': 'approximate surveyed chassis geometric center assumed equal to odom base_footprint; unmeasured',
              'start_status': 'candidate inherited from other L runs, not independently measured for these bags',
              'clock': 'sensor headers and cmd reception use recorded ROS wall-clock seconds minus first bag receipt; no fitted clock correction',
              'keyframes': 'arange(ceil(max(first odom header, first UWB header)+1), floor(min(last odom header,last UWB header)),1)',
              'bin_min_valid_observations': 5,
              'range_robust_loss': 'existing pseudo-Huber on normalized ranges only, delta=1; odom/prior Gaussian; scipy loss=linear',
              'optimizer': {'max_nfev': 300, 'ftol': 1e-7, 'xtol': 1e-7, 'gtol': 1e-7,
                            'failure_policy': 'retain finite iterate for diagnosis; exclude failed solve from accepted accuracy claim'},
              'evaluation': {'window_after_final_forward_stop_s': [2., 7.], 'interval': '[left,right)',
                             'statistic': 'median estimated antenna X and Y at frozen keyframes',
                             'endpoints_xyz_m': ENDPOINTS, 'endpoint_in_optimizer': False},
              'filter': {'version': 'rebuild_exploratory_physical_hampel_v1', 'all_nodes_and_bags_same_rule': True,
                         'vertical_feasibility_tolerance_m': .05, 'half_window_s': .5,
                         'min_other_valid_neighbors': 10, 'mad_scale': 1.4826, 'mad_multiplier': 4.5,
                         'absolute_floor_m': .35, 'neighbor_policy': 'centered header-time window, original baseline-valid values, exclude self; no iterative filtering',
                         'threshold_basis': 'exploratory 0.20 m/s antenna speed envelope * 0.5 s + 0.25 m margin = 0.35 m; MAD handles local variation; not validated',
                         'insufficient_support': 'keep if physically feasible; flag insufficient support',
                         'known_limit': 'cannot certify correct values or remove stable bias or majority corruption'},
              'historical_filter': {'recovered': False, 'unknown': ['old added code', 'window definition', 'MAD threshold and scale', 'exact old preprocessing'],
                                    'exact_old_C_reproduction_claimed': False},
              'parameter_policy': 'inherited Oct17 weights are unvalidated pilot settings; no tuning to endpoints or historical results',
              'imu': 'diagnostic only; odom yaw may share IMU source',
              'online_performance_claimed': False, 'continuous_truth_available': False}
    write_json(out/'frozen_config.json', config)
    inputs, checks = [], []
    with tarfile.open(args.archive, 'r:gz') as t:
        sums = t.extractfile('20261018/BAG_SHA256SUMS.txt').read()
        (out/'evidence/BAG_SHA256SUMS.txt').write_bytes(sums)
        expected = {Path(n.strip().lstrip('*')).name: h for h, n in
                    (line.split(maxsplit=1) for line in sums.decode().splitlines() if line.strip())}
        for m in t.getmembers():
            if not m.isfile():
                continue
            if m.name.endswith('.bag'):
                raw = t.extractfile(m).read()
                h = hashlib.sha256(raw).hexdigest()
                assert h == expected[Path(m.name).name]
                checks.append({'member': m.name, 'size_bytes': len(raw), 'sha256': h, 'manifest_match': True})
                if Path(m.name).name not in BAGS.values():
                    continue
                run = next(k for k, v in BAGS.items() if v == Path(m.name).name)
                data = parse_bag(raw, BAGS[run], config['anchors_xyz_m'])
                bounds = command_bounds(data['cmd'])
                data['bounds'] = bounds
                data['phases'] = phase_windows(bounds, data['duration_s'])
                cache = out/'input_audit'/f'{run}_decoded.json.gz'
                cache.parent.mkdir(exist_ok=True)
                with gzip.open(cache, 'wt', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, allow_nan=False)
                write_csv(out/'input_audit'/f'{run}_commands.csv',
                          [dict(zip(['receive_s','vx_m_s','vy_m_s','wz_rad_s'], row)) for row in data['cmd']])
                inputs.append({'run': run, 'bag': BAGS[run], 'sha256': h, 'size_bytes': len(raw),
                               'duration_s': data['duration_s'], 'origin_ns': data['origin_ns'],
                               'topic_counts': {k: len(v) for k, v in data['timing'].items()},
                               'frames': data['frames'], 'odom_child_frames': data['odom_child_frames'],
                               'bounds': bounds, 'phases': data['phases'], 'cache_sha256': checksum(cache)})
            else:
                p = PurePosixPath(m.name)
                assert not p.is_absolute() and '..' not in p.parts
                dst = out/'evidence/archive_notes'/Path(*p.parts)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(t.extractfile(m).read())
    assert sorted(x['run'] for x in inputs) == sorted(BAGS)
    write_json(out/'input_manifest.json', {'analysis_label': '重建分析', 'git_at_prepare': initial,
        'attachments': [{'name': p.name, 'path': str(p), 'sha256': checksum(p), 'size_bytes': p.stat().st_size}
                        for p in [args.archive, args.index, args.sums]],
        'all_archive_bag_checks': checks, 'selected_inputs': sorted(inputs, key=lambda x: x['run']),
        'prior_artifact_search': {'old_uncommitted_outputs_recovered': False,
          'missing': ['HANDOFF.md before this run', 'single_car_baseline_20261020/', 'review_oct18_single_car.py', 'test_single_car_oct18_review.py', 'uncommitted analyzer changes'],
          'existing': ['committed two_car_graph results (different task)', 'raw field archive', 'guidance index (not localization output)'],
          'scope': '/workspace including hidden/ignored files, readable /tmp and uploaded archive listings; inaccessible old cloud session',
          'visible_related_analysis_processes_at_start': False, 'docker_socket': 'not accessible in sandbox'},
        'software': {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
                     'numpy': np.__version__, 'scipy': scipy.__version__, 'rosbags': version('rosbags')},
        'config_sha256': checksum(out/'frozen_config.json')})
    (out/'METHOD_REVIEW.md').write_text('''# 重建分析：实现核对与冻结假设

原实现 tools/analyze_october_field_session.py 的 optimize_graph 是单车固定高度 SE(2) 批量最小二乘，非在线融合，非 iSAM2。状态为 base XY/yaw；odom 增量在前一帧车身坐标中计算；初始全局变换仅由候选起点和 +Y 朝向定义。三维测距保留墙节点与天线的高度差。

已有参数沿用 10 月 17 日配置：每 1s 关键帧、±0.4s 窗内至少 5 个原始有效值取中位数；range sigma=0.2m；odom translation sigma=0.03m×sqrt(dt)、yaw sigma=2deg×sqrt(dt)；位置/朝向先验 sigma=0.2m/5deg。range 使用原有伪 Huber，其他因子 Gaussian。这些是未独立验证的试验权重。

最小适配：原函数新增可选水平外参（默认零，旧调用兼容），测距前按状态 yaw 旋转 [0.12,-0.08]m 并更新稀疏雅可比的 yaw 依赖；新增优化状态记录。底盘几何中心等于 base_footprint 是未测定假设。候选天线起点 [2,2,0.2]m 对应 base 起点 [1.92,1.88]m（yaw=90deg）。A/B/C 均采用相同参考点、外参和 odom。

原先 P1 偏差、手工 N10 时间掩码和 odom innovation gate 均不进入本轮。B 为原始有效测距加已有中位数聚合及鲁棒损失。C 仅在聚合前新增统一物理下界和非迭代 Hampel 筛选；版本及阈值先冻结于 frozen_config.json。旧任务筛选源码、窗口和 MAD 参数均未恢复，不能精确复现旧 C，也不按历史数字调整配置。

传感器使用 header，指令无 header 因而用 bag 接收时刻；均减同一个 bag 首条记录原点，不估计时延修正。测量/命令时间关联存在未量化的发布与接收延迟。指令停止边界由最后一段正向指令之后第一条非前进指令确定；评价 [stop+2, stop+7)。接收停顿另作时间诊断，不当作测距异常。

人工终点只交给评价/几何诊断，优化函数及筛选无人工终点参数。起点数值仍是候选、水平参考点关系未测定；测量不确定度未完全量化。全部结果是条件性重建对照，不计算 ATE/RMSE，不宣称在线性能或融合必有改善。输入文档中的历史命令只作为证据保存，不执行。
''', encoding='utf-8')
    print('PREPARED', out, flush=True)
    for x in inputs:
        print(x['run'], 'WINDOW', x['bounds']['evaluation_window_s'], flush=True)


def load_data(out, run):
    manifest = read_json(out/'input_manifest.json')
    assert checksum(out/'frozen_config.json') == manifest['config_sha256'], 'frozen config changed'
    entry = next(x for x in manifest['selected_inputs'] if x['run'] == run)
    cache = out/'input_audit'/f'{run}_decoded.json.gz'
    assert checksum(cache) == entry['cache_sha256']
    with gzip.open(cache, 'rt', encoding='utf-8') as f:
        return json.load(f)


def antenna(states, lever):
    th = states[:, 2]
    return states[:, :2] + np.column_stack((np.cos(th)*lever[0]-np.sin(th)*lever[1],
                                           np.sin(th)*lever[0]+np.cos(th)*lever[1]))


def initial_base(local, start_antenna, heading, lever):
    base_start = np.asarray(start_antenna[:2])-legacy.rotation(heading).dot(lever)
    return legacy.align_odom(local, list(base_start)+[start_antenna[2]], heading), base_start


def filter_rows(data, config):
    """Return complete per-frame/node ledger; decisions never use endpoints."""
    anchors, rule = config['anchors_xyz_m'], config['filter']
    frames = data['uwb']
    sequences = {k: [] for k in anchors}
    for i, f in enumerate(frames):
        for k in anchors:
            v, state = valid_value(f['ranges'].get(k, []))
            if state == 'valid':
                sequences[k].append((i, f['header_s'], v))
    decisions = {}
    for k, rows in sequences.items():
        times = np.asarray([r[1] for r in rows])
        values = np.asarray([r[2] for r in rows])
        for j, (i, t, v) in enumerate(rows):
            lo, hi = np.searchsorted(times, [t-rule['half_window_s'], t+rule['half_window_s']], side='left')
            # Include the exact right-hand endpoint consistently.
            hi = int(np.searchsorted(times, t+rule['half_window_s'], side='right'))
            neighbors = np.r_[values[lo:j], values[j+1:hi]]
            median = float(np.median(neighbors)) if len(neighbors) else None
            mad = float(np.median(np.abs(neighbors-median))) if len(neighbors) else None
            threshold = max(rule['absolute_floor_m'], rule['mad_multiplier']*rule['mad_scale']*mad) if mad is not None else None
            reasons = []
            if v < abs(anchors[k][2]-config['antenna_height_m'])-rule['vertical_feasibility_tolerance_m']:
                reasons.append('below_vertical_geometry_bound')
            support = len(neighbors) >= rule['min_other_valid_neighbors']
            if support and abs(v-median) > threshold:
                reasons.append('centered_hampel')
            decisions[(i,k)] = dict(C_keep=not reasons, C_reason=';'.join(reasons) or 'kept',
                neighbors=len(neighbors), local_median_m=median, local_mad_m=mad,
                threshold_m=threshold, support_sufficient=support)
    ledger = []
    for i, f in enumerate(frames):
        for k in sorted(anchors):
            raw = f['ranges'].get(k, [])
            v, state = valid_value(raw)
            row = {'frame': i, 'header_s': f['header_s'], 'receive_s': f['receive_s'],
                   'node': k, 'phase': phase_at(f['header_s'], data['phases']),
                   'raw_values_json': json.dumps(raw), 'raw_m': v, 'baseline_status': state,
                   'B_keep': state == 'valid', 'C_keep': False, 'C_reason': 'baseline_'+state,
                   'neighbors': 0, 'local_median_m': None, 'local_mad_m': None,
                   'threshold_m': None, 'support_sufficient': False}
            if state == 'valid':
                row.update(decisions[(i,k)])
            ledger.append(row)
    return ledger


def build_inputs(data, config, ledger):
    od = np.asarray(data['odom'], dtype=float)
    od[:, 3] = np.unwrap(od[:, 3])
    low = max(od[0,0], data['uwb'][0]['header_s'])
    high = min(od[-1,0], data['uwb'][-1]['header_s'])
    params = config['graph_parameters']
    times = np.arange(math.ceil(low+1.), math.floor(high), params['keyframe_step_s'])
    if len(times) < 3:
        raise ValueError('Insufficient common coverage')
    local = np.column_stack([np.interp(times, od[:,0], od[:,j]) for j in [1,2,3]])
    initial, base_start = initial_base(local, config['candidate_start_antenna_xyz_m'],
                                     math.radians(config['initial_heading_deg']), config['base_to_antenna_body_xy_m'])
    observations, bins = {}, []
    for method in ['B', 'C']:
        raw = {k: [(r['header_s'], r['raw_m']) for r in ledger if r['node'] == k and r[method+'_keep']]
               for k in config['anchors_xyz_m']}
        obs = []
        for i,t in enumerate(times):
            row = {}
            for k, seq in sorted(raw.items()):
                v = [v for stamp,v in seq if abs(stamp-t) <= params['range_bin_half_width_s']]
                value = float(np.median(v)) if len(v) >= config['bin_min_valid_observations'] else None
                if value is not None:
                    row[k] = value
                bins.append({'method': method, 'keyframe': i, 'time_s': t, 'node': k,
                             'phase': phase_at(t, data['phases']), 'raw_support': len(v), 'range_m': value,
                             'factor_present': value is not None})
            obs.append(row)
        observations[method] = obs
    return times, local, initial, base_start, observations, bins


def distribution(values):
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    if not len(a):
        return dict(n=0, min=None, p05=None, median=None, p95=None, max=None, mean=None, std=None)
    return dict(n=len(a), min=float(a.min()), p05=float(np.percentile(a,5)),
                median=float(np.median(a)), p95=float(np.percentile(a,95)), max=float(a.max()),
                mean=float(a.mean()), std=float(a.std()))


def endpoint_result(times, states, window, target, lever):
    mask = (times >= window[0]) & (times < window[1])
    xy = antenna(states, lever)[mask]
    if not len(xy) or not np.isfinite(xy).all():
        raise ValueError('Unavailable endpoint estimate')
    med = np.median(xy, axis=0)
    return {'state_samples': len(xy), 'median_antenna_xy_m': med.tolist(),
            'planar_difference_m': float(np.linalg.norm(med-np.asarray(target[:2]))),
            'xy_min_m': xy.min(axis=0).tolist(), 'xy_max_m': xy.max(axis=0).tolist(),
            'xy_std_m': xy.std(axis=0).tolist(),
            'first_to_last_drift_m': float(np.linalg.norm(xy[-1]-xy[0]))}


def baseline(args):
    out = args.output
    dest = out/'baseline'
    if dest.exists():
        raise FileExistsError('Baseline output already exists; use a fresh independent run')
    dest.mkdir()
    config = read_json(out/'frozen_config.json')
    write_json(dest/'source_hashes_at_run.json', {str(p.relative_to(REPO)): checksum(p) for p in
               [Path(__file__).resolve(), REPO/'tools/analyze_october_field_session.py']})
    all_summary, trajectories = [], []
    for run in BAGS:
        data = load_data(out, run)
        ledger = filter_rows(data, config)
        times, local, initial, base_start, obs, bins = build_inputs(data, config, ledger)
        write_csv(dest/f'{run}_filter_ledger.csv', ledger)
        write_csv(dest/f'{run}_range_bins.csv', bins)
        states = {'A': initial}
        statuses = {'A': {'optimizer_success': None, 'method': 'deterministic aligned odom propagation'}}
        for method in ['B', 'C']:
            print('SOLVING', run, method, len(times), flush=True)
            try:
                graph, info = legacy.optimize_graph(local, obs[method], config['anchors_xyz_m'],
                    config['range_bias_m'], config['antenna_height_m'], base_start,
                    math.radians(config['initial_heading_deg']), times, config['graph_parameters'],
                    tag_to_base_lever_xy_m=config['base_to_antenna_body_xy_m'], raise_on_failure=False)
                states[method], statuses[method] = graph, info
            except Exception as exc:
                statuses[method] = {'optimizer_success': False, 'exception': repr(exc)}
            write_json(dest/f'{run}_{method}_optimizer.json', statuses[method])
        for method, poses in states.items():
            ant = antenna(poses, config['base_to_antenna_body_xy_m'])
            for i,t in enumerate(times):
                trajectories.append({'run': run, 'method': method, 'time_s': t,
                    'phase': phase_at(t, data['phases']), 'base_x_m': poses[i,0], 'base_y_m': poses[i,1],
                    'yaw_rad': poses[i,2], 'antenna_x_m': ant[i,0], 'antenna_y_m': ant[i,1],
                    'accepted_solve': method == 'A' or statuses[method].get('optimizer_success',False),
                    'range_factors': len(obs[method][i]) if method in obs else 0,
                    'in_evaluation_window': data['bounds']['evaluation_window_s'][0] <= t < data['bounds']['evaluation_window_s'][1]})
            e = endpoint_result(times, poses, data['bounds']['evaluation_window_s'],
                                config['evaluation']['endpoints_xyz_m'][run], config['base_to_antenna_body_xy_m'])
            all_summary.append({'run': run, 'method': method, 'analysis_label': '重建分析',
                'conditional': True, 'accepted_solve': method == 'A' or statuses[method].get('optimizer_success',False),
                'keyframes': len(times), 'first_state_s': float(times[0]), 'last_state_s': float(times[-1]),
                'evaluation_window_s': data['bounds']['evaluation_window_s'], 'endpoint': e,
                'optimizer': statuses[method],
                'additional_rejected_observations': sum(r['B_keep'] and not r['C_keep'] for r in ledger) if method == 'C' else 0})
            print('RESULT',run,method,e['planar_difference_m'],statuses[method],flush=True)
        write_json(dest/f'{run}_completed.json', {'methods_with_states': list(states), 'status': statuses})
    write_csv(dest/'trajectories.csv', trajectories)
    write_json(dest/'summary.json', all_summary)
    write_csv(dest/'endpoint_comparison.csv', [{'run':s['run'], 'method':s['method'], 'analysis_label':'重建分析',
       'accepted_solve':s['accepted_solve'], 'window_start_s':s['evaluation_window_s'][0], 'window_end_s':s['evaluation_window_s'][1],
       'samples':s['endpoint']['state_samples'], 'median_x_m':s['endpoint']['median_antenna_xy_m'][0],
       'median_y_m':s['endpoint']['median_antenna_xy_m'][1], 'planar_difference_m':s['endpoint']['planar_difference_m'],
       'extra_rejected_observations':s['additional_rejected_observations']} for s in all_summary])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('stage', choices=['prepare','baseline'])
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--archive', type=Path)
    ap.add_argument('--index', type=Path)
    ap.add_argument('--sums', type=Path)
    args = ap.parse_args()
    if args.stage == 'prepare':
        prepare(args)
    else:
        baseline(args)


if __name__ == '__main__':
    main()
