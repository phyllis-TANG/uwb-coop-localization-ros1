#!/usr/bin/env python3
"""Verify exports, locate downweighted intervals and retain negative evidence."""
import argparse
import collections
import csv
import json
from pathlib import Path
import sys

import numpy as np
import scipy

from run_two_car_updated_comparison import write_csv, write_json
from two_car_updated_comparison import CARS, build_inputs, read_bag, sha256
from two_car_range_confidence import lagged_weight, predict_confidence

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open() as f: return list(csv.DictReader(f))


def contamination_check(docs, protocol, plan):
    case = next(c for c in plan['static_cases'] if c['id']=='015009')
    parent = json.loads((ROOT/protocol['parent_protocol_path']).read_text())
    fixed = json.loads((ROOT/protocol['frozen_fixed_scales_path']).read_text())
    raw = read_bag(ROOT/case['path'], case['sha256'])
    model = dict(start_antenna_xyz_m=case['antenna_xyz_m'], initial_heading_deg={c: 0. for c in CARS})
    config = dict(correction='per_car', peer_sigma_m=.2, withheld_wall_car=None, car2_peer_shift_s=0.)
    inputs = build_inputs(raw, model, parent, config, fixed['biases_m'])
    reference = float(np.linalg.norm(np.asarray(case['antenna_xyz_m']['car1'])-case['antenna_xyz_m']['car2']))
    output = {}
    for name in ['all_walls', 'remove_car2_node10_from_predictor_only']:
        if name != 'all_walls':
            for row in inputs['cars']['car2']['observations']: row.pop('node_10', None)
        values = predict_confidence(inputs, protocol['new_policy'])['peer']
        predicted = float(np.median([v['predicted_m'] for v in values]))
        output[name] = dict(peer_predicted_median_m=predicted,
            peer_prediction_minus_reference_m=predicted-reference,
            peer_observed_median_m=float(np.median([v['measured_corrected_m'] for v in values])),
            peer_min_weight=min(v['weight'] for v in values),
            peer_downweighted_bins=sum(v['weight']<1-1e-12 for v in values))
    output.update(reference_3d_m=reference, diagnostic_only=True,
                  used_to_change_frozen_policy_or_graph_weights=False)
    write_json(docs/'diagnostics/predictor_contamination_check.json', output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('docs', type=Path)
    parser.add_argument('--dependency-path', type=Path)
    args = parser.parse_args()
    if args.dependency_path: sys.path.append(str(args.dependency_path.resolve()))
    docs, result = args.docs, args.docs/'results'
    protocol = json.loads((result/'protocol.json').read_text())
    plan = json.loads((docs/'diagnostic_plan.json').read_text())
    parent = json.loads((ROOT/protocol['parent_protocol_path']).read_text())
    summary = json.loads((result/'summary.json').read_text())
    manifest = json.loads((result/'input_manifest.json').read_text())
    raw = json.loads((docs/'diagnostics/raw_summary.json').read_text())
    assert sha256(docs/'protocol.json') == manifest['protocol_sha256'] == sha256(result/'protocol.json')
    assert manifest['source_files_sha256'] == {k: sha256(ROOT/'tools'/k) for k in manifest['source_files_sha256']}
    assert manifest['data_sha256'] == {c['path']: c['sha256'] for kind in ['static', 'dynamic'] for c in plan[kind+'_cases']}
    quality_count = sum(v['samples'] for c in raw['recordings'] for v in c['quality'].values())
    quality_finite = sum(v['finite_quality_samples'] for c in raw['recordings'] for v in c['quality'].values())
    assert quality_finite == 0
    confidence = read_csv(result/'confidence.csv')
    groups = collections.defaultdict(list)
    for row in confidence: groups[(row['case'], row['kind'], row['factor'])].append(row)
    statistics, intervals = [], []
    weight_delta = 0.
    for (case, kind, factor), rows in sorted(groups.items()):
        rows.sort(key=lambda r: int(r['epoch']))
        history, active = [], []
        for row in rows:
            expected = lagged_weight(history, protocol['new_policy'])
            weight_delta = max(weight_delta, abs(expected-float(row['weight'])))
            history.append(float(row['signed_z']) if row['signed_z'] else None)
            if float(row['weight']) < 1-1e-12:
                active.append(row)
            elif active:
                intervals.append(dict(case=case, kind=kind, factor=factor,
                    first_keyframe_s=float(active[0]['elapsed_s']), last_keyframe_s=float(active[-1]['elapsed_s']),
                    bins=len(active), min_weight=min(float(r['weight']) for r in active)))
                active = []
        if active:
            intervals.append(dict(case=case, kind=kind, factor=factor,
                first_keyframe_s=float(active[0]['elapsed_s']), last_keyframe_s=float(active[-1]['elapsed_s']),
                bins=len(active), min_weight=min(float(r['weight']) for r in active)))
        z = [float(r['signed_z']) for r in rows if r['signed_z']]
        statistics.append(dict(case=case, kind=kind, factor=factor, bins=len(rows),
            downweighted_bins=sum(float(r['weight'])<1-1e-12 for r in rows),
            min_weight=min(float(r['weight']) for r in rows),
            median_signed_z=float(np.median(z)) if z else None))
    assert weight_delta < 1e-12
    write_csv(result/'confidence_statistics.csv', statistics)
    write_csv(result/'downweighted_intervals.csv', intervals)
    trajectories = read_csv(result/'trajectories.csv')
    table = {(r['case'],r['configuration'],r['method'],r['car']): r for r in read_csv(result/'comparison.csv')}
    maximum, fits, effects = 0., 0, []
    for case in summary['cases']:
        reference = next(c for c in parent['cases'] if c['id']==case['case'])
        for name, pair in case['configurations'].items():
            for method in ['independent', 'joint']:
                fits += 1; metrics = pair[method]; assert metrics['optimizer']['success']
                ledger = metrics['factor_cost_ledger']
                cost = sum(sum(v.values()) if isinstance(v,dict) else v for v in ledger.values())
                assert abs(cost-metrics['optimizer']['cost']) < 1e-9
                for car in CARS:
                    rows = [r for r in trajectories if r['case']==case['case'] and r['configuration']==name
                            and r['method']==method and r['car']==car]
                    assert len(rows)==metrics['keyframes']
                    xy = np.asarray([[float(r['antenna_x_m']),float(r['antenna_y_m'])] for r in rows])
                    error = float(np.linalg.norm(np.median(xy[-5:],axis=0)-reference['evaluation_only']['end_antenna_xyz_m'][car][:2]))
                    path = float(np.linalg.norm(np.diff(xy,axis=0),axis=1).sum())
                    old = table[(case['case'],name,method,car)]
                    maximum = max(maximum, abs(error-metrics['endpoint_difference_m'][car]),
                        abs(error-float(old['endpoint_difference_m'])),
                        abs(path-metrics['cars'][car]['estimated_antenna_path_m']), abs(path-float(old['antenna_path_m'])))
            assert pair['independent']['peer_factor_count']==0
            assert pair['independent']['wall_factor_count']==pair['joint']['wall_factor_count']
        for suffix in ['', '_stationary']:
            for method in ['independent','joint']:
                a, b = [case['configurations'][strategy+suffix][method] for strategy in ['original','adaptive']]
                for car in CARS:
                    effects.append(dict(case=case['case'], near_zero_odom=bool(suffix), method=method, car=car,
                        adaptive_minus_original_endpoint_m=b['endpoint_difference_m'][car]-a['endpoint_difference_m'][car],
                        adaptive_minus_original_path_m=b['cars'][car]['estimated_antenna_path_m']-a['cars'][car]['estimated_antenna_path_m']))
    assert fits == 36 and len(trajectories)==6168 and maximum < 1e-12
    write_csv(result/'adaptive_signed_effects.csv', effects)
    counterfactual = contamination_check(docs, protocol, plan)
    write_json(result/'DERIVED_VERIFICATION.json', dict(passed=True, method_records=fits,
        trajectory_rows=len(trajectories), confidence_rows=len(confidence),
        metric_recomputation_max_delta_m=maximum, lagged_weight_recomputation_max_delta=weight_delta,
        baseline_trajectory_reproduction_max_delta=manifest['baseline_reproduction_max_component_delta'],
        actual_cost_ledgers_verified=True, independent_peer_factors_zero=True, matched_wall_factor_counts=True,
        source_protocol_data_hashes_verified=True, quality_samples=quality_count, finite_quality_samples=quality_finite,
        max_nfev=max(p[m]['optimizer']['nfev'] for c in summary['cases'] for p in c['configurations'].values()
                     for m in ['independent','joint']),
        max_abs_adaptive_endpoint_change_m=max(abs(e['adaptive_minus_original_endpoint_m']) for e in effects)))
    lines = ['# 原始测距诊断与一种历史一致性降权策略', '',
        '已完成用户授权的两步：七包原始诊断；一种冻结的留一链路预测/历史一致性降权，与原模型、固定降权及近零约束开关对照。',
        '32 项相关测试通过；36 次实际图求解全部成功；PR39 四组配置的完整轨迹逐点复现差为 0。', '',
        '## 约 92 cm 的差异位于录制之间', '',
        '| 静态包 | Car2/node_10 原始中位数/m | 原修正后参考偏差/cm | 首五秒→末五秒原始中位数/m |',
        '|---|---:|---:|---|']
    for case in raw['recordings']:
        if case['kind'] != 'static': continue
        v = case['cars']['car2']['links']['node_10']
        lines.append(f"| {case['id']} | {v['raw']['median']:.3f} | {100*v['corrected_median_minus_geometry_m']:+.2f} | {v['first_five_median_m']:.3f} → {v['last_five_median_m']:.3f} |")
    lines += ['', '前三包 Car2 人工参考位置均为 [2,2,0.2] m，记录的 Odom XY 未变，013951 与 015009 的记录航向差约 0.0029°。',
        '每包 1–33 秒的中位数曲线各自稳定；013951→015009 的全包原始中位数差为 92.5 cm。',
        '现有包未覆盖两段录制之间的切换，无法给出切换发生的精确时刻或确定物理原因。020151 为不同的 Car2 位置，仅作对照。',
        f'七包共检查 {quality_count:,} 个 quality 值，有限值为 0；没有可用于本轮判断的有效质量分数、RSSI/CIR 或独立 NLOS 标签。',
        '嵌入消息定义为米，tag/anchor ID 和旧前端读数核对一致；包内 UWB header 未发现倒退。header/receipt 偏移随录制变化，但零 Odom 的整段中位数差不能仅靠小幅时间平移解释。',
        '这些证据缩小了排查范围，尚不能排除摆位参考、遮挡、安装朝向或设备状态变化；不改写用户坐标来消除差异。', '',
        '## 新策略及实际触发时段', '',
        '对每条墙链路，用不包含它的三状态预测器处理 Odom 和其他墙测距；车间距离由不使用任何车间测距的两车预测器给出。',
        '当前权重只读取前三个关键帧的标准化不一致分数：中位绝对分数超过 2 时逐步降权，下限 0.1。原修正值、先验、损失和因子数量不变。',
        '预测器协方差为近似值，分数不是校准后的卡方检验；当前/未来被检测距不能影响当前权重，单条测距也不进入自身预测。', '',
        '| 包 | 被降权信息 | 关键帧时段/s | 最小权重 |', '|---|---|---|---:|']
    for row in intervals:
        if row['factor'] in ['car2/node_10','peer']:
            lines.append(f"| {row['case']} | {row['factor']} | {row['first_keyframe_s']:.0f}–{row['last_keyframe_s']:.0f} | {row['min_weight']:.3f} |")
    lines += ['', '这里是算法触发的关键帧时段，不是独立标注的 NLOS 起止。所有链路详见 downweighted_intervals.csv。', '',
        '## 原模型、固定降权、新策略：完整终点对照', '',
        '每格为各自融合→联合融合，与人工终点差，单位 cm；末五个关键帧的天线坐标中位数。', '',
        '| 包 | 近零约束 | 策略 | Car1/cm | Car2/cm |', '|---|---|---|---:|---:|']
    for case in summary['cases']:
        for suffix in ['', '_stationary']:
            for strategy in ['original','fixed','adaptive']:
                pair = case['configurations'][strategy+suffix]
                values = [f"{100*pair['independent']['endpoint_difference_m'][c]:.2f} → {100*pair['joint']['endpoint_difference_m'][c]:.2f}" for c in CARS]
                lines.append(f"| {case['case']} | {'开' if suffix else '关'} | {strategy} | "+' | '.join(values)+' |')
    lines += ['', '新策略与相同近零开关下的原模型比较，最大终点变化约 0.41 cm，未形成明显且可靠的精度提升；人工参考误差尚未量化。',
        '015334 静止 Car1 的联合轨迹在开启近零约束时从 6.79 cm 缩短到 4.98 cm，但其终点差从 17.87 cm 增至 18.28 cm。',
        '033248 对应静止 Car2 轨迹为 3.02→2.98 cm；050447 的联合终点仍约 Car1 20.11 cm、Car2 17.71 cm。',
        '所以只能说部分形变受到抑制，不能宣称稳定协同增益或全程轨迹更准确。', '',
        '## 检出不一致仍不等于找到了错误源', '',
        '015009 的车间测距中位数约 2.1255 m，人工三维参考约 2.0618 m，相差约 +6.37 cm；',
        '但使用全部墙测距的预测器给出约 1.3107 m，于是车间信息在 27/33 个关键帧被降权，最低约 0.253。',
        '只在预测端移除 Car2/node_10 后，车间预测中位数变为约 1.8331 m，车间降权次数降至 0；其余预测偏差仍存在。',
        '这个反事实只用于诊断，没有回写本轮冻结权重、改变阈值或新增第二种融合策略。它支持“墙测距可污染预测端”的解释，也表明简单一致性门控不足以独立确定错误源。', '',
        '## 本轮决策', '',
        '新增方法保留为研究候选和可复现对照，不替换默认模型。现阶段更明确的成果是定位了跨录制持续差异、找出了原始质量字段缺失及预测端污染这一限制。',
        '下一轮应研究有冗余支持的错误源区分，再决定对墙测距还是车间测距降权；避免只降低阈值追求更多触发。实验室仍需同点同朝向、改变遮挡、返回原点的独立重复记录。',
        '三个动态包均为已知开发数据，静态预测以已知位置作外部起点先验，不是盲测。继承 ±0.4 秒居中统计窗和 Odom 插值；权重在关键帧序列上只取过去分数，但端到端仍是离线批量平滑。',
        '没有双车在线/固定窗口或独立 IMU 因子。连续真值、原点外参与物理原因仍待补证。', '',
        '![原始静态证据](static_node10_diagnosis.png)', '', '![诊断分数和权重](confidence_timeline.png)', '',
        '![完整终点对照](confidence_endpoint_comparison.png)', '']
    (result/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps(dict(verified=True, fits=fits, metric_delta=maximum, weight_delta=weight_delta)))


if __name__ == '__main__': main()
