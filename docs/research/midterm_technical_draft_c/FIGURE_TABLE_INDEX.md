# 图表、完整矩阵与固定来源索引

本文件是证据附件。正文保留代表结果；本附件保留全条件矩阵、全部方法、95%/99%名义阈值以及不利条件。图像均逐字节复用，未重画、未裁去极端点；PR108来源从独立只读checkout读取。复制清单、固定完整提交、源路径及SHA256见 [SOURCE_COPIES.json](evidence/SOURCE_COPIES.json)。此处的可用性是区间可计算性，不等于数值驻点，也不等于定位正确。

## 固定来源身份与历史对应

|来源短码|固定提交|路径与内容核验|历史对应|
|---|---|---|---|
|R0|`c51411433d30dc379bd69cf5fb20a11e196b7182` 中保留的原确认资料|`../midterm_simulation_confirmation/REPORT.md`、`HANDOFF.md`及结果：36条件、50seed、7200方法|冻结执行来源为 `6317e977572b4e8fb8282211485356562ddc62d2`；不把后续分析当新运行|
|R106|`d39c99589bd15938484d64871981d45a9dd74efe`|`../midterm_uncertainty_a/REPORT.md`、`ANALYSIS_PROTOCOL.md`、`HANDOFF.md`、`EVIDENCE_MAP.csv`：恢复原7200终点、0优化器调用|内容交付提交 `eee2a6061fa13fa8415c6e46577204b232206aa1`，随后审查头规范化清单；固定来源为PR106审查头|
|R107F/R107N|`afafabbd2b7f8f25fe38ba99f539dab8baf2491c`|`../midterm_mismatch_b/`与其`noise_exploration/`：fault 28800，noise 14400；父HANDOFF/清单覆盖两个批次|故障交付 `7abe9b152028b73f23a2fdeab28b9647f0fc04d7`；独立噪声协议冻结 `54ac42b60a11a0666e8840cf5bd8417a02a677e1`；审查头收窄便携清单|
|R108|`41ba0d3a6e69897ef6330cc9ad218253c7fb80ea`|`docs/research/midterm_joint_coverage_a/`报告、协议、HANDOFF、矩阵定义、汇总表和图：复用43200结果，无新观测/定位运行|`git show --stat`核对该提交新增完整分析交付；该路径不在固定PR109开发树中，因此单独复制证据附件|
|R109|`c51411433d30dc379bd69cf5fb20a11e196b7182`|`../midterm_prior_mechanism_b/`报告、协议、HANDOFF：14400非线性+14400真值线性化诊断|协议先冻结于 `5223d08ed219bafeb092df6f598b842308dee33e`；指定提交新增完整结果、全范围散点与失败记录|

关联不是按目录名猜测：已比较 `git log -- <报告路径>` 的首次内容提交、`git show --stat <审查提交>` 的变更清单、报告中的冻结提交/运行计数以及各协议和HANDOFF。当前GitHub合并状态不作为来源身份；此处所有链接和索引固定到上述提交。

## 正文候选图及完整图

图号可随整份中期报告排版统一。以下F编号是稳定证据编号，不与正文自动图号绑定。

|编号、文件|条件与指标|独立样本量、统计口径|限制与正文用途|
|---|---|---|---|
|F01 [全部范围线性/非线性误差](figures/prior_linear_nonlinear_full_range.png)|R109全36条件、B0–B3、两车；横轴真值线性化MSE，纵轴非线性MSE，单位m²|每条件100独立seed；各方法每车36个条件均值点，使用全部有限终点，含未驻点；对数轴覆盖所有数值|理想线性参照；条件/方法共享seed，图中点数不等于独立样本数；MSE较小不等于覆盖更好；适用§4.5|
|F02 [噪声机制与覆盖](figures/noise_explanations.png)|R108三噪声×四方法×两车；A_total/B_iid/C_true_noise，名义95%点平均覆盖|每噪声24条件等权描述均值；每条件50seed、每车300点；无跨条件合并CI；+标未驻点存在，x标预算耗尽存在|C知道生成噪声Ω，估计位置不改变；不将均值视为全条件校准；适用§4.4，与n32反例并列|
|F03a [Car1全部先验条件覆盖](figures/prior_coverage_car1.png)|R109全36条件、四方法、非线性/线性、曲率候选95%/99%点覆盖|每条件100独立seed、每车600点；全部有限结果；方法和诊断配对|完整矩阵用于核对极低覆盖条件，不跨格推风险；适用§4.5和附件|
|F03b [Car2全部先验条件覆盖](figures/prior_coverage_car2.png)|同F03a，Car2|同F03a|与Car1并列，避免双车平均掩盖单车失败|
|F04a/b [故障95%](evidence/pr108/fault/coverage_95.png) / [故障99%](evidence/pr108/fault/coverage_99.png)|R108全72故障条件×四方法×两车×三视图|每条件100seed、每车600点；保留数值状态和全部有限终点|错误候选/多链路零覆盖未删除；0/600并不证明真实概率为0|
|F05a/b [噪声95%](evidence/pr108/noise/coverage_95.png) / [噪声99%](evidence/pr108/noise/coverage_99.png)|R108全72噪声条件×四方法×两车×三视图|每条件50seed、每车300点；两批seed不可混为同一批|真实Ω后仍有欠覆盖；不得只展示平均改善|
|F06 [原确认逐车配对收益](../midterm_simulation_confirmation/figures/position_gains.png)|R0全部36条件，B2与B1/B0比较|每条件50seed配对；逐项95%bootstrap；未驻点终点保留|不作多重比较家族保证，不把24个相关区间称24次独立确认|
|F07 [PR106强先验](../midterm_uncertainty_a/figures/strong_prior.png)|PR106先验中心/强度条件与误差、预测尺度|每条件50seed；同seed配对；全部保存有限终点|错误中心效应不等于所有强先验都变差|
|F08 [完整S1b秩与偏差信息](../midterm_simulation_s1b/results/rank_and_bias_information.png)|指定真值点、18主场景和peer-only负对照|确定性线性化诊断；本图无可被解释为独立性能样本的n|总体秩亏、偏差可辨识、有限噪声精度分开；不当作罕见风险证据|

推荐图注（F01）：**36个预设条件下两车的线性与非线性均方误差对照。** 每条件100个独立seed，四方法共享观测；每点是同条件、同方法、同车的seed平均MSE（m²），包括未驻点有限终点。横轴是使用真值展开的理想线性诊断，纵轴是原非线性结果。对数轴保留全部极值；方法调用、车辆及线性参照不增加独立样本量，图不提供覆盖或风险保证。

推荐图注（F02）：**噪声失配下三种局部不确定性视图的95%点平均覆盖。** 每个柱为24个条件的等权描述均值，每条件50个独立seed、每车6时刻，共300相关点；四方法及全部不利条件保留。+和x分别标记存在未驻点与预算耗尽结果。真实Ω视图仅为离线传播参照，没有重估位置；不提供跨条件总体置信区间，均值改善不能掩盖n32等残余欠覆盖。

## 正文代表表的可追溯入口

|表内容|固定来源与选择键|正文必须同时保留的口径|
|---|---|---|
|实测D/C/T及逐车校正交互|[MODEL_AND_CALCULATIONS](../conference_paper_v003_20261101/MODEL_AND_CALCULATIONS.md) §4–5；固定R109树；CLAIM C005–C012|单位m²；同bag共同有效时刻；先算bag再G1两包/G2三包等权；人工参考敏感性不是CI|
|原确认B0–B3与失败数|[确认REPORT](../midterm_simulation_confirmation/REPORT.md)数值表、`results/NONACCEPTED.csv`；C025–C028|50seed/条件；7200方法调用；25未驻点保留|
|故障失配B2覆盖代表表|[fault DESCRIPTIVE](evidence/pr108/fault/DESCRIPTIVE.csv)：`method=B2,view=A_total,level=.95`；C041|每类12条件等权描述均值及范围；每条件100seed、600点；不是合并7200个独立点|
|噪声B_iid→C_true_noise|[noise DESCRIPTIVE](evidence/pr108/noise/DESCRIPTIVE.csv)：`method=B2,view∈{B_iid,C_true_noise},level=.95`；C043|每类24条件等权；每条件50seed；估计中心不变|
|残余欠覆盖n32|[noise COVERAGE](evidence/pr108/noise/COVERAGE.csv.gz)：`id=n32,method=B2,view=C_true_noise,car=1,level=.95,subset=all,aggregation=point_average`；C044|221/300，CI按50seed整簇；all_times另为34/50|
|均值偏移m28|[fault MOMENTS](evidence/pr108/fault/MOMENTS.csv.gz)：`id=m28,method=B2,car=1,view=C_true_noise`六时刻；C042|MSE与样本中心方差ddof=1关系含(n−1)/n；不能误把mean²+ddof1 trace直接相加|
|先验机制六组|[R109 B2_FULL_MATRIX](../midterm_prior_mechanism_b/B2_FULL_MATRIX.md)、`results/SUMMARY.csv`与`COVERAGE.csv`：weak、bias=.3、B2、sigma=.5/.05、三机制；C049–C052|每条件100seed；表内非线性/线性结果配对；点覆盖和轨迹全覆盖分开|
|传播块奇异与未驻点|[R109 REPORT](../midterm_prior_mechanism_b/REPORT.md)、`results/COUNTS.json`与`COVERAGE.csv`；C046–C047|691200个二维块中6400奇异；该块计数只选单一名义水平、point_average、all避免95/99与子集重复；65未驻点仍在主表|

## 完整矩阵附件入口

PR108复制表保留原压缩文件，不重新计算和筛选。故障与噪声分别有110592行位置覆盖、1728行偏差表；故障偏差真值仅zero/constant正确候选适用。`subset`、`aggregation`、`available`、`unavailable`、`covered_over_full_plan`和原因列不能省略。

|研究问题|完整表位置|包含内容|
|---|---|---|
|R106原确认不确定性|`../midterm_uncertainty_a/results/`|`COVERAGE.csv.gz`、`BIAS_COVERAGE.csv.gz`、`EMPIRICAL_MOMENTS.csv.gz`、`PRIOR_COMPARISONS.csv`、`NOT_STATIONARY.csv`；36条件、50seed、三矩阵、95/99|
|R107故障定位误差|`../midterm_mismatch_b/results/`|`PER_RUN.csv`、`SUMMARY.csv`、`PAIRED_INTERVALS.csv`、`FAILURES.csv`、`NONACCEPTED.csv`；72×100×4|
|R107噪声定位误差|`../midterm_mismatch_b/noise_exploration/results/`|`PER_RUN.csv`、`SUMMARY.csv`、`NOISE_CONTRASTS.csv`、数值失败与误差超阈表；72×50×4|
|R108故障覆盖|[fault](evidence/pr108/fault/)|`COVERAGE.csv.gz`、`BIAS_COVERAGE.csv.gz`、`MOMENTS.csv.gz`、`PAIRED.csv.gz`、`CHECKS.json`、`DESCRIPTIVE.csv`、95/99图|
|R108噪声覆盖|[noise](evidence/pr108/noise/)|同上，独立于fault批次，不合并种子|
|R109先验和线性诊断|`../midterm_prior_mechanism_b/results/`|`SUMMARY.csv`、`COVERAGE.csv`、`MOMENTS.csv`、`LINEAR_ANALYTIC_COVERAGE.csv`、`BIAS_COVERAGE.csv`、`PAIRED_COMPARISONS.csv`、`FAILURES.csv`和`COUNTS.json`；36×100×4×两类型|

## 只读核验

执行 `python3 evidence/verify_sources.py`（可在任意cwd指定完整脚本路径）会核对全部复制品SHA、PR108完整覆盖行数、wrong_link/multi_link全12条件零覆盖、n32计数、PR109关键覆盖、方法调用/65未驻点以及6400奇异块。输出 [NUMERIC_READBACK.json](evidence/NUMERIC_READBACK.json) 已保存为本次只读核对结果。脚本不调用定位后端、优化器、随机抽样或仿真，不改历史结果；输出重定向到新路径即可再次核验。

来源文件的更完整逐结论行号、成立条件和限制见 [CLAIM_EVIDENCE.csv](CLAIM_EVIDENCE.csv)。未找到原始材料的内容进入OPEN_QUESTIONS，不凭目录或聊天摘要补造公式与风险保证。
