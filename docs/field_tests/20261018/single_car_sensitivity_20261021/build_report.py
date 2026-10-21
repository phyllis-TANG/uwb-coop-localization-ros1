#!/usr/bin/env python3
"""Present already-computed results; this script never runs the optimizer."""
import argparse
import base64
import csv
import hashlib
import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(map(str, headers)) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def md_inline(text):
    escaped = html.escape(text)
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)


def render_md(markdown):
    """Small safe renderer for this report's headings, tables, paragraphs, fences."""
    lines = markdown.splitlines()
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith('```'):
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith('```'):
                code.append(lines[i]); i += 1
            output.append('<pre><code>' + html.escape('\n'.join(code)) + '</code></pre>')
            i += 1
            continue
        if line.startswith('#'):
            level = min(len(line) - len(line.lstrip('#')), 6)
            output.append(f'<h{level}>' + md_inline(line[level:].strip()) + f'</h{level}>')
            i += 1
            continue
        if line.startswith('| '):
            block = []
            while i < len(lines) and lines[i].startswith('| '):
                block.append([c.strip() for c in lines[i].strip().strip('|').split('|')]); i += 1
            output.append('<div class="tablewrap"><table><thead><tr>' + ''.join('<th>' + md_inline(c) + '</th>' for c in block[0]) + '</tr></thead><tbody>')
            for row in block[2:]:
                output.append('<tr>' + ''.join('<td>' + md_inline(c) + '</td>' for c in row) + '</tr>')
            output.append('</tbody></table></div>')
            continue
        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(('#', '| ', '```')):
            paragraph.append(lines[i]); i += 1
        output.append('<p>' + md_inline(' '.join(paragraph)) + '</p>')
    return '\n'.join(output)


def main(args):
    summary = json.loads((ROOT / 'results/summary.json').read_text())
    validation = json.loads((ROOT / 'results/test_verification.json').read_text())
    if not validation['successful']:
        raise ValueError('Tests must pass before report generation')
    endpoint = {(r['run'], r['range_scale'], r['odom_translation_scale']): r for r in summary['endpoints']}
    static = summary['stationary']
    grid_rows = []
    for r in [.5, 1., 2.]:
        for o in [.5, 1., 2.]:
            a, b = endpoint[('004023', r, o)], endpoint[('005135', r, o)]
            grid_rows.append([f'{r:g}', f'{o:g}', f'{100 * a["endpoint_difference_m"]:.2f}',
                              f'{100 * b["endpoint_difference_m"]:.2f}',
                              f'{100 * a["scatter_about_median_RMS_m"]:.2f}',
                              f'{100 * b["scatter_about_median_RMS_m"]:.2f}'])
    grid_table = table(['距离 σ 倍数', '平移 σ 倍数', '004023 终点差/cm', '005135 终点差/cm',
                        '004023 末端散布/cm', '005135 末端散布/cm'], grid_rows)
    static_rows = []
    phase_names = {'initial': '初始静止', 'idle_before_turn': '转弯前静止',
                   'idle_after_turn': '转弯后静止', 'endpoint': '末端静止'}
    for run in ['004023', '005135']:
        for phase in phase_names:
            selected = [s for s in static if s['run'] == run and s['phase'] == phase]
            base = next(s for s in selected if s['range_scale'] == s['odom_translation_scale'] == 1.)
            values = [s['scatter_about_median_RMS_m'] * 100 for s in selected]
            static_rows.append([run, phase_names[phase], base['samples'],
                                f'{100 * base["scatter_about_median_RMS_m"]:.3f}',
                                f'{min(values):.3f}–{max(values):.3f}'])
    static_table = table(['记录', '阶段', '每组状态数', '原参数散布/cm', '九组散布范围/cm'], static_rows)
    residual_rows = []
    for row in summary['residuals']:
        residual_rows.append([row['run'], row['cell'], f'{100 * row["range_RMS_m"]:.3f}',
                              f'{100 * row["odom_step_translation_vector_RMS_m"]:.3f}',
                              f'{row["odom_step_yaw_RMS_deg"]:.4f}'])
    residual_table = table(['记录', '组合', '测距拟合 RMS/cm', '每步平移改变量 RMS/cm',
                            '每步 yaw 改变量 RMS/deg'], residual_rows)
    context_rows = []
    for run in ['004023', '005135']:
        row = endpoint[(run, 1., 1.)]
        values = [e['endpoint_difference_m'] * 100 for e in summary['endpoints'] if e['run'] == run]
        context_rows.append([run, f'{100 * row["A_endpoint_difference_m"]:.2f}',
                             f'{100 * row["U_endpoint_difference_m"]:.2f}',
                             f'{100 * row["endpoint_difference_m"]:.2f}', f'{min(values):.2f}–{max(values):.2f}'])
    context_table = table(['记录', 'A 对齐 Odom/cm', 'U 既有 UWB-only/cm', 'F 原融合/cm', '九组融合范围/cm'], context_rows)
    max_shift = max(e['trajectory_displacement_from_F_max_m'] for e in summary['endpoints'])
    max_cost_diff = max(e['reconstructed_cost_abs_difference'] for e in summary['residuals'])
    report = f'''# 单车权重敏感性：完整九组诊断

日期：2026-10-21。基线：main `21b17f344b58b72c2bd00c9834f89e5d0a9b1bc5`，PR #32 已合并。

## 结论先行

这一轮没有发现“参数稍变，两个终点就整体失稳”的现象，但不能据此说整条轨迹已经准确或参数已验证。第一条记录的终点差始终约 11.5–13.1 cm，第二条为 3.6–6.8 cm。继续细磨权重可能改变终点数字，却不足以解释或解决目前的参考点、外参与阶段性测距不一致问题。

全轨迹相对原融合的最大改变量可达 {100 * max_shift:.2f} cm，即使终点变化没有那么大。由于没有连续位置真值，不知道这个改变量是修正还是偏离。不能用终点、平滑程度或低拟合残差替代途中精度验证。

建议保留原参数作为可复现基线，不从本轮选“最佳参数”。下一步优先核实车体参考点与天线外参，然后用具有独立起点/中间点/终点和朝向记录的新重复试验验证冻结方案；不继续以这两个已看过的终点作为调参目标。本轮没有修改在线节点或默认配置，没有新增 IMU 因子。

## 1. 先做了什么核查

主分支与 PR31/PR32 的 48 个普通文件 Git blob SHA 逐一相同。依赖文件自身的 SHA-256 清单复核 30 + 16 个文件；两个 decoded cache 哈希匹配；原参数 `(1,1)` 的车体状态、天线状态、终点差和所有静止散布均逐数复现旧结果，差值为 0。

天线量测坐标轴已明确为 x 前、y 左，不需要重新猜测符号。真正未确认的是：测量时的“近似车体几何中心”是否等于 `base_footprint` 原点。两个 bag 没有 TF；本仓库没有车端底盘驱动及 `base_serial.launch` 的实现。`odom_combined` 是启动参数指定的名字，不能据此认定 IMU 已在上游融合。

详细证据和最小补充材料见 `REFERENCE_AUDIT.md`。本轮保持旧外参假设，没有借助终点表现反推外参。以下全部数值以该假设为条件。

## 2. 冻结方案与边界

仅改变距离噪声尺度与 Odom 平移噪声尺度，各取 0.5、1、2 倍，共 9 组 × 2 个 bag = 18 次求解。实际距离 σ 为 0.10/0.20/0.40 m；实际平移 σ 为 0.015/0.030/0.060 m × √dt_seconds（每个 XY 分量）。σ 越小，该项约束越强。

yaw σ 固定为 2° × √dt_seconds；起点位置/朝向先验仍为 0.20 m/5°。P1 标定偏置、天线高度、旋转杆臂、候选起点、初始朝向、时间戳处理、1 秒关键帧、四条测距中位数、优化器初值和停止条件全部保持不变。没有新增过滤、剔除某个节点、对齐终点或重估偏置。

需要特别注意：原求解器对标准化测距残差施加 delta=1 的 pseudo-Huber。因此改变距离 σ 同时改变鲁棒损失在物理米制下的过渡尺度，本轮不是“只变高斯权重、鲁棒阈值完全固定”的试验。平移 σ 不改变 yaw σ，所以相同距离/平移倍数比也不保证目标函数等价。

终点仍使用最终前进停止后 `[2,7)` 的五个关键帧，分别对估计天线 X/Y 取中位数，再与人工量测的天线终点求二维距离。人工参考的不确定度未量化。这两个 bag 早已被分析过，本轮只能称回顾性开发诊断，不能称未见测试、统计显著改进或在线结果。

## 3. 全部九组终点与末端静止散布

{grid_table}

`(1,1)` 是原参数，并不是搜索得出的新选择。没有隐藏变差的组合，也没有追加更有利的网格。散布为估计位置相对本窗口中位数的 RMS，不是相对真值的位置 RMSE。

此前冻结的对照数值保持如下：

{context_table}

U 使用原 σ=0.20 m 的逐帧 UWB-only；本轮并未为三个距离 σ 各重做 U，所以该列只作既有背景，不能把全网格与这一个 U 列比较后宣称隔离了融合收益。F 是全轨迹离线批处理，会用未来观测；U 不使用 Odom/时间平滑，信息预算也不同。A 的房间坐标对齐依赖候选起点，仍不是独立精度基准。

## 4. 为什么权重更“好看”不等于模型更正确

以 `005135` 为例，固定平移 σ=0.03 m，把距离 σ 从 0.40 降到 0.10 m（加强测距约束）时：测距拟合 RMS 从 9.66 cm 降到 8.50 cm，但终点差从 3.64 cm 上升到 6.62 cm。更贴近 UWB 数据不保证更接近人工位置参考，尤其数据里还可能含有未建模系统误差。

同样，Odom 平移 σ 改变也可能将更少的平移改变量换成更多 yaw 调整；即便 yaw σ 没有改，状态间仍然耦合。下表同时保留全部物理单位残差，避免只看某一项。每步改变量表示优化后的相邻车体增量与原 Odom 增量之差，不是实际车体运动误差。

{residual_table}

残差由同一批用于优化的数据计算，不能当独立测试误差。不同 σ 的目标函数数值不可直接排名；低总 cost 可能只是尺度变大。也不能根据这些结果判定哪个传感器绝对正确。

## 5. 静止阶段是否一并改善

{static_table}

短窗口只有 3–5 个状态，统计量有限。部分参数能减小某些窗口的散布，却不保证其它窗口或终点同时改善；缩小散布本身也可能只意味着更强平滑。全部 72 条窗口的首末位移、散布和路径长度都在 `stationary_diagnostics.csv`，没有只保留有利窗口。

## 6. 数值与复核结果

18/18 次求解返回 success，全部按原 `ftol=1e-7` 停止（status=2），不是达到全局最优的证明。原算法的一阶最优性指标、迭代次数和停止原因已完整保留，不把 success 等同统计正确或全局唯一解。

通过 {validation['tests_run']} 项独立单元/CSV 算术复核：杆臂旋转、车体增量坐标、角度归一、散布定义、半开区间、九组完整性、全部 18 个终点、72 个静止窗口、1,674 条步进残差以及相对冻结基线的改变量。独立重建原目标函数与优化器报告的最大绝对差为 {max_cost_diff:.3g}。测试全部通过，无失败单元、无未收敛组合。

本轮不声称重跑全仓库旧测试，不评估真实在线延迟，也不将 18 次求解当作 18 条独立采集轨迹。

## 7. 最适合的下一步

第一，补齐参考点证据。只读取得实际底盘 launch、Odom/IMU 发布及积分代码和相关静态变换，确定 `base_footprint` 的物理定义，以及 Odom 是否已用同源陀螺仪；核实后再决定是否需要变更杆臂或新增独立 IMU 因子。当前不能断言这两个未知项就是剩余误差的原因。

第二，针对上一轮转弯前后出现的链路不一致做可辨识的验证。需独立记录转向前后天线中心和车体方向，或在同一独立量测位置重复多个朝向，区分几何运动、外参误差和朝向/遮挡相关测距变化。此时才有依据决定是否需要链路/朝向相关噪声或偏置模型；不先按这两个终点删节点、加修正项。

第三，将标定、模型开发和最终验证分开。用现有数据形成模型与固定参数，再用未参与选择的新重复轨迹验证；每次记录天线起点、转弯处停留点和终点以及测量不确定度，尽可能增加独立中间检查。若要宣称连续轨迹精度，还需连续独立真值。单车模型与误差来源弄清后，其单车因子可复用于双车协同；不能预先保证双车精度。

本轮按冻结方案到此停止：不选新默认参数，不扩网格，不改在线配置，不连接小车，不自动上传或合并 PR。新代码和结果按普通文件保留，原始数据及旧工作区修改均未覆盖。

## 8. 可追溯文件

实际求解：`analyze_sensitivity.py`；独立验证：`test_sensitivity.py`；冻结方案：`protocol.json`；外参证据核查：`REFERENCE_AUDIT.md`；复现说明：`README.md`。全部结果在 `results/`，优化器记录和检查在 JSON 中。`SHA256SUMS.txt` 覆盖本轮普通文件，但不包含自身和报告生成后的验证清单 `report_verification.json`，避免循环引用。

输入数据未重新拟合，两个原始 bag 的哈希为 `72d4a051005b0b109461842b6489aa2d07b08dd6f6e750c4b9a82aac8d8e1d82` 和 `63880adf78d5f07a9b12a87f7352f49e8f7be82d223bcdf60d96e257ba38b2ff`。本轮使用已核对哈希的 decoded cache，不重新解码 bag。冻结方案 SHA-256：`048de25b3fb93344f0863d0c62245ada0b9aaf4f7cde76d7ef03e66acc78cd35`。
'''
    (ROOT / 'REPORT.md').write_text(report)
    files = sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                   and p.name not in ['SHA256SUMS.txt', 'report_verification.json'])
    sums = ''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(ROOT).as_posix() + '\n' for p in files)
    (ROOT / 'SHA256SUMS.txt').write_text(sums)
    files.append(ROOT / 'SHA256SUMS.txt')
    if args.html_output:
        downloads = []
        attachment_hashes = {}
        for file in files:
            data = file.read_bytes()
            relative = file.relative_to(ROOT).as_posix()
            attachment_hashes[relative] = hashlib.sha256(data).hexdigest()
            mime = 'text/csv' if file.suffix == '.csv' else 'application/json' if file.suffix == '.json' else 'text/plain'
            downloads.append('<li><a download="' + html.escape(file.name, quote=True) + '" href="data:' + mime + ';base64,' + base64.b64encode(data).decode() + '">' + html.escape(relative) + '</a> <small>' + str(len(data)) + ' bytes</small></li>')
        document = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>单车九组权重敏感性诊断</title><style>
body{font-family:system-ui,-apple-system,"Noto Sans CJK SC",sans-serif;color:#172334;line-height:1.75;max-width:1100px;margin:36px auto;padding:0 22px;background:#fbfcfe}h1{font-size:1.9rem;color:#173e66}h2{margin-top:2.2em;border-top:1px solid #d9e2ee;padding-top:.8em;color:#173e66}p{max-width:98ch}code{background:#edf2f7;padding:2px 5px;border-radius:4px;font-size:.85em;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#edf2f7;padding:18px}.tablewrap{overflow-x:auto}table{border-collapse:collapse;min-width:640px;width:100%;font-size:.9rem;margin:20px 0}th,td{padding:9px 12px;border-bottom:1px solid #dbe3ec;text-align:left;font-variant-numeric:tabular-nums}th{background:#e7eef8}tr:nth-child(even){background:#f0f4f9}small{color:#586a80}a{color:#1459a0}summary{cursor:pointer;font-weight:600}li{margin:6px 0}.meta{color:#586a80;border-left:4px solid #6a8db5;padding:10px 16px;background:#edf2f9}
</style></head><body><div class="meta">固定九组 · 两条历史轨迹 · 不选择新参数 · 非独立最终测试</div>'''
        document += render_md(report)
        document += '<h2>附：外参证据核查</h2>' + render_md((ROOT / 'REFERENCE_AUDIT.md').read_text())
        document += '<h2>普通文件下载</h2><p>每个链接下载一个原格式文件，无须解压；可按显示路径放回目录。原始 bag 和历史输入归档未重复包含。</p><ul>' + ''.join(downloads) + '</ul>'
        document += '<h2>来源</h2><p><a href="https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/32">已合并 PR #32</a> · <a href="https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/21b17f344b58b72c2bd00c9834f89e5d0a9b1bc5/docs/CAR2_QUICK_START.md">冻结版本启动记录</a></p></body></html>'
        args.html_output.write_text(document)
        from html.parser import HTMLParser
        class AttachmentParser(HTMLParser):
            def __init__(self):
                super().__init__(); self.attachments = []
            def handle_starttag(self, tag, attributes):
                values = dict(attributes)
                if tag == 'a' and values.get('href', '').startswith('data:'):
                    self.attachments.append(base64.b64decode(values['href'].split(',', 1)[1], validate=True))
        parser = AttachmentParser(); parser.feed(document)
        assert len(parser.attachments) == len(files)
        for file, payload in zip(files, parser.attachments):
            assert file.read_bytes() == payload, str(file)
        assert len(endpoint) == 18 and len(static) == 72
        verification = {'html_output': args.html_output.name, 'html_sha256': hashlib.sha256(args.html_output.read_bytes()).hexdigest(),
                        'embedded_ordinary_files': len(files), 'all_embedded_bytes_match_sources': True,
                        'endpoint_table_cells': 18, 'stationary_windows': 72,
                        'attachment_sha256': attachment_hashes}
        (ROOT / 'results/report_verification.json').write_text(json.dumps(verification, indent=2) + '\n')
        print(json.dumps({k: v for k, v in verification.items() if k != 'attachment_sha256'}, indent=2))
    print('REPORT_READY', ROOT / 'REPORT.md')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html-output', type=Path)
    main(parser.parse_args())
