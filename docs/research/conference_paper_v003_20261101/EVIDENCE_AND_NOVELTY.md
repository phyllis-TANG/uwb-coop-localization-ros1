# 会议论文：证据、创新主张与不能越过的边界

2026-11-01。本文档对应 `PAPER_OUTLINE.md` 与 `MODEL_AND_CALCULATIONS.md`。它是给后续写作者的论证卡，不是投稿正文。PR92 已合并到 main；本交接不改估计器或任何旧实验用途。

## 论文目前要回答的问题

两辆车各有墙锚测距，另有一条车间测距进入联合估计。一辆车的本地测距校正会同时改变独立解和协同解。我们关心的不是“校正是否降低某车绝对误差”这一个问题，而是校正是否改变**每辆车相对其独立解的协同收益**，这种改变又如何随摆位条件变化。

同一车、同一输入、同一评价时刻定义 $D=\mathrm{MSE}_{\mathrm{coop}}-\mathrm{MSE}_{\mathrm{ind}}$，$C=D_{\mathrm{hist}}-D_{\mathrm{raw}}$，$T=C_{G2}-C_{G1}$。$C$ 可恒等分解为“校正对协同解的 MSE 改变”减“校正对独立解的 MSE 改变”。公式简单，贡献在于用该分解提出可检查的逐车问题，并用实际记录和预冻结控制对照检验它；不把代数本身称新定理。

## 已完成证据与正式用途

| 证据 | 已得到什么 | 论文中可支持什么 | 不能写什么 | 来源 |
|---|---|---|---|---|
| 既有静态五个无人体正常包，G1 两包、G2 三包 | Car1 完整协同 $T=+0.079695$ m²；Car2 $T=-0.138701$ m²。在 G1，Car2 校正使独立解 MSE −0.420618、协同解 −0.281562 m²，因此二者都改善，协同相对优势却减少 | 现场摆位条件下的逐车校正交互，以及“绝对改善不等于相对收益改善” | 事后二次分析不能当独立预测验证；G1/G2 同时改变传播环境和初始化，不能单独归因几何 | 本地 `outputs/calibration_geometry_interaction_20261101/v001/RESULT.json`；公开静态交接见 [PR89](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/89) |
| PR91 预冻结配对仿真 | 四墙偏差从一车经 peer 约束影响另一车；故障源与运动条件切换后逐车效应不同；固定缩权同时牺牲收益并减小部分代价 | 跨车传播机制和局部测量统计不足以描述全部伙伴响应的受控例子 | 不代表在线检测率、绝对安全概率或自然 NLOS 风险 | [PR91 报告](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/b7af016b09e5717b718d9251341706fc33aa6f46/docs/research/two_car_mechanism_20261101/REPORT.md) |
| PR92 摆位控制，4 seed、48 单元 | 仅平移 Car2 整条真值轨迹，保持合成随机原语、算法与校正处理固定。M3 Car1 $T=-0.001530079$ m²，Car2 $T=-0.297352631$ m²；两车均满足冻结主规则。Car1 符号与现场相反；W025 的 Car1 四 seed 符号混合 | 在指定合成模型中，摆位变化足以造成校正与相对协同收益的交互；现场方向的简单跨域迁移失败 | 不能说纯几何已解释现场角色变化。仿真为四墙已知合成偏差及完整减除，两处理分别初始化；现场为既有静态 P1 校正 | [PR92 报告](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/723cf1745b6739a0eed3a1afc2b38f34a4b27bf8/docs/research/geometry_correction_20261101/REPORT.md)、[逐 seed CSV](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/723cf1745b6739a0eed3a1afc2b38f34a4b27bf8/docs/research/geometry_correction_20261101/results/PER_SEED_INTERACTIONS.csv) |
| A2/B2 已冻结实车动态 | 原 M2/M3/M3W025 在运动后人工测量停点的逐车误差与覆盖；A2 RETURN 的 Car1 RMSE 30.84→27.75 cm，Car2 46.33→51.89 cm（M2→M3） | 原方法配置在真实运动后停点可出现逐车收益方向不同 | 无已验收连续运动真值；A2/B2 对新的 $T$ 假设已经暴露，不能重新称盲验证 | 本地 `outputs/reserved_validation_20261101/v001/RESERVED_RESULTS.json`；[PR90](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/90)仅保存早期开发结果和保留规则草案，最终 A2/B2 数值仍以本地结果为准 |

静态旧 I/J/W025 没有后续接入的 IMU 因子；动态 M2/M3/M3W025 和 PR91/92 都含 IMU。两类结果只能分别在自身配置下比较。实测人工参考按操作者每轴约 ±2 cm 估计做条件性敏感性分析，不是经认证的置信区间。PR92 每 seed/车 88/90 预定时刻在全部 12 配置中共同 accepted；四 seed 是统计重复单位，帧数不是。

## 可主张的创新与近邻差别

**当前最稳的贡献句：**本文针对低冗余双车 UWB 协同定位，逐车量化本地测距校正对独立解与协同解的不同作用，并在实测摆位条件与预冻结受控仿真中检验其相对收益交互；受控试验同时揭示该交互方向不能简单从合成摆位迁移到现场。

这是一项实证与分析贡献。已有研究涉及[有偏邻居传播和可信节点选择](https://www.eurecom.fr/publication/5001/download/comsys-publi-5001_1.pdf)、[有偏测量的鲁棒协同融合](https://ieeexplore.ieee.org/document/10423111/)和[UWB 锚布局及校正敏感性](https://ieeexplore.ieee.org/document/9459845)。本文不以“偏差能传播”“校正重要”“几何影响精度”或“IMU 融合”为首创。上述近邻的精确评价量、实验设置及与 $D/C/T$ 的重合程度还需要在相关工作正式稿逐篇核查；现有检索不足以断言“首次”。

PR92 预定主规则通过，同时预定“现场 Car1 方向一致”规则失败。两个结果须在摘要、结果和讨论中并列；不能把后者藏进附录。Car2 的跨场景同号也不能作为数值复现，因为现场与仿真的偏差类型、校正程度、运动和初始化不同。

## 投稿前最小工作

1. 对照冻结代码写出实际状态、天线杆臂、墙锚／peer／odom／gyro 因子和鲁棒损失；保持静态旧接口与动态 IMU 方法的身份。
2. 用同一 $D/C/T$ 符号制作现场五包与 PR92 逐 seed 图，并将 PR91 和 A2/B2 作为机制与有限实测的补充；每图同时报共同有效和计划帧分母。
3. 完成最近邻“假设—评价量—数据—本文差异”表，再定贡献措辞。现有证据足以完成整稿，不因这份交接追加实车采集或结果驱动调参。

本交接没有上传原始 bag、视频、密码或完整本地输出；`outputs/...` 是本地研究总账的来源路径，远端读者需以本文件数值和所链接的已公开 PR 为起点。PR92 逐 seed CSV 的 $T$、均值和四 seed Student-$t$ 区间曾由本地窗口独立重算；未在本地重跑其 48 个估计单元。

