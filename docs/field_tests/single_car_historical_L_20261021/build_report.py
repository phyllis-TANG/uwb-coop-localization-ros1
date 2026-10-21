#!/usr/bin/env python3
"""Derive auditable summaries and present frozen historical rerun outputs."""
import argparse
import base64
import collections
import csv
import hashlib
import html
import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
LABELS = {'oct11_keyboard_083512': '10.11 manual 083512',
          'oct11_auto_091958': '10.11 auto 091958', 'oct17_auto_061540': '10.17 auto 061540'}


def read(name):
    with (ROOT / 'results' / name).open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(name, rows):
    with (ROOT / 'results' / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def table(headings, rows):
    return '\n'.join(['| ' + ' | '.join(headings) + ' |', '| ' + ' | '.join(['---'] * len(headings)) + ' |'] +
                     ['| ' + ' | '.join(str(x) for x in row) + ' |' for row in rows])


def render_md(text):
    def inline(value):
        return re.sub(r'`([^`]+)`', r'<code>\1</code>', html.escape(value))
    lines = text.splitlines(); output = []; i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1; continue
        if line.startswith('```'):
            code = []; i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                code.append(lines[i]); i += 1
            output.append('<pre><code>' + html.escape('\n'.join(code)) + '</code></pre>'); i += 1; continue
        if line.startswith('#'):
            level = min(len(line) - len(line.lstrip('#')), 6)
            output.append(f'<h{level}>' + inline(line[level:].strip()) + f'</h{level}>'); i += 1; continue
        image = re.fullmatch(r'!\[(.*?)\]\((.*?)\)', line)
        if image:
            path = ROOT / image.group(2)
            output.append('<img style="width:100%" alt="' + html.escape(image.group(1), quote=True) + '" src="data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode() + '">')
            i += 1; continue
        if line.startswith('| '):
            block = []
            while i < len(lines) and lines[i].startswith('| '):
                block.append([x.strip() for x in lines[i].strip().strip('|').split('|')]); i += 1
            output.append('<div class="tablewrap"><table><thead><tr>' + ''.join('<th>' + inline(x) + '</th>' for x in block[0]) + '</tr></thead><tbody>')
            output.extend('<tr>' + ''.join('<td>' + inline(x) + '</td>' for x in row) + '</tr>' for row in block[2:])
            output.append('</tbody></table></div>'); continue
        para = [line]; i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(('#', '| ', '```', '![')):
            para.append(lines[i]); i += 1
        output.append('<p>' + inline(' '.join(para)) + '</p>')
    return '\n'.join(output)


def main(args):
    out = ROOT / 'results'
    summary = json.loads((out / 'summary.json').read_text())
    verification = json.loads((out / 'verification.json').read_text())
    if not verification['success']:
        raise ValueError('Independent checks did not pass')
    tracks = read('trajectories.csv'); inputs = read('keyframe_inputs.csv'); ranges = read('range_residuals.csv')
    static = {(r['case'], r['method'], r['window']): r for r in summary['stationary']}
    displacement = []
    for row in summary['endpoints']:
        start = static[row['case'], row['method'], 'initial']
        dx = row['median_x_m'] - start['median_x_m']; dy = row['median_y_m'] - start['median_y_m']
        ref_dx = row['reference_x_m'] - start['reference_x_m']; ref_dy = row['reference_y_m'] - start['reference_y_m']
        displacement.append({'case': row['case'], 'method': row['method'], 'window': row['window'],
            'estimated_delta_x_m': dx, 'estimated_delta_y_m': dy, 'reference_delta_x_m': ref_dx,
            'reference_delta_y_m': ref_dy, 'displacement_vector_difference_m': math.hypot(dx - ref_dx, dy - ref_dy)})
    write_csv('displacement_metrics.csv', displacement)
    reference_rows, fit_rows = [], []
    for case in summary['cases']:
        cid = case['case']['id']; day = case['case']['day']
        cfg = json.loads((out / 'evidence' / (day + '_config.json')).read_text())
        height = case['run']['start_antenna_xyz_m'][2]
        for window in case['window_checks']:
            name = window['window']; left, right = window['bounds_elapsed_s']
            ref = case['run']['start_antenna_xyz_m'] if name == 'initial' else case['run']['end_antenna_xyz_m']
            for node, anchor in sorted(cfg['anchors_xyz_m'].items()):
                selected = [r for r in inputs if r['case'] == cid and r['node'] == node and left <= float(r['elapsed_s']) < right]
                geom = math.dist(anchor, ref)
                values = [float(r['range_m']) - float(r['full_P1_bias_m']) for r in selected]
                reference_rows.append({'case': cid, 'window': name, 'node': node, 'keyframe_bins': len(values),
                    'reference_geometry_m': geom, 'corrected_bin_median_m': float(np.median(values)) if values else '',
                    'corrected_minus_reference_geometry_m': float(np.median(values) - geom) if values else '',
                    'reference_not_continuous_truth': True})
        for method in ['G_raw', 'G_old', 'G_new0', 'G_P1', 'G_assumedL']:
            for name in ['whole_graph'] + [w['window'] for w in case['window_checks']]:
                window = next((w for w in case['window_checks'] if w['window'] == name), None)
                for node in sorted(cfg['anchors_xyz_m']):
                    selected = [float(r['residual_m']) for r in ranges if r['case'] == cid and r['method'] == method and r['node'] == node and
                        (window is None or window['bounds_elapsed_s'][0] <= float(r['elapsed_s']) < window['bounds_elapsed_s'][1])]
                    fit_rows.append({'case': cid, 'method': method, 'window': name, 'node': node, 'samples': len(selected),
                        'signed_median_m': float(np.median(selected)) if selected else '',
                        'abs_median_m': float(np.median(np.abs(selected))) if selected else '',
                        'RMS_m': float(np.sqrt(np.mean(np.square(selected)))) if selected else ''})
    write_csv('reference_range_residuals.csv', reference_rows)
    write_csv('residual_by_link_window.csv', fit_rows)
    derived = {'source_summary_sha256': hashlib.sha256((out / 'summary.json').read_bytes()).hexdigest(),
               'displacement_rows': len(displacement), 'reference_range_rows': len(reference_rows),
               'link_window_fit_rows': len(fit_rows), 'includes_unavailable_link_rows': True,
               'derivation_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    write_json(out / 'derived_verification.json', derived)
    # Scientific figure: all output points shown, no planned L asserted as truth.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.6))
    for axis, case in zip(axes, summary['cases']):
        cid = case['case']['id']
        for method, label, color, style in [('U_P1', 'P1 UWB-only', '#dc9850', ':'), ('A', 'Aligned Odom', '#477dad', '--'),
                ('G_P1', 'Graph, historical zero lever', '#228568', '-'), ('G_assumedL', 'Graph, assume base at chassis center', '#9b5c9c', '--')]:
            selected = [r for r in tracks if r['case'] == cid and r['method'] == method]
            axis.plot([float(r['antenna_x_m']) for r in selected], [float(r['antenna_y_m']) for r in selected],
                      color=color, linestyle=style, linewidth=1.5 if method != 'U_P1' else .8,
                      alpha=.9 if method != 'U_P1' else .55, label=label)
        start, end = case['run']['start_antenna_xyz_m'], case['run']['end_antenna_xyz_m']
        axis.scatter(start[0], start[1], marker='o', facecolors='none', edgecolors='black', s=70, zorder=5, label='Marked antenna start')
        axis.scatter(end[0], end[1], marker='*', color='black', s=110, zorder=5, label='Measured antenna end')
        axis.set_title(LABELS[cid]); axis.set_xlabel('Room X (m)'); axis.set_ylabel('Room Y (m)')
        axis.set_aspect('equal', adjustable='datalim'); axis.grid(alpha=.22)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3, fontsize=9, frameon=False)
    fig.suptitle('Historical L recordings: frozen rerun, conditional geometry comparison', fontsize=13)
    fig.tight_layout(rect=[0, .14, 1, .94]); fig.savefig(out / 'trajectories.png', dpi=170); plt.close(fig)
    primary = []
    secondary = []
    start_rows = []
    all_rows = []
    for case in summary['cases']:
        cid = case['case']['id']; short = LABELS[cid]
        archived = next(r for r in summary['checks']['legacy_reproduction'] if r['case'] == cid)
        get = lambda method, window='historical_tail5': static[cid, method, window]
        primary.append([short, f'{100 * archived["archived_endpoint_difference_m"]:.2f}',
                        f'{100 * get("G_P1")["reference_difference_m"]:.2f}',
                        f'{100 * get("G_assumedL")["reference_difference_m"]:.2f}',
                        f'{100 * get("U_P1")["reference_difference_m"]:.2f}',
                        f'{100 * get("A")["reference_difference_m"]:.2f}'])
        secondary.append([short] + [f'{100 * get(m,"after_stop_2_7")["reference_difference_m"]:.2f}' for m in ['G_P1','G_assumedL','U_P1','A']])
        start_rows.append([short] + [f'{100 * get(m,"initial")["reference_difference_m"]:.2f}' for m in ['G_old','G_P1','G_assumedL','U_P1']])
        for method in ['A','U_raw','U_P1','G_raw','G_old','G_new0','G_P1','G_assumedL']:
            row = get(method)
            all_rows.append([short, method, f'{100 * row["reference_difference_m"]:.3f}',
                             f'{100 * row["scatter_about_median_RMS_m"]:.3f}', row['samples']])
    ptable = table(['记录', '旧归档融合/cm', '新版零杆臂/cm', '假设两中心重合/cm', '匹配纯UWB/cm', '对齐Odom/cm'], primary)
    stable = table(['记录', '新版零杆臂/cm', '假设两中心重合/cm', '匹配纯UWB/cm', '对齐Odom/cm'], secondary)
    itable = table(['记录', '旧版复跑/cm', '新版零杆臂/cm', '假设两中心重合/cm', '匹配纯UWB/cm'], start_rows)
    full_table = table(['记录', '方法', '末尾窗终点差/cm', '末尾窗散布/cm', '状态数'], all_rows)
    marked_rows = [[LABELS[r['case']], r['node'], r['keyframe_bins'],
                    f'{r["corrected_minus_reference_geometry_m"]:.3f}' if r['keyframe_bins'] else '无该链路']
                   for r in reference_rows if r['window'] == 'initial']
    marked_table = table(['记录', '链路', '初始关键帧数', '校正测距减标记起点几何距离/m'], marked_rows)
    repro_max = max(r['absolute_difference_m'] for r in summary['checks']['legacy_reproduction'])
    report = f'''# 三个历史 L 型包：固定方案复跑结果

日期：2026-10-21。代码核查基线 main `ba16d58a08148531db136c4a96e289161dc9f1c4`。这是回顾性的跨录包开发验证。

计算后补充：用户确认 UWB 在车上的安装位置始终未改变，因此不再把“历史天线是否移动”列为未知。10.18 测量的是相对近似几何中心的偏移；仍需核实该中心与 Odom 车体参考点是否重合。详见 `MOUNT_USER_CONFIRMATION_20261021.md`。本次更新解释，原冻结方案与数值结果保留。

## 结论

三个包已完成全部 15 次图优化，均返回成功；7 项独立数值检查通过。新版核心求解器在保留历史零杆臂和相同偏置时，与旧版的全部状态逐数相同。重新核对全精度静态 P1 校正后，三个终点差约为 22.61、5.42、9.04 cm，未出现新的明显改善。

将相对几何中心量得的天线偏移作为 Odom 车体参考点到天线的杆臂，末尾窗口终点差约为 22.61、5.42、9.04 cm，同样没有明显改善。用户已确认安装未变；这组计算的剩余条件是两参考点重合。该关系未被独立核实，因此这些数值用于检验参考点假设的影响，不能据此宣布该外参正确。

这次结果说明：旧实验本来已经做过静态偏置校正；把同一标定方法重新运行，或者完善杆臂表达，并不会自动再次产生此前零偏置对照中那么大的收益。当前限制集中在跨位置/朝向的测距一致性、异常约束和未验证的几何前提，不能只靠末端数字或静止平滑程度判定问题已解决。

## 1. 主评价：严格保留历史末尾窗口

{ptable}

旧归档融合是历史静态校正图；新版零杆臂指 `G_P1`，使用该安装时期重新核对的全精度 P1 偏置，保留历史零水平杆臂近似。假设两中心重合指 `G_assumedL`，将几何中心到天线的 `[0.12,-0.08] m` 同时当作 Odom 车体参考点到天线的偏移。匹配纯 UWB 指 `U_P1`，在同一批关键帧与校正测距中位数上独立鲁棒求解，不用 Odom、终点或时间平滑。

对齐 Odom 使用标记起点和近似初始朝向，其结果依赖这些前提；起始误差为零是构造结果，不构成独立定位验证。新版图没有在三个包上稳定优于这一对照。图与纯 UWB 也没有一致的末端收益；图会使用整段未来信息，纯 UWB 不使用，不能据此声称同等信息条件下的普遍优势。

10.11 两包每个关键帧仅有 N10/N2/N3 三条可用测距，N8 没有被补造；10.17 每帧有四条。三个包分别为 117、176、132 个状态。旧报告的末尾五秒在这些关键帧上均只有 4 个状态，不能把它说成五次独立位置测量。

## 2. 补充评价：统一取最后运动停止后 [2,7)

{stable}

该窗口由最后非零运动指令和随后零指令确定，每个包完整覆盖 5 个关键帧；没有按误差大小挑选。三个窗口内 Odom 路径和 yaw 变化为零，未出现非零运动指令；这些支持静止判断，仍不能代替独立物理真值。

两种评价窗口都会保留。10.11 自动包在两个窗口下约为 4–5 cm；手动包仍约 21–23 cm；10.17 仍约 9–10 cm。换成统一停止窗口也没有改变本轮主要判断。

## 3. 只看终点会漏掉什么

初始窗口相对标记天线起点的差值如下：

{itable}

10.17 包末端约差 9 cm，但图的初始位置仍偏约 60 cm，因而不能把该包描述为全程达到 9 cm。假设历史杆臂后，初始差值约为 61.5 cm，未消除这个问题。10.11 手动包的图虽然初始位置较接近标记起点，终点仍出现约 22.6 cm 的偏差。

下表直接用初始窗口中的测距关键帧中位数减去标记天线起点对应的几何距离，使用本场次 P1 校正，独立于图优化输出：

{marked_table}

10.17 的 N10 初始超差约 +2.066 m，其余三链路接近标记几何；10.11 手动包 N2 初始约 +0.418 m。样本窗口短，标记起点的测量不确定度也未量化，这些是明显的不一致证据，不能仅凭此确认遮挡、朝向、设备或某一种故障原因。它们也表明静态固定偏置不足以覆盖全部运行条件。添加一个 14 cm 左右的假设水平杆臂，并不能解释/消除 2 m 量级的初始链路差。

## 4. 所有方法的主窗口结果

{full_table}

`G_raw` 到 `G_P1` 是零偏置到静态校正的控制对照，表明校正仍然重要；这项收益历史上已经存在。`G_old` 与 `G_new0` 是完全相同输入和标定下的新旧代码等价对照；`G_P1` 只是将原 P1 舍入数值换回全精度。10.11 最大偏置舍入差约 0.343 mm，10.17 约 0.00051 mm，不能把这类小数变化当作算法提升。

散布是相对本窗口估计位置中位数的 RMS，不是位置真值误差。约 0.02 cm 的末端散布并不表示约 0.02 cm 的定位精度。

## 5. 轨迹图

![全部历史轨迹与条件性外参对照](results/trajectories.png)

只标出已有标记起点和人工终点，没有把计划 L 折线画成全程真值。全轨迹展示用于观察估计之间的差异，不能计算连续轨迹准确度。条件性杆臂会改变部分中间状态，即使末端差值近似不变。

## 6. 复现与检查

主分支 9 个源文件/配置/旧结果的 Git blob 字节核查通过。三个 L bag 与两个独立静态标定 bag 的哈希核对通过，10.11 与 10.17 使用各自的锚点和标定，未跨安装混用。

10.11 两个旧终点结果精确复现；10.17 旧终点最大复现差为 {repro_max:.3g} m。10.17 原归档是 Python2/NumPy1.13.3/SciPy0.19.1，本轮是 Python3/NumPy2.3.5/SciPy1.17.0；该数值差不能当作算法收益。现代运行环境下，新旧求解器零杆臂的完整状态差为 0。

独立复核从普通 CSV 重建全部 48 条终点记录、72 条静止窗口、3,400 条轨迹状态及 7,035 条物理测距残差；物理残差重建的最大差为 {verification['max_independent_range_difference_m']:.3g} m。原算法的收敛停止不代表达到全局最优或统计模型正确。

`displacement_metrics.csv` 同时保留起终点位移向量差；`residual_by_link_window.csv` 保留所有链路在全程和各窗口的拟合残差，含缺失链路；`reference_range_residuals.csv` 保留已知参考点的测距差。所有组合都已保存，没有删去变差的假设或异常包。

## 7. 对下一步工作的影响

目前五个纯单车 L 形包已各有离线分析，用户确认天线安装未变。相对几何中心的天线偏移可按这一安装历史沿用，但几何中心与 Odom 车体参考点的关系仍未知，因此不能把五包直接称为完全验证了同一个已测量的 Odom—天线外参模型。

已有证据支持优先研究测距质量判断和异常约束管理：10.17 N10 的初始稳定大偏差、10.11 手动包的链路变化是应保留的困难样例。后续可以用事先冻结、与终点无关的规则做新对照，比较全程状态、起终点、缺测可用性及是否引入新的错误；这轮未新增门限或按终点挑规则。

同时补齐实际底盘 Odom/IMU 代码与车体参考点定义，确定几何中心到该参考点的变换。在线因果回放可以先做软件准备，但不能直接继承这轮批处理的准确度承诺。最终泛化评估仍需未用于选择的新数据与独立参考。本轮保持原始 bag、旧结果和默认配置，尚未发布新 PR。
'''
    (ROOT / 'REPORT.md').write_text(report)
    files = sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                   and 'scratch_inputs' not in p.parts and p.suffix != '.bag'
                   and p.name not in ['SHA256SUMS.txt', 'report_verification.json'])
    sums = ''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(ROOT).as_posix() + '\n' for p in files)
    (ROOT / 'SHA256SUMS.txt').write_text(sums); files.append(ROOT / 'SHA256SUMS.txt')
    if args.html_output:
        downloads = []
        for file in files:
            data = file.read_bytes(); relative = file.relative_to(ROOT).as_posix()
            mime = 'image/png' if file.suffix == '.png' else 'text/plain'
            downloads.append('<li><a download="' + html.escape(file.name, quote=True) + '" href="data:' + mime + ';base64,' + base64.b64encode(data).decode() + '">' + html.escape(relative) + '</a> <small>' + str(len(data)) + ' bytes</small></li>')
        document = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>三个历史 L 型包复跑结果</title><style>
body{font-family:system-ui,-apple-system,"Noto Sans CJK SC",sans-serif;color:#172334;line-height:1.75;max-width:1150px;margin:32px auto;padding:0 22px;background:#fbfcfe}h1{font-size:1.9rem;color:#173e66}h2{margin-top:2.1em;border-top:1px solid #d9e2ee;padding-top:.8em;color:#173e66}p{max-width:104ch}code{background:#edf2f7;padding:2px 5px;border-radius:4px;font-size:.86em;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#edf2f7;padding:18px}.tablewrap{overflow-x:auto}table{border-collapse:collapse;min-width:650px;width:100%;font-size:.88rem;margin:20px 0}th,td{padding:9px 10px;border-bottom:1px solid #dbe3ec;text-align:left;font-variant-numeric:tabular-nums}th{background:#e7eef8}tr:nth-child(even){background:#f0f4f9}small{color:#586a80}a{color:#1459a0}li{margin:6px 0}.meta{color:#586a80;border-left:4px solid #6a8db5;padding:10px 16px;background:#edf2f9}
</style></head><body><div class="meta">三个历史录包 · 固定参数 · 独立数值复核 · 历史外参条件性对照</div>'''
        document += render_md(report) + '<h2>普通文件下载</h2><p>代码、配置、原始计算结果与派生统计均可单独下载，无需解压。bag 副本不在附件中。</p><ul>' + ''.join(downloads) + '</ul></body></html>'
        args.html_output.write_text(document)
        from html.parser import HTMLParser
        class Parser(HTMLParser):
            def __init__(self):
                super().__init__(); self.files = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'a' and attrs.get('href', '').startswith('data:'):
                    self.files.append(base64.b64decode(attrs['href'].split(',', 1)[1], validate=True))
        parser = Parser(); parser.feed(document)
        assert len(parser.files) == len(files)
        for path, content in zip(files, parser.files):
            assert path.read_bytes() == content
        record = {'html_sha256': hashlib.sha256(args.html_output.read_bytes()).hexdigest(),
                  'html_file': args.html_output.name, 'attachments': len(files), 'all_attachment_bytes_match': True,
                  'report_source_sha256': hashlib.sha256((ROOT / 'REPORT.md').read_bytes()).hexdigest()}
        write_json(out / 'report_verification.json', record); print(json.dumps(record, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html-output', type=Path)
    main(parser.parse_args())
