# 本轮方法迁移所回应的现有证据

核查日期：2026-11-17。以下均通过固定 SHA 的 `git show` 只读核对报告、数学说明、决策备忘与实现；没有运行定位器、历史分析脚本或新增随机试验。PR123/124 是当前审查快照，不能因本轮读到其结果就视为已经合并。初查状态与工作区身份见 [环境记录](notes/ENVIRONMENT.json)。交付复核时PR123/124已由外部合入main 30f9379249a4e695acf75910c40862a770e6f4ce，head与本文快照一致；PR122仍OPEN，见 [交付记录](notes/DELIVERY_ENVIRONMENT.json)。本分支没有合并它们。

|来源|本轮固定提交|定位目录与角色|
|---|---|---|
|PR122 文献基线|`9832da3b7cb44e43c89bd10dad550d96419b72c0`|`docs/research/midterm_integrity_targeted_c/`：已核集合反演、短轨迹、轨迹管和 solution separation，提出低维外包验收路线|
|A，PR123|`f354cf5e370d4ffc54077b7280ca97638a8bd585`|`docs/research/midterm_nonlinear_decomposition_a/`：既有端点代数分解与退化仿射区域|
|B，PR124|`aab57504262fff739d0754145c61a61efa79791a`|`docs/research/midterm_nonlinear_region_b/`：已完成低维非线性噪声事件反演与外包证书|
|本轮 main|`0c3dbbb59a5c65087e073ad1c49eaed397f2958b`|`docs/research/moon1_bias_dynamics_eval/`：数值验收、常值/阶跃/斜坡偏差探索|

## 1. PR122 已建立的入口，本轮不重复宣称为新成果

PR122 已区分确定性外包、输入事件概率、位置区域概率与完好性（integrity）事件；提出从完整联合噪声事件反演，而非假定非线性估计误差 Gaussian。它还明确未决队列、全部分支、固定域依据、有限样本与保护级之间的边界。全文笔记已有 SIVIA、Drevelle–Bonnifait、轨迹管和固定窗 SS；Kuwada2026 仅为取得正式身份的摘要级线索。[文献矩阵 L3–15][c-matrix]、[理论审计 L5–12、L72–126][c-audit]。

当时“先实现低维可信外包”是计划，[方法路线 L3–24][c-method] 明确写为尚未实施。**当前 PR124 已完成该低维原型及八个确定性例的外包证书。** 因而本轮推荐必须是对现有外包器的单项改进/成本对照，不能再把“从零实现 SIVIA、保留镜像支和队列”作为尚未完成的首项工作。短轨迹、故障排除、偏差学习和相关误差仍需分别给条件，不能一次拼成已验证方法。

## 2. A：已有端点解释更清楚，非线性区域证明仍缺

**已完成的事实。** A 只读 PR119 的 1200 个和 PR121 的 600 个保存端点，共 1800 个；每条件独立 seed 分别为 40 和 30，两批不能合并为配对试验。未产生新观测、非线性优化器调用或 Monte Carlo。实现直接读端点与归档仿射结果；运行保护禁止进入优化器/生成器。[REPORT L9–16、L80–85][a-report]、[analyze.py L6–22、L66–68][a-analyze]、[common.py L15–19][a-common]。

其恒等分解为

$$
\Delta_N-\Delta_L=v_g+v_\eta+v_J,\quad
H_0v_g=g_N,\quad H_0v_\eta=-J_0^T\eta,\quad
H_0v_J=-\Delta J^Tr_N.
$$

它适用于任一保存端点，无须假定驻点。不能因接受标签把 $g_N$ 置零；三项范数不能相加当“独立因果份额”。本批弱几何中，位置差主要呈现 Jacobian 变化与残差耦合的响应，偏差状态差主要呈现残差非线性余项；该结果没有证明未发现分支、路径高阶效应和几何干预各占多少，也不给未来扰动域的统一界。[MATH L7–21][a-math]、[REPORT L18–50、L89–93][a-report]。

**固定 survey 与随机传播。** A 的先验中心固定：仿射解为 $G\epsilon+T\delta$，协方差为 $GG^T$，不是把全部曲率逆 $KK^T$ 当随机协方差。共线首时刻可有唯一状态解但秩 1 的随机位置边缘。A 已给支持子空间与 $\chi_r^2$ 的正确集合定义，再与同一个四维固定偏移集合相加；12 个位置块采用预先固定的并集界，无须车间/时间独立。[MATH L25–35、L39–75][a-math]；实现仅将前 74 个随机残差列纳入 $G$，[common.py L45–50][a-common]。

**保留不利结果。** 零中心偏移、weak/先验 sigma=.5 条件下，仿射联合外包圆全轨迹覆盖 30/30，直接套用到非线性端点仅 7/30；该对照使用相同的仿射区域，不继承仿射保证。轻几何扰动也没有同步修复车 2 覆盖。这里的 30/30 或 7/30 是既有有限样本描述，不能变成罕见失效风险声明。[REPORT L48、L62–76][a-report]、[DECISION_MEMO L5–9][a-decision]。

**本轮回应。** 可信外包回应“未控制的非线性/多分支”缺口；最优性证书只检查给定目标的最优性，不能代替上述区域事件。不能用有限端点的最大余项作为确定界，也不能因残余梯度很小就认定位置可靠。

## 3. B：二维/三维外包已完成，当前困难是约束传播与模型扩展

**实际模型。** 状态是 $(x,y)$ 或 $(x,y,b)$；前三个锚点及第四个参考车位置均已知。$b$ 只进入预定第 4 条测距：阶段 1 已知 $b=.3$ m，阶段 2 固定未知 $b\in[-.6,.6]$ m。没有第二未知车、位置先验、运动输入或未知故障发现。这里的 $b$ 是测距偏差，不是 A/历史 PR121 的固定 survey 中心偏移 $\delta$；不能笼统称本轮 A/B 为同一种先验模型。[MATH L5–7][b-math]、[inputs.py L4–14][b-inputs]。

四条原始测量误差满足声明的 $N(0,.04^2I_4)$，完整噪声事件以 $q=9.488$ 反演。维数是四个生成误差，不能减去拟合参数数目。真参数属于事先给定域、噪声模型与输入表示区间正确时，事件蕴含真参数进入反演集合；无须估计误差 Gaussian、唯一解或可逆局部 Hessian。[MATH L7–17][b-math]。

**已有计算保证。** 八例全部是预定确定性机制例，不是八个 Gaussian 样本。仅可靠下界大于 $q$ 时删盒；内盒、边界未决、异常未决和预算队列均保留。完整分割树及所有已分类叶由独立精确算术读回；硬中断无结果不冒充空集。[REPORT L13–19、L37–39][b-report]、[invert.py L35–60][b-invert]。镜像两支已保留；外包圆较宽、不一致例域内为空、预算例保留队列都是已有证据，不能重新列成尚未验证能力。[REPORT L21–27][b-report]。

**可靠负面证据。** 加一个未知 $b$ 后 good/mirror 处理盒数分别由 207/461 增至 2687/5741，约 13/12.45 倍。三维投影面积上界增加同时包含额外未知量与区间依赖膨胀，不能全归因于真实区域增大；低维计时不支持直接外推 25 维。[REPORT L29–33][b-report]。

**本轮回应。** B 已建议只选一种平方差或可信收缩改进，同域、同输入、同阈值、同预算比较，保留全部分支和原证书体系。[DECISION_MEMO L3–11][b-decision]。Calafiore 可提供凸差分约束与外包盒作为预收缩/成本基线，但原逐条测距界与 B 的联合 Gaussian 球不是同一个统计集合。安全迁移须先把球保守包到坐标区间，再证明不删原事件内点；原球约束仍保留。未知 $b$ 必须共享同一合法变量或安全投影，不能代入拟合值；详见 [Calafiore 笔记](notes/CALAFIORE.md)。

## 4. moon1：常偏差模块有匹配证据，时间变化与真实噪声契约仍缺

**模型和调用口径。** 两车六时刻联合估计 XY，高度使用 oracle；四个人工信标的位置视为精确已知，测距仍含噪声；运动输入是合成全局 XY 增量，不是已完成 IMU/轮滑模型。M0 丢弃 peer，M1 使用原始 peer，M2 为同一预定 peer 链路增广一个自由常数；M2 不读取注入条件来切换模型。模型代码明确 M0 删除六条 peer 行、M2 增加第 25 个状态，其余为 24 维。[REPORT L14–19][m-report]、[model.py L23–57][m-model]。

任务二为 10 个独立 seed、3 窗口、4 条件、3 方法，共 360 方法运行/720 优化器阶段调用；最终 349 接受、11 `NOT_STATIONARY`，均保留。3 窗口乘 10 seed 的 30 项不是 30 个独立 seed，不能把车辆、时刻或阶段当独立样本。`formal_runs=0` 是报告中的研究批次身份，不表示无方法调用；包含开发冒烟及旧端点继续后的 766 次优化器调用也不是样本数。[REPORT L5–8、L40–65、L123–133][m-report]。

**先验与 A 不同。** moon1 的初始中心为真实首时刻位置加独立 Gaussian 抽样，sigma=.5 m；range/motion/prior 使用不同生成 stream。A 的固定 survey 中心不是这种随机观测。因而 A 的“只传播 74 个随机行、其余四行固定”不能直接移植到 moon1 的生成分布；应先写清随机对象。[generate.py L25–38][m-generate]、[inputs.py L17–34][m-inputs]。B PR124 则根本没有这个位置先验，需另行区别。

**已支持和未支持。** M2 在 normal 与 constant03 的位置估计几乎一致，偏差状态相应平移，是常值模型匹配的一致性证据。step/ramp 下 M2 平均误差小于 M1、却大于 M0，两车各自平均 per-robot cooperative benefit 相对 M0 均为负，peer 残差仍有时间结构。这反驳“一个常偏差足以处理任意时间变化”的一般化，不给真实 NLOS 模式转移概率，也不能把确定性阶跃/斜坡当平稳 Gauss–Markov 噪声。[REPORT L82–105][m-report]、[DECISION_MEMO L6–21][m-decision]。

**集中式耦合不等于已建模相关噪声。** 现有 peer 残差同一行含两车状态导数，运动残差连接相邻时刻，M2 的同一 $b$ 跨六时刻进入目标，因此集中式联合估计保留这些状态耦合；由联合响应传播可产生车间/时刻/状态—偏差的估计相关性。与此同时，primitive 测距、运动和 prior 残差目前逐项除以各自 sigma，没有为有色时间噪声或共享传感器误差构造完整联合白化。**这是代码结构判断，不是新增协方差实验。** [model.py L31–54][m-model]、[独立实现 bridge.py L37–59][m-bridge]。

因此“需要检查实际输入相关模型”成立，但“必须改成分布式滤波才能保留相关性”不成立。引入 Gauss–Markov 模块前先证明参数范围、初始过程分布和全窗口协方差外包；引入 IMM 前先说明模式及偏差先验的数据来源。本轮不把任何作者算法作为现有 constant/step/ramp 的已验证修复。

## 5. 本轮方法筛选所采用的实际缺口

|缺口|已有成果应保留|本轮可推进的模块边界|
|---|---|---|
|非线性多支与全域包含|PR124 已有低维证书；PR123 有仿射移植失败证据|优先验证一个保解预收缩器的证书与成本，不再从零重复低维 SIVIA|
|常偏差与时间变化|moon1 M2 常值匹配、step/ramp 不利结果均已存在|模式/偏差相关性原理可储备；真实参数与模式概率未校准，不立即迁移完整 IMM|
|时间相关与车间相关|当前联合估计保留因子导致的状态耦合|另核输入联合协方差与全窗口 PSD 外包，不把对角权重当有色噪声模型|
|安全量化|条件性噪声事件反演与数值外包已闭合一小步|还需域/偏差/噪声依据、故障与未覆盖事件、告警和可用率合同；最优性证书、低维计时和少量覆盖例均不能填补这些定义|

[c-matrix]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/9832da3b7cb44e43c89bd10dad550d96419b72c0/docs/research/midterm_integrity_targeted_c/LITERATURE_MATRIX.md#L3-L15
[c-audit]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/9832da3b7cb44e43c89bd10dad550d96419b72c0/docs/research/midterm_integrity_targeted_c/THEORY_AUDIT.md#L5-L126
[c-method]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/9832da3b7cb44e43c89bd10dad550d96419b72c0/docs/research/midterm_integrity_targeted_c/METHOD_OPTIONS.md#L3-L24
[a-report]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/f354cf5e370d4ffc54077b7280ca97638a8bd585/docs/research/midterm_nonlinear_decomposition_a/REPORT.md#L9-L93
[a-math]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/f354cf5e370d4ffc54077b7280ca97638a8bd585/docs/research/midterm_nonlinear_decomposition_a/MATH.md#L3-L81
[a-decision]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/f354cf5e370d4ffc54077b7280ca97638a8bd585/docs/research/midterm_nonlinear_decomposition_a/DECISION_MEMO.md#L3-L9
[a-analyze]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/f354cf5e370d4ffc54077b7280ca97638a8bd585/tools/midterm_nonlinear_decomposition_a/analyze.py#L6-L68
[a-common]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/f354cf5e370d4ffc54077b7280ca97638a8bd585/tools/midterm_nonlinear_decomposition_a/common.py#L15-L61
[b-report]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/aab57504262fff739d0754145c61a61efa79791a/docs/research/midterm_nonlinear_region_b/REPORT.md#L3-L39
[b-math]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/aab57504262fff739d0754145c61a61efa79791a/docs/research/midterm_nonlinear_region_b/MATH.md#L5-L43
[b-decision]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/aab57504262fff739d0754145c61a61efa79791a/docs/research/midterm_nonlinear_region_b/DECISION_MEMO.md#L3-L11
[b-inputs]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/aab57504262fff739d0754145c61a61efa79791a/tools/midterm_nonlinear_region_b/inputs.py#L4-L26
[b-invert]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/aab57504262fff739d0754145c61a61efa79791a/tools/midterm_nonlinear_region_b/invert.py#L6-L60
[m-report]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/0c3dbbb59a5c65087e073ad1c49eaed397f2958b/docs/research/moon1_bias_dynamics_eval/REPORT.md#L5-L134
[m-decision]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/0c3dbbb59a5c65087e073ad1c49eaed397f2958b/docs/research/moon1_bias_dynamics_eval/DECISION_MEMO.md#L5-L24
[m-model]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/0c3dbbb59a5c65087e073ad1c49eaed397f2958b/tools/moon1_localization_eval/model.py#L23-L59
[m-generate]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/0c3dbbb59a5c65087e073ad1c49eaed397f2958b/tools/moon1_localization_eval/generate.py#L25-L39
[m-inputs]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/0c3dbbb59a5c65087e073ad1c49eaed397f2958b/tools/moon1_bias_dynamics_eval/inputs.py#L17-L37
[m-bridge]: https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/0c3dbbb59a5c65087e073ad1c49eaed397f2958b/tools/moon1_bias_dynamics_eval/bridge.py#L35-L60
