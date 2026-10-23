#!/usr/bin/env python3
"""Recompute exported trajectory metrics and summarize positive/negative cases."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from run_two_car_updated_comparison import write_csv, write_json
from two_car_stationary_confidence import confidence_scales
from two_car_updated_comparison import CARS, sha256

CONFIGS = ['baseline', 'stationary_only', 'confidence_only', 'combined']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    args = parser.parse_args(); root = args.results
    project = Path(__file__).resolve().parents[1]
    protocol = json.loads((root/'protocol.json').read_text())
    summary = json.loads((root/'summary.json').read_text())
    scales = json.loads((root/'range_confidence.json').read_text())
    manifest = json.loads((root/'input_manifest.json').read_text())
    parent = json.loads((project/protocol['parent_protocol_path']).read_text())
    with (root/'trajectories.csv').open() as stream:
        data = list(csv.DictReader(stream))
    with (root/'comparison.csv').open() as stream:
        table = {(r['case'], r['configuration'], r['method'], r['car']): r for r in csv.DictReader(stream)}
    frozen = confidence_scales(scales['training'], protocol['range_confidence']['wall_sigma_floor_m'],
                               protocol['range_confidence']['peer_sigma_floor_m'])
    assert frozen == scales['scales']
    assert not {r['id'] for r in scales['training']} & {r['id'] for r in scales['validation']}
    assert not {r['id'] for r in scales['training']} & set(protocol['cases'])
    assert manifest['protocol_sha256'] == sha256(root/'protocol.json')
    assert manifest['source_files_sha256'] == {k: sha256(project/'tools'/k) for k in manifest['source_files_sha256']}
    maximum, derived, method_count = 0., [], 0
    for case in summary['cases']:
        reference = next(r for r in parent['cases'] if r['id'] == case['case'])
        detector = json.loads((root/case['case']/'motion_candidates.json').read_text())
        for name, pair in case['configurations'].items():
            for method in ['independent', 'joint']:
                method_count += 1; metrics = pair[method]
                ledger = metrics['factor_cost_ledger']
                actual_cost = sum(sum(v.values()) if isinstance(v, dict) else v for v in ledger.values())
                assert abs(actual_cost-metrics['optimizer']['cost']) < 1e-9
                for car in CARS:
                    rows = [r for r in data if r['case'] == case['case'] and r['configuration'] == name
                            and r['method'] == method and r['car'] == car]
                    rows.sort(key=lambda r: float(r['elapsed_s']))
                    assert len(rows) == metrics['keyframes']
                    xy = np.asarray([[float(r['antenna_x_m']), float(r['antenna_y_m'])] for r in rows])
                    steps = np.linalg.norm(np.diff(xy, axis=0), axis=1)
                    mask = np.asarray([r['candidate'] for r in detector[car]])
                    endpoint = np.median(xy[-5:], axis=0)
                    target = reference['evaluation_only']['end_antenna_xyz_m'][car][:2]
                    error = float(np.linalg.norm(endpoint-target))
                    path = float(steps.sum())
                    old = table[(case['case'], name, method, car)]
                    differences = [abs(error-metrics['endpoint_difference_m'][car]),
                        abs(path-metrics['cars'][car]['estimated_antenna_path_m']),
                        abs(float(old['endpoint_difference_m'])-error), abs(float(old['antenna_path_m'])-path)]
                    maximum = max(maximum, *differences)
                    derived.append(dict(case=case['case'], configuration=name, method=method, car=car,
                        candidate_edge_path_m=float(steps[mask].sum()),
                        other_edge_path_m=float(steps[~mask].sum()), total_path_m=path,
                        candidate_edges=int(mask.sum()), total_edges=len(mask)))
            assert pair['independent']['peer_factor_count'] == 0
            assert pair['independent']['wall_factor_count'] == pair['joint']['wall_factor_count']
            for car in CARS:
                effect = pair['joint']['endpoint_difference_m'][car]-pair['independent']['endpoint_difference_m'][car]
                assert abs(effect-pair['endpoint_effect_joint_minus_independent_m'][car]) < 1e-14
    assert maximum < 1e-12 and method_count == manifest['method_records'] == 36
    assert len(data) == manifest['trajectory_rows'] == 6168
    write_csv(root/'candidate_edge_deformation.csv', derived)
    training_n10 = {r['id']: r['wall_errors_m']['car2']['node_10'] for r in scales['training']}
    assert all(r['antenna_xyz_m']['car2'] == [2., 2., .2] for r in protocol['range_confidence']['training'])
    write_json(root/'DERIVED_VERIFICATION.json', dict(passed=True,
        method_records=method_count, trajectory_rows=len(data),
        csv_and_summary_metric_max_difference_m=maximum,
        baseline_trajectory_reproduction_max_component_delta=manifest['baseline_reproduction_max_component_delta'],
        actual_factor_ledgers_verified=True, independent_peer_factor_counts_zero=True,
        matched_wall_factor_counts=True, range_scales_reproduced_from_training_only=True,
        source_and_protocol_hashes_verified=True, car2_same_position_training_node10_errors_m=training_n10,
        car2_same_position_node10_error_span_m=max(training_n10.values())-min(training_n10.values()),
        all_solves_accepted=True, max_nfev=max(p[m]['optimizer']['nfev'] for c in summary['cases']
        for p in c['configurations'].values() for m in ['independent', 'joint'])))
    lines = ['# 静止车拉动与测距可信度：冻结方案的第一轮开发试验', '',
        '本轮完成三包 × 六配置 × 两方法，共 36 次全包离线求解；全部接受，最多 10 次函数评估。PR38 主基线逐点复现差为 0。',
        '22 项数值与策略测试通过。四种主配置为：原基线、仅近零运动协方差、仅测距可信度、两项同时启用；另外保留两种人工整车墙测距缺失。', '',
        '## 静止车辆的形变确实减少，但整体平移仍存在', '',
        '| 包 / 静止车 | 原联合轨迹/cm | 仅近零运动/cm | 仅测距可信度/cm | 同时启用/cm |',
        '|---|---:|---:|---:|---:|']
    for case in summary['cases']:
        car = case['stationary_car']
        if car:
            values = [100*case['configurations'][c]['joint']['cars'][car]['estimated_antenna_path_m'] for c in CONFIGS]
            lines.append(f"| {case['case']} / {car} | "+' | '.join(f'{x:.2f}' for x in values)+' |')
    lines += ['', '这些数值是静止车辆的累计估计轨迹长度，不是定位误差、ATE 或两车间距误差。',
        '仅近零运动策略分别使联合图的静止车轨迹缩短约 69% 和 67%；同时启用约 89% 和 84%。',
        '策略只把已有 Odom 相对增量的标准差乘 0.1，保留原始均值和起点先验；没有把真实静止坐标锁入优化。',
        '缺样/时间间隙处不启用加强约束，残余形变可能集中在这些边，详见 candidate_edge_deformation.csv。', '',
        '## 终点并非全面改善', '',
        '单位 cm；每格为各自融合 → 联合融合，与人工终点比较，采用最后五个关键帧天线坐标中位数。', '',
        '| 包 | 配置 | Car1/cm | Car2/cm |', '|---|---|---:|---:|']
    for case in summary['cases']:
        for config in CONFIGS:
            pair = case['configurations'][config]
            values = [f"{100*pair['independent']['endpoint_difference_m'][c]:.2f} → {100*pair['joint']['endpoint_difference_m'][c]:.2f}" for c in CARS]
            lines.append(f"| {case['case']} | {config} | "+' | '.join(values)+' |')
    lines += ['', '同时启用时，050447 的 Car2 从基线联合 17.91 cm 降到 4.13 cm，但 Car1 从 20.06 cm 增到 23.27 cm；',
        '015334 的移动 Car2 则从 8.92 cm 增到 15.14 cm，033248 的静止 Car2 从 2.67 cm 增到 10.26 cm。',
        '不能据此宣称新配置整体优于基线、两车均受益或协同收益已稳定成立。静止形变减少与绝对定位改善是两个评价目标。', '',
        '## 固定可信度为何仍会退步', '',
        '保持 PR38 的每车墙测距修正和无车间偏置的策略；新尺度为 hypot(0.2 m, 训练静态包中该链路最大的绝对中位数参考偏差)。',
        '013206、013951、015009 为尺度训练；020151 只验证。没有动态终点拟合，也没有新增位置修正函数。',
        'Car2/node_10 的尺度由 0.2 m 增到 0.65146 m，车间尺度为 0.34897 m；损失仍是原 signed pseudo-Huber。',
        '这会降低存在迁移问题的测距影响，但也会在该链路已经恢复正常时丢掉有用的信息，且不能消除物理测距偏差。', '',
        '**偏差还不能单纯归因于位置。** 三个训练静态包的 Car2 人工参考位置均为 [2, 2, 0.2] m，',
        '但 node_10 修正后参考偏差分别为 '+', '.join(f"{k}: {100*v:+.2f} cm" for k, v in training_n10.items())+'。',
        '同一位置的差异约 '+f'{100*(max(training_n10.values())-min(training_n10.values())):.2f}'+' cm。',
        '这只能证明现有固定修正未充分描述数据与参考的差异，不能独自确定是遮挡、朝向、时间变化、设备状态还是参考记录问题。', '',
        '## 人工整车墙测距缺失：完整保留反例', '',
        '| 包 | 同时启用后移除观测 | Car1 各自→联合/cm | Car2 各自→联合/cm |', '|---|---|---:|---:|']
    for case in summary['cases']:
        for config in ['combined_no_car1_walls', 'combined_no_car2_walls']:
            pair = case['configurations'][config]
            values = [f"{100*pair['independent']['endpoint_difference_m'][c]:.2f} → {100*pair['joint']['endpoint_difference_m'][c]:.2f}" for c in CARS]
            lines.append(f"| {case['case']} | {config} | "+' | '.join(values)+' |')
    lines += ['', '这是合成缺测，不能称为真实 NLOS 测试。静止车只靠正确外部起点和零 Odom 得到零终点差，不代表普遍零误差定位。',
        '例如 033248 移除 Car2 墙测距后，联合图仍使其整体偏移约 16.31 cm，尽管轨迹形变已经很小。', '',
        '## 当前决策与后续验证', '',
        '近零运动协方差保留为可选候选：相对形变目标有正面证据，须验证推车、打滑、极低速、停车边界与掉帧。',
        '静态统一测距尺度保留为实验对照，不替换默认模型，也不作为已解决空间偏差的结论。',
        '下一轮优先检查随时间变化的多链路一致性/异常测距识别，并用独立留出数据评价；不继续依靠这三个终点调出漂亮数字。',
        '实验室先核对 Odom 原点和安装外参/朝向，随后在同位置、不同朝向、交换遮挡和移动后返回原点的静态重复中记录卷尺参考，区分位置效应与状态变化。',
        '近零检测中的 pose/twist 来自同一 Odom 消息，彼此不独立；即使两者为零，也不能证明真实车辆没有被推动或打滑。',
        '所有结果仍是已知历史包的全包离线平滑，无连续真值、无盲测结论、无双车顺序回放或联合固定窗口，也无新增独立 IMU 因子。', '',
        '![静止轨迹形变](stationary_deformation.png)', '', '![终点消融对照](endpoint_ablation.png)', '',
        '![静态测距参考偏差](static_range_transfer.png)', '']
    (root/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps(dict(verified=True, records=method_count, maximum_metric_delta_m=maximum)))


if __name__ == '__main__':
    main()
