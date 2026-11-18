# PR119：几何改善回答了什么，还缺什么

核查日期：2026-11-17。只读来源为 PR119 固定提交 `e35f94fb89a71236bd04c7f25fc318b016ba592d`，未合并该 PR。先读取 main `b492c17d719013c31a93168994afe40beed5001f` 中 PR118 的文献矩阵、理论审计和方法路线，再读取 PR119 的 PROTOCOL、REPORT、DECISION_MEMO，并对照实现与保存汇总 CSV。本轮仅读取和筛选已有表，没有调用优化器、重新计算 bootstrap 或启动 Monte Carlo。

## 1. 能归属于这次配对对照的证据

PR119 在六时刻静止双车简化模型中，将四个原共线锚点按固定符号交替横向扰动 0、0.10、0.50 m。三几何共享同 seed 的测距标准噪声、全局位移噪声、正确固定先验中心、五个实际初始状态及求解设置；真实距离按各几何重新生成。正确先验中心是理想实验条件。B2 知道受影响的 peer 链路并估计单一自由常偏差；B3 知道注入幅度。这些控制支持比较**本配置中的几何改变效应**，不支持对一般环境的因果外推。[协议 L7–17](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/PROTOCOL.md#L7)、[输入生成 L17–23](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/tools/midterm_geometry_perturbation_a/model.py#L17)。

每条件每方法的独立单位为 **40 个 seed**。三几何复用这 40 组随机流；两个机器人、六个时刻、五个初值以及 P0/P1 求解阶段均不增加独立样本量。正式记录为 120 个几何输入、240 个输入—方法单元、1200 个方法—初值配置、2400 次阶段/优化器调用；最终 1181 接受、16 未驻点、3 预算耗尽，全部有限且保留。开发的 30 配置/60 调用另列。[协议 L35–39](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/PROTOCOL.md#L35)、[COUNTS.json](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/results/COUNTS.json)、[报告 L13](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/REPORT.md#L13)。

|B2 扰动|多接受终点组 seed|车1 / 车2点覆盖|车1 / 车2六时刻全覆盖|车1 / 车2面积均值（m²）|
|---|---:|---:|---:|---:|
|0 m|22/40|87.083% / 83.333%|70% / 77.5%|0.060647 / 0.056983|
|0.10 m|9/40|88.750% / 81.250%|72.5% / 70%|0.040242 / 0.039259|
|0.50 m|0/40|95% / 95%|80% / 80%|0.014071 / 0.014162|

**表的口径：** 名义 95% 的局部曲率椭圆；选优接受组内先对成员平均，再对 40 seed 等权平均。每车每条件计划/可用点均为 240；点平均的 240 项不是独立 n。六时刻全覆盖以 seed 为单位，且仍先作组内成员平均；它不是双车联合事件，也不是由点态 95% 自动导出的轨迹保证。面积同样采用选优组口径，不与单个 selected 代表点混淆。数值逐项核对保存表：[组率](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/results/summary/BRANCH.csv#L2)，[0 m 组内汇总 L4/L9](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/results/contrasts/GROUP_SUMMARY.csv#L4)，[0.10 m L24/L29](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/results/contrasts/GROUP_SUMMARY.csv#L24)，[0.50 m L44/L49](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/results/contrasts/GROUP_SUMMARY.csv#L44)。

0.50 m 相对 0 m 的预定 B2 主对比中，多组率下降 55 个百分点，逐项配对 seed 95% 区间为 [−70,−40]。车1点覆盖增加约 7.917 个百分点，区间约 [0,17.083]，车2增加约 11.667 个百分点，区间 [2.917,21.667]。车1区间没有明确排除零；两车不独立且没有多重比较保证。达到经验 95% 的两车自身区间分别约为 [91.25%,98.33%] 和 [91.25%,97.92%]，不能认定总体已校准。[主对比 L25/L29](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/results/contrasts/GEOMETRY_CONTRASTS.csv#L25)、[车2 L75](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/results/contrasts/GEOMETRY_CONTRASTS.csv#L75)。

## 2. 已回答的问题与不能跨越的边界

|问题|PR119 支持的回答|仍需的证据 / 不能声称的结论|
|---|---|---|
|几何是否值得认真处理？|值得。控制不变时，0.50 m 扰动同时改善多组数、误差、面积及关键弱方向诊断。|不能把所有覆盖失准归于共线；0.10 m 的不利结果必须保留。不能把这三点拟合为单调通用规律。|
|原共线系统的横向信息缺在哪里？|真状态下 B2 测距 Jacobian 为 13/25 秩，测距+位移为 23/25；加入固定先验才为 25/25。有效横向秩分别为 0/12、10/12、12/12。|只是指定真状态的一阶信息结构；数据局部秩亏不自动证明非线性可行集无界或不可全局辨识，局部满秩也不证明全局唯一。|
|扰动是否使测距本身提供横向信息？|0.10/0.50 m 下 B2 测距全列秩，有效横向最小特征值约 2.66434/64.51739 m⁻²。|不能用真状态设计矩阵替代噪声端点的区域，更不能用未删测的满秩代替各故障排除子问题的可辨识性。|
|多组减少是否仅因为删掉未接受终点？|本数据全部有限与仅接受候选的多组数一致；这个简单解释不足。|接受集合、选优、曲率和误差同时变化，其贡献未独立分离。不能根据现象推断唯一因果。|
|0.50 m 下 0/40 多组是否证明唯一解？|仅说明固定五初值与固定分组阈值下未观察到多个接受组。|没有穷尽所有合法解、所有驻点或所有域；需要解析对照或可信外包，增加有限初值不能替代证书。|
|整体 Hessian 差小是否足够？|不足。整体相对 Frobenius 差约 0.0031–0.0035，B2 最弱子空间二阶/GN谱范数比却约 3.255→0.907→0.00636。|不能仅以整体范数设非线性余项界；端点二阶诊断不是全扰动域上严格余项上界。|
|是否已获得保护区域 / PL？|获得的是有清楚统计口径的局部椭圆诊断。|仍缺全部分支包含、固定偏移域依据、联合噪声事件、未知故障管理、数值外包证书及输出/告警合同。|

信息数据见 [TRUTH_DESIGN_INFORMATION.csv L2–16](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/results/information/TRUTH_DESIGN_INFORMATION.csv#L2)；横向消元按 Jacobian 干扰列空间的正交投影，而非直接取条件块当边缘信息，见 [information.py L6–15](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/tools/midterm_geometry_perturbation_a/information.py#L6)。弱方向、全有限候选和选优局限见 [REPORT L40–72](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/REPORT.md#L40)。

## 3. 会影响下一轮方法解释的三个具体接口

**区域身份必须保留。** PR119 主报告的 `curvature` 使用 $C_G=(J^TJ)^{-1}$，另有固定先验噪声传播 `fixed_prior_noise` 视图。固定先验中心没有重新采样，因此不能将 $C_G$ 普遍叫作重复试验协方差。两视图在强扰动下经验覆盖相同也不使其定义等价，更没有建立精确 Hessian 逆的协方差身份。[PROTOCOL L31](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/PROTOCOL.md#L31)、[两视图覆盖表 L1090/L1106](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/docs/research/midterm_geometry_perturbation_a/results/summary/COVERAGE.csv#L1090)。本轮没有发现足以宣布该批次无效的具体错误；上述区别是迁移审计要求。

**线性基准必须是直接定义并解算的仿射问题。** PR119 真状态信息是六个确定性设计点，不是六个独立样本或仿射估计器输出。下一轮若比较“线性正常、非线性异常”，应明确定义固定设计矩阵、同一随机输入和固定先验机制；仅在真值处计算 Jacobian，再评估原非线性端点，不足以建立这个对照。PR118 已提醒 PR116 存在同类身份边界。[PR118 THEORY_AUDIT §1](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/b492c17d719013c31a93168994afe40beed5001f/docs/research/midterm_integrity_literature_c/THEORY_AUDIT.md#L7)、[PR119 真状态诊断实现 L24–26](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/tools/midterm_geometry_perturbation_a/information.py#L24)。

**时间概率不能从当前生成器直接迁移到实物。** 当前位移是全局 XY 相邻位置差加独立 Gaussian 噪声，先验是正确固定中心；它不是完整里程计/IMU随机误差过程。短轨迹方法若把多个时刻的置信度相乘，必须另核原始观测及运动增量的联合独立性。即使增量独立，将同一初值逐步积分得到的状态误差也共享历史噪声，不能再次当作独立量测相乘。[model.py L19–21](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/e35f94fb89a71236bd04c7f25fc318b016ba592d/tools/midterm_geometry_perturbation_a/model.py#L19)。这是一项由生成式直接得到的依赖关系提醒，并非宣称 PR119 已错误计算时间概率。

## 4. 对低维验证协议的具体要求（建议，未执行）

1. **先隔离概率入口与算法包含性。** 仿射基准固定设计矩阵、噪声联合协方差及有界固定偏移集合；用解析逆像验证噪声事件内的状态必在外包内。报告的是确定性包含检查和必要的解析概率，不将有限测试点无失败叫作全域证明。
2. **再隔离多解与几何信息。** 二维测距使用可解析的镜像双解，预给完整搜索域；显式保留两支。另设弱几何/非共线对照，仅检查集合如何变化，不预设“破共线即单解”“面积应更小”或“覆盖必改善”。不可从最优点附近裁出搜索盒。
3. **在故障排除接口重新查可辨识性。** 把含故障边的模型、删边后的模型、相关 nuisance 参数同时写清。已删除全部支撑量测的偏差变量不得仍保留为无信息列；若目标投影无界，按不可用输出，不能用有限域裁剪伪造有限保护半径。
4. **同时保留失败与性能代价。** 边界、空集、无界、未决盒与超时都是预设案例。超时保留队列外包或明确不可用；没有有限认证结果时不得仅统计成功案例。覆盖/包含、区域大小、可用率和计算成本必须同步报告。

这些验证是为判断文献模块能否迁移而提出的方案，不更改 PR119 冻结协议、门槛或已有结论。PR119 提供了保留弱几何和轻扰动不利对照的充分动机；它没有替下一轮完成非线性集合包含、故障假设完整性或保护级理论。
