# 协同故障模式与 solution separation 定向核查

检索日期：2026-11-17。这是本轮只读核查，不修改 PR118，也不运行作者代码或定位实验。核心精读补核为 Hafez 等 2020；Kuwada 等 2026 保留为最接近工作线索，**没有取得全文**。

## 1. 指定最近工作：Kuwada、Joerger、Spenko（2026）

**书目已核实。** Shinsaku Kuwada, Mathieu Joerger, Matthew Spenko, *Fault-Mode Aware Integrity Monitoring for Collaborative CAV Localization*, Proceedings of the 2026 International Technical Meeting of the Institute of Navigation, Anaheim, January 26–29, 2026, pp.288–301；DOI [10.33012/2026.20494](https://doi.org/10.33012/2026.20494)。[ION正式记录](https://www.ion.org/publications/abstract.cfm?articleID=20494)明确标注 Peer Reviewed；不是仅有会议摘要/预印本身份。

**全文状态。** ION正式页要求会员、下载额度、订阅或购买。核查了 [Joerger作者发表页](https://www.aoe.vt.edu/people/faculty/joerger/personal-page/publications.html)、其 Papers Archive、[IIT CARNATIONS项目发表列表](https://www.iitcarnations.org/publications)、IIT实验室人员页，以及题名/DOI+PDF、作者+collaborative localization、NSF/ROSA P机构域名检索。作者与项目列表确认书目，但本轮未找到合法公开全文。未购买、未借用登录、未尝试规避访问控制。实验室首页/猜测发表页访问失败不等于作者从未提供全文。

**可以说的内容限于线索。** 官方摘要区分车辆特有故障与共同故障，并报告协同对前者改善有限、对后者更有帮助。这一不利于普遍“协同即安全”的摘要结论必须保留，但没有全文支持我们复核其条件或量化数值。

**不能说的内容。** 状态维数、具体传感器方程、检测器是否属于 solution separation、故障位置是否已知、时间独立性、先验机制、线性化余项、假设概率、秩条件、删测后可辨识性、概率/集合保证强度、多解处理、搜索域、空集/无界/超时、实验公平性、代码与许可证，均标为**未核查**。题名和摘要不能填补这些栏目。尤其不能因为本轮主题是 SS，就将它归类为已核验 SS 算法。

证据质量：**元数据可靠；公式/保证不可评价**。迁移适用性：**研究问题高度相邻；可实现模块未确认**。两轴不能合并为“差论文”，也不能据此宣布本项目创新性成立。

## 2. 可取得的相关原始资料，不冒充指定论文

[USDOT ROSA P技术报告](https://rosap.ntl.bts.gov/view/dot/79312) *Multi-Vehicle/Infrastructure Jammer/Spoofer Detection and Localization*，机构记录日期2024-09-30，报告号6，21页；[公开PDF](https://rosap.ntl.bts.gov/view/dot/79312/dot_79312_DS1.pdf)的附录A由 Kuwada、Spenko、Joerger署名，PDF页9–20。已读取相关附录，**它不是2026论文，也没有确认与2025 ICRA最终版逐字相同**。

附录A §A-2（PDF页10–11）显式排除由其他机器人估计偏差引起的相对量测故障，并将未映射物体关联与错误映射关联区分；§A-3–A-5（页11–17）讨论CEKF/DMV及创新检测，非本文所需的完整解分离证明；§A-6（页17–19）为双车仿真和校园数据。这里最有用的是暴露**故障传播的合同边界**：将别车状态传给本车，不代表别车的偏差已被安全模型覆盖。报告中的方程/性能不外推为2026正文的已验证结论。全文SHA256见访问清单。

2025 ICRA同作者 *The Impact of Sensor Faults on Connected Autonomous Vehicle Localization* 的 DOI线索为 `10.1109/ICRA55743.2025.11127760`；本轮没有取得正式版全文，且作者列表中存在另一题名 *Integrity Monitoring for Centralized Connected Autonomous Vehicles Localization*。本轮不自行断言二者完全同版，也不拿技术报告附录替代正式论文的页码与实验。

## 3. 已有核心文献补核：Hafez等2020固定窗 SS

**版本。** Osama Abdul Hafez, Guillermo Duenas Arana, Mathieu Joerger, Matthew Spenko, *Quantifying Robot Localization Safety: A New Integrity Monitoring Method for Fixed-Lag Smoothing*, IEEE RA-L 5(2):3182–3189；DOI [10.1109/LRA.2020.2975769](https://doi.org/10.1109/LRA.2020.2975769)。本轮重新读取[NSF公开8页正式排版PDF](https://par.nsf.gov/servlets/purl/10203881)，与 PR118 所读文件SHA256一致。本节在旧核查上补齐代码、成本与迁移限制；不将重读计作新增不同文献。

|核查维度|原文锚点与本项目判断|
|---|---|
|输入/状态/故障|p3183式(2)–(10)：非线性绝对、相对测量与随机历史先验，在估计终点线性化；故障幅度确定未知。p3184式(13)按预定义故障位置假设分解风险。它没有预知实际故障身份，要求假设族覆盖或另计未监控项。|
|保证对象|p3185式(29)–(33)的SS界建立在故障假设正确的子解、线性化Gaussian误差及有效协方差上。是当前兴趣方向的条件式风险分析；不能移植成非线性全局/全轨迹保证。|
|固定先验偏移|p3183式(5)的历史先验是带噪声、可带故障的估计；当前项目四行固定survey先验不是同一随机机制。只复制逆信息/自由度会混淆随机与确定输入。|
|相关噪声|原文块噪声与历史先验合同必须在融合前成立。项目若有跨车、跨时刻或先验—数据相关，须重推联合误差；不能把单车白化直接拼接后假定独立。|
|多解与数据选择|p3183式(7)附近使用收敛点Jacobian；没有覆盖全部非线性分支的区间搜索证书。全解和子解各自收敛、检测/选择之后也不能自动继承单一Gaussian误差。|
|删测后可辨识|p3184式(17)及p3185子解协方差使用信息逆。迁移须逐假设查保留行秩、目标方向及偏差列支撑。假设数增加不是信息增加；删掉peer所有行却保留自由b列必然无支撑。|
|搜索域和异常退出|原文不是集合反演算法，未给全域搜索盒、未决盒、空集/无界/超时的外包合同。实际求解拒绝或秩亏，不能自动用有限协方差替代；项目应计为不可用。|
|维数/成本|p3183定义窗状态维数为每时刻m乘窗长；p3188实测m=15，包含姿态、速度和IMU偏置。窗长动态变化，不是固定15维优化。p3186 §VI-A：SS检测要逐假设求子解，CS检测较便宜；p3188 Fig.3及讨论：风险界求值阶段SS更省。应区分“检测成本”和“风险计算成本”，不能笼统写SS每一步更快。|
|实验证据及公平性|p3187同一地标图比较SS/CS，降低地图混杂；窗长随地标数调整。p3187–3189结果是模型风险界/运行成本比较，不是通过罕见失效频数证明风险。绝对故障合同、DGPS、真实IMU和15状态实测，不等于我们的二维已知peer常偏差。没有独立证据把其数值优势移植到低冗余UWB网络。|
|代码/许可|p3189明确给作者仓库，本轮取得固定提交，见下一节。可读不等于已核实可复制许可，更不等于论文精确复现。|

证据质量：**原文可定位且可独立重推SS事件；特定CS印刷公式有明确不一致；代码复现尚未确认**。迁移适用性：**故障族/子解/告警事件接口较强，当前固定先验、多分支及删测弱几何下的直接算法迁移较弱**。

### 独立推导：SS应先做事件检查，而非调阈值

此段是本项目独立代数核查，不是另引一条新算法。设方向误差 `e0 = eh + Δh`，在正确故障假设h下，若未告警蕴含 `|Δh|≤τh`，则

$$\{|e_0|>\ell,\;\mathrm{no\ alarm}\}\subseteq\{|e_h|>\ell-\tau_h\}.$$

这不需要把 `eh` 与 `Δh` 假定独立。若要将右侧写成Gaussian尾界，必须另证子解误差分布；若子解存在固定偏移，其均值不可设为零。若 `ℓ≤τh`，只能退回平凡上界1；若目标方向方差为零，须按确定性事件处理。以残差检验“通过”代替右侧的位置界，没有这条逻辑。

最小后续检查仅需固定仿射模型及预定删行假设：直接代数验证子解的秩、误差/分离相关性和尾事件。失秩或真实故障没有一个清洁且可辨识子解时，否定该条件下的可用SS，而不是调整门槛掩盖。此轮未执行。

## 4. 对PR118的实质补充：确有作者代码，尾项并非印刷疑式

p3189明确链接 [mspenko/RoboticsLab-Integrity-Evaluation](https://github.com/mspenko/RoboticsLab-Integrity-Evaluation)。2026-11-17读取的 `master` HEAD为

`9737f3497c00eff81a32df0d6dbbf3720cfc485e`。

仓库含 `factor_graph_simulation/`、`factor_graph_experiment/`、`utils/class/` 与MATLAB目录。根README只有项目标题，未提供论文固定复现版本映射。根目录没有LICENSE；GitHub license API返回404。递归树因条目多而截断，**不声称穷尽所有嵌套许可文件**；本轮没有确认允许移植该代码的许可，因此候选路线只能借鉴方法，不能默认复制实现。未安装依赖、未执行程序、未做性能复现。

更关键的是，[固定版本 `IntegrityMonitoringClassFgSimOff.py` L137–139](https://github.com/mspenko/RoboticsLab-Integrity-Evaluation/blob/9737f3497c00eff81a32df0d6dbbf3720cfc485e/utils/class/IntegrityMonitoringClassFgSimOff.py#L137) 使用

$$[1-\Phi((\ell-\mu)/\sigma)+\Phi((-\ell-\mu)/\sigma)]\,F_{\chi'^2}(T),$$

即区间**外**尾概率，与PR118对PDF式(35)事件的独立推导一致。它与PDF式(36)/(39)所印区间内CDF差不同。这给出具体反证：**不能由印刷疑点推断作者公开实现同错**。然而该仓库提交未被论文绑定，且本轮只静态读一处函数，仍不能断言论文所有实验都调用此版本或已经完成复现。

PR118原文“未核实作者实现”的访问结论应视为上轮检索边界，本轮追加该新证据；不改历史文献记录。印刷式疑点保留其指定PDF版本，代码证据也单独绑定SHA，二者不可互相替代。

## 5. 最近工作与当前模型的差异（不得预设创新成立）

|比较对象|可核实的相邻点|不能消除的差异/未知|本项目下一步可交付的区别，尚非创新性结论|
|---|---|---|---|
|Kuwada2026指定论文|题名与摘要明确面向协同CAV完好性及不同故障模式|未有全文，方法/定理/成本/代码不可比较；不能判断我们的区域构造是否已包含于其方案|取得全文后逐项对比。此前只登记“共同故障/个体故障应分开”这个待落实的问题，不声称先做。|
|CARNATIONS报告附录A|双车、协同信息、未检测故障、跨车相关|CEKF/DMV、LiDAR/INS；明确排除别车估计偏差引起的相对故障；不是2026定稿|为本项目明确peer距离偏差与共享状态偏差两种合同，不能统称“协同故障”。|
|Hafez2020|多时刻估计与故障假设下的安全事件，SS子解接口|随机历史先验、地图和真实IMU信息；局部线性化；没有全分支可信外包|先以低维全解外包检验当前候选区域遗漏，再决定SS是否有可用子解。已有方法不同不等于研究创新成立。|

**排序建议。** 先做可信外包低维验证；SS暂列第二候选，只推进删测可辨识性与固定仿射事件合同。PR119改善几何后减少了已发现的终点歧义，却没有给全分支证书；而SS依赖清洁且可辨识子解及有效分布，不能绕过该缺口。可靠的“协同对某故障帮助有限”结论即使不利于我们，也应作为故障族设计的约束保留。
