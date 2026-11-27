# 双车 UWB 协同定位期刊工作归档

**英文拟题**　Certifying Per-Vehicle Position Bounds in Cooperative UWB Localization with Bounded Inter-Vehicle Range Bias

**中文拟题**　有界车间测距偏差下双车 UWB 协同定位的逐车水平位置界验证

**归档日期**　2026-11-23

给定同一时刻两辆车到四个已知锚点的八条测距，再加入一条可能带偏差的车间测距，究竟能排除哪些双车位置？对每辆车，能否据此给出 10 cm 或 20 cm 的水平覆盖保证？现有结果支持三种可复核的判断：新增测距可能完全冗余，可能排除一些双车位置，也可能使其中一辆车首次获得指定门槛的覆盖保证。锚点布局则在部分案例中确实改变了任意圆心所需的最小覆盖半径。

## 1. 分析对象与判定规则

每辆车的天线高度已知，待估状态为两车的四个水平坐标。固定锚点、斜距观测、测距标准差 4 cm 和平方标准化残差总预算 $q=26$。对给定双车位置，车间测距残差按允许区间内最有利的偏差计算。仅锚距的联合可行集合记为 $F_8$，加入车间测距后记为 $F_9$。固定同一预算使 $F_9$ 包含于 $F_8$，从而可以单独考察第九条测距的作用。八链与九链的同一预算对应不同的统计尾概率。文中的门槛均为该模型下的单时刻研究目标。

| 问题 | 使用的证据 | 能得到的结论 |
| --- | --- | --- |
| 新增测距是否冗余？ | 例如，证明 $F_8$ 中的每种双车位置都能用允许的偏差解释车间测距，使新增残差为零 | $F_9=F_8$，两车各自的可行位置均保持相同 |
| 是否排除了某个双车位置？ | 给出一个满足八链预算的完整双车位置，并证明加入第九链后即使用最有利的偏差也超预算 | $F_9$ 是严格子集；被排除的位置和两次得分均可代回原观测核查 |
| 某辆车能否达到目标半径？ | 将联合可行集合投影到该车平面。两个已验证可行位置相距的一半给出最小覆盖半径下界 $L$；以实际发布点为圆心，覆盖全部保留盒所需的半径给出上界 $U$ | 对门槛 $T$，$U\leq T$ 可保证，$L>T$ 可排除，其余未定。若新上界小于旧下界，还能证明自由选择圆心时的最小半径严格下降 |

这里的逐车目标量为 $r_i^*(F)=\min_{c\in\mathbb{R}^2}\sup_{x\in F}\|\pi_i(x)-c\|_2$，其中 $\pi_i$ 取出第 $i$ 辆车的水平坐标。两端证据满足 $L_i\leq r_i^*(F)\leq U_i$。数值上界变小只表明可报告的保证有所收紧。

## 2. 已有实验与计数

一次联合求解对应一组条件下的两辆车，共两条逐车记录。先导实验含 Moon_1 主段两个时刻和另一条预先固定的合成路线两个时刻。A 复用先导输入，B、C 分别使用同向和交错合成路线。两条路线都在第 4、14 秒比较原矩形与等面积方形布局，使用三个相同噪声种子。已逐元素核对 B、C 的三组 $23\times9$ 噪声矩阵。配对设计控制了噪声差异，同一观测、同一辆车在不同偏差档下会重复出现在表中。

| 实验与固定版本 | 新增联合求解 / 逐车记录 | 10 cm（保证 / 排除 / 未定） | 20 cm（保证 / 排除 / 未定） |
| --- | ---: | ---: | ---: |
| [先导 #156][pilot]，含 16 条已知零偏差诊断记录 | 24 / 48 | 0 / 48 / 0 | 12 / 10 / 26 |
| [A 偏差扫描 #159][sweep]，仅计新增 ±30、±15、±5 cm 三档 | 24 / 48 | 0 / 48 / 0 | 10 / 12 / 26 |
| [B 同向路线 #158][parallel]，三种子、两时刻、两布局、四种模式 | 48 / 96 | 0 / 96 / 0 | 24 / 9 / 63 |
| [C 交错路线 #157][crossing]，与 B 配对 | 48 / 96 | 0 / 91 / 5 | 25 / 12 / 59 |
| **后续 A、B、C 合计** | **120 / 240** | **0 / 235 / 5** | **59 / 33 / 148** |

含先导共 144 次联合求解、288 条逐车输出。后续 240 条中的五个 10 cm 未定项全部来自交错路线。A 的 ±50 cm 结果直接由已有八锚距搜索树证明。表中计数来自固定版本的逐车 CSV，描述各方法在受测条件下能判定多少项；样本间的相关性使这些比例不能直接解释为任务漏警率或现场覆盖率。[先导逐车表][p-rows] · [A 逐车表][a-rows] · [B 逐车表][b-rows] · [C 逐车表][c-rows]

**偏差范围决定新增测距能排除什么。** 先导八组输入和两条后续路线各十二组输入，在 ±60 cm 下均证实整条车间测距冗余。A 的八组在 ±50 cm 下仍全部冗余。收紧到 ±30 cm 后，原矩形布局的两个留出时刻已能排除部分双车位置，其余六组到 ±15 cm 才首次证实排除。B、C 两条路线共 24 个配对输入条件，±15 cm 时 23 项严格缩小、1 项未定，±5 cm 时 24 项全部严格缩小。这里给出的是已测档位间的转变，精确临界值尚未确定。[偏差扫描][sweep] · [同向结果][parallel] · [交错结果][crossing]

**布局能使两辆车跨过同一保护目标。** 先导留出路线第 14 秒，两辆车在原矩形布局的下界为 22.03、21.97 cm；改用同中心、同面积的方形布局后，上界为 19.48、19.22 cm。两辆车均从“任何圆心都无法达到 20 cm”转为“可以保证 20 cm”。先导的八个逐车布局对照中有三项满足严格改善判据，其余五项未定。这些证据支持特定几何下的改善，布局优劣仍随车位而变。[布局对照及上下界][pilot]

## 3. 用一组观测复现三层结论

选取 C 的交错路线、第 4 秒、等面积方形布局、种子 `2026112312`。两车真值斜距约 8.401 m，四种模式共用原始测距和各车的发布点。已从该组测距重新执行 **4 次四维联合搜索**，独立回放全部 4 棵树，并核对 **8 条逐车结果**，待处理队列均为零。这是对 C 中既有观测的复现，样本数仍按第 2 节计。[原始观测][obs] · [联合集合证据][sets] · [逐车上下界][c-rows]

| 观测与允许偏差 | 相对八锚距的双车可行集合 | 车 1 上界 / 20 cm 判定 | 车 2 上界 / 20 cm 判定 |
| --- | --- | ---: | ---: |
| 八条锚距 | 参照 | 20.93 cm / 未定 | 20.47 cm / 未定 |
| 加车间距，±60 cm | 已证相同 | 20.93 cm / 未定 | 20.47 cm / 未定 |
| 加车间距，±15 cm | 已证严格缩小 | 20.93 cm / 未定 | 20.47 cm / 未定 |
| 加车间距，±5 cm | 已证严格缩小 | **19.72 cm / 可保证** | 20.47 cm / 未定 |

±15 cm 已经排除了一些双车位置，但两车的上界都没有变化。±5 cm 使车 1 的上界首次低于 20 cm，而车 2 仍未定。车 1 原先的下界也低于 20 cm，因此这一例证明的是**新增了一项可给出的保证**。它的自由圆心最小半径是否严格下降，现有上下界仍未判定。这也是正文应同时画出上下界和门槛的原因。

**支持实验。** 早期地面仿真给出了四个车×场景实例，其中同一观测允许的两个目标车位置相距至少 32.87–38.14 cm，均足以排除 10 cm。[地面位置见证 #153][ground] 月面四个正常历元中，即使令车间偏差为零，八个逐车下界仍为 11.46–17.97 cm；只缩小原观测的噪声假设会在部分案例排除真值。[月面敏感性 #151][sensitivity] 地面另有按车辆时钟回放的阶跃与渐变告警结果，可用于讨论单时刻几何与连续告警的关系。以上数据单列为背景和敏感性证据。[地面时序告警 #149][alarm]

截至本轮，单独增加车间测距的 A、B、C 对照中均未证实自由圆心最小半径严格下降。部分案例已证实集合相同，其余案例须保留半径变化未定。已证实的严格半径改善来自布局配对。实车逐车定位精度收益属于另一个研究问题，本稿的最小半径和阈值计数均来自仿真。

## 4. 稿件行文与图表安排

| 拟写章节 | 该节回答什么 | 建议证据或图表 |
| --- | --- | --- |
| I. Introduction | 给定同样的测距，为什么两辆车能够获得不同的保护保证？ | 用第 3 节车 1 与车 2 的差异开篇，引出冗余、集合缩小、逐车门槛三个问题 |
| II. Related Work and Problem Formulation | 已有有界误差协同定位解决了什么？本文要验证哪个几何量？ | 介绍最坏误差定位、可行集合、逐车投影与最小覆盖圆；交代已知高度与共享预算 |
| III. Method | 如何证明新增测距冗余、排除具体位置，或证明某辆车跨过门槛？ | 图 1 用一组双车状态及其逐车投影说明 $L$、$U$；给出搜索树与独立核验步骤 |
| IV. Simulation Design | 如何分开锚点布局、偏差范围和路线的影响？ | 图 2 放两种布局与路线；表 1 给出开发/复验输入、噪声配对、误差预算和样本单位 |
| V. Results | 单组观测揭示的现象能在哪些条件下复现？已有方法又能判定哪些案例？ | 图 3 放单观测四档上下界与 20 cm 线；图 4 展示跨路线的集合判定和布局改善；同行方法比较另表，待实跑 |
| VI. Discussion and Conclusion | 哪些判断可以推广，哪些依赖模型、几何或计算分辨率？ | 用未定案例解释界的松紧；交代逐时刻结果的适用范围，讨论从几何界到任务风险还需要的概率模型 |

## 5. 投稿前的首要工作

方法与实验设计现在可以动笔。投稿前，优先用同一批观测与一种已发表的有界误差协同定位方法做配对比较。建议从 Shi 等的 *Robust Localization Using Range Measurements With Unknown and Bounded Errors*（IEEE TWC，2017）入手。该文采用逐链误差界，本研究主实验使用联合残差预算。先在双方都能表达的可行条件下冻结对照，分别报告原模型的结果与适配后的共同条件。[同行方法原文][shi]

在 A 的输入上调通后固定对照规则，在 B、C 归档输入上原样回放，记录逐车上界、10/20 cm 判定、未定数与同机耗时。这里属于对既有路线的回顾性方法比较。若对方只输出点位置、整体网络界或固定中心的上界，应在表中注明所界定的量。最小复现已跑通；这项外部方法对照仍待实施，暂不写相对性能结论。

<details>
<summary>复核入口与版本</summary>

实验 #157、#158、#159 均基于 #156 的固定提交。以上链接固定到各自实验版本。各实验目录内可用下列命令独立读取归档树、见证或结果表：

| 实验目录 | 在该版本目录执行 |
| --- | --- |
| [先导][pilot] | `python3 verify.py 4` |
| [A 偏差扫描][sweep] | `python3 readback.py --verify` |
| [B 同向][parallel] | `python3 verify_results.py` |
| [C 交错][crossing] | `python3 check_inputs.py`，再执行 `python3 verify.py` |

要只从头重跑第 3 节的四种模式，可在 **C 固定版本的 `peer_followup_c/` 目录**运行以下 Python 代码（Python 3，NumPy、SciPy，保留默认断言）。它只向临时目录写入新结果，逐项与原表比较，并使用归档排除见证复核集合关系。

```python
import csv
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import verify as checker
import run as experiment

case = "2026112312_04_equal_area_square"
source = Path("results")
with (source / "rows.csv").open() as stream:
    expected = {
        (row["mode"], row["car"]): row for row in csv.DictReader(stream)
        if (row["seed"], row["t"], row["layout"]) == ("2026112312", "4", "equal_area_square")
    }
assert len(expected) == 8
with tempfile.TemporaryDirectory() as temp:
    output = Path(temp)
    for group in ("observations", "peer_witnesses"):
        (output / group).mkdir()
        shutil.copyfile(source / group / (case + ".json"), output / group / (case + ".json"))
    raw = (output / "observations" / (case + ".json")).read_bytes()
    obs = json.loads(raw)
    obs["input_hash"] = hashlib.sha256(raw).hexdigest()
    assert all(r["input_hash"] == obs["input_hash"] for r in expected.values())
    experiment.OUT = experiment.pilot.OUT = checker.D = output
    actual = {}
    for mode in checker.MODES:
        for result in experiment.job((obs, mode)):
            row = {k: "" if v is None else str(v) for k, v in result.items()}
            ref = expected[mode, row["car"]]
            for key in ("upper_cm", "status_10cm", "status_20cm", "truth_feasible", "nodes", "pending"):
                assert row[key] == ref[key], (mode, row["car"], key)
            actual[case, mode, row["car"]] = row
    assert len(actual) == 8
    checker.init_table(actual)
    relations = {r["mode"]: r["status"] for mode in checker.MODES
                 for r in checker.verify_job((obs, mode))}
    assert relations == {"peer_60": "已证相同", "peer_15": "已证缩小", "peer_05": "已证缩小"}
    print("PASS", len(actual), relations)
```

</details>

[pilot]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/tree/3787e3a4b61aac969a46ab8245c37f5ed1199d92/docs/research/lunar_end_to_end/layout_peer_pilot
[p-rows]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/3787e3a4b61aac969a46ab8245c37f5ed1199d92/docs/research/lunar_end_to_end/layout_peer_pilot/results/rows.csv
[sweep]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/tree/9b39914d8d897344708d70108ae25c8815b65d2f/docs/research/lunar_end_to_end/peer_followup_a
[a-rows]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/9b39914d8d897344708d70108ae25c8815b65d2f/docs/research/lunar_end_to_end/peer_followup_a/by_car.csv
[parallel]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/tree/8d789960898cad79f7edd90cfadbe86fafffba45/docs/research/lunar_end_to_end/peer_followup_b
[b-rows]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/8d789960898cad79f7edd90cfadbe86fafffba45/docs/research/lunar_end_to_end/peer_followup_b/results/rows.csv
[crossing]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/tree/a4687f2d4c52987e69d3d0ef0f74618f9c550438/docs/research/lunar_end_to_end/peer_followup_c
[c-rows]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/a4687f2d4c52987e69d3d0ef0f74618f9c550438/docs/research/lunar_end_to_end/peer_followup_c/results/rows.csv
[sets]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/a4687f2d4c52987e69d3d0ef0f74618f9c550438/docs/research/lunar_end_to_end/peer_followup_c/results/sets.csv
[obs]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/a4687f2d4c52987e69d3d0ef0f74618f9c550438/docs/research/lunar_end_to_end/peer_followup_c/results/observations/2026112312_04_equal_area_square.json
[ground]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/153
[sensitivity]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/151
[alarm]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/149
[shi]: https://doi.org/10.1109/TWC.2017.2691699
