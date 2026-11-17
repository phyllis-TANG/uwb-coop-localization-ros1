# 先验精度证据清单

以下为固定 PR109 提交树内可取得资料的核查，不宣称覆盖外部实验笔记或现场未归档信息。四类误差（锚点坐标、机器人/tag初始位置、安装外参、测距偏差）不可直接混用。1–2cm 自报估计不等于已证实精度。

|主题|来源路径|实际记录/性质|能否约束当前先验|缺口|
|---|---|---|---|---|
|直接测距参照|`datasets/field_raw/20260927/notes/live_field/TWO_CAR_PA0_PB1_static_LOS_camera_clear_facing_GT1p85m_20260927_063345_ground_truth.txt`|卷尺量天线参考点间距1.85m，approximately .01m不确定度；实测记录+未经定义的精度估计|仅约束该次标量距离参照；不能转换四维XY先验sigma|覆盖概率、校准、重复读数、两车全局坐标误差|
|tag参考位置|`datasets/field_raw/20261011/notes/live_field/MOBILE_P1_h0p20_clear_A_20261011_014350_survey.txt`|人工参考XYZ=[2.01,1.99,.20]；人工记录|可核对该次名义/人工参考位置；无法建立误差分布|工具、坐标原点实现、重复测量、真值精度|
|重复采集|`datasets/field_raw/20261011/notes/live_field/MOBILE_P1_h1p00_clear_R1_20261011_020429_survey.txt`|R1人工参考[2,2,1]；人工设定/记录，测量过程未确认|R1/R2是UWB重复采集，不证明XY独立重复读数|独立参考测量读数、工具与方差|
|安装外参|`datasets/field_raw/20261018/notes/live_field/antenna_mount_survey_20261018.txt`|手工量相对近似底盘几何中心Car1[.08,-.06]、Car2[.12,-.08]，odom对应待核；实测人工安装记录|外参来源，不是机器人全球起点精度；不追溯历史安装|原点对应、角度、重复读数、外参协方差|
|锚点/坐标系/安装|`docs/field_tests/20261024_25/geometry.json`|历史锚点沿用、fresh_survey_date及uncertainty为null；房间/odom不直接等同；部分目标名义值；历史测量复用+人工名义值+计算值混合，字段区分|不能把锚点坐标小数位解释为定位先验精度|新测日期、工具、原点、相关误差、外参旋转和不确定度|
|锚点坐标来源|`docs/field_tests/20261017/session_config.json`|现场session引用的锚点坐标配置；配置保存的测量来源，精度待确认|几何输入来源，不是误差上界|校准及重复测量报告|
|现场交叉核对|`docs/field_tests/20261024_25/SESSION_LOG_ARCHIVE.md`|直接卷尺2.08m与XYZ推算2.061771m均保留；人工标记非连续计量真值；安装可能变化；实测+计算+操作者说明|1.82cm差额提示核对问题，不是标准差；不同日期安装不混用|独立全局XYZ复测、姿态/参考点一致性|
|停车点参考|`docs/research/paper_evidence_completion_20261103/references/A1_DEV_RESTART_20261101T081711Z.bag.notes.txt`|Car1(1.51,3.99)，Car2起点(2.02,2.01)、B(2.74,2.01)、C(3.49,1.90)、返程(2.02,2.04)；operator estimate1–2cm not certified；操作者现场人工测量记录；1–2cm是自报估计|存在实际停车点资料，但不同位置不能当同一真值重复测量，不能认定sigma=.01/.02|测量工具/校准/基准坐标误差、独立重复、同点重复读数|
|参考值交叉检查|`docs/research/paper_evidence_completion_20261103/references/A1_B_reference.json`|直接2.37m与坐标水平距离2.330944m；未调坐标；人工读数+派生计算|不闭合约3.89cm（高度修正前）不应被消除或视为误差分布|差额归因、工具误差、共同坐标误差|
|示例软件配置|`ros_ws/src/uwb_coop_localization/config/anchors.yaml`|文件明确simulation only，需换实测坐标；人工仿真示例|不能用于真实平台先验精度|现场测量关联|
|本研究survey/先验|`docs/research/midterm_prior_mechanism_b/CONFIG.json`|survey为固定人为偏移；sigma=.5/.05；fixed_correct/random_correct依赖truth；人工仿真假设|适用机制隔离，不是实车标定证据|survey误差来源、4维偏移集合/协方差|
|先验生成实现|`tools/midterm_prior_mechanism_b/adapter.py`|fixed_correct用truth；random_correct独立stream2高斯；survey积分初值不变；计算定义|证明控制变量实现，不证明现场精度|实车先验生成和误差机制|
|较早二手审计|`docs/research/reference_resolution_audit_20261029/REPORT.md`|区分参考分辨率、UWB重复性与计量准确度；派生分析|辅助定位缺口；日期早于11月停车点记录，不能代替最新证据|原始测量误差模型|

所有表行固定提交与文件SHA256见 EVIDENCE_INVENTORY.json。PR108仅作只读数学解释参考：41ba0d3a6e69897ef6330cc9ad218253c7fb80ea 的 docs/research/midterm_joint_coverage_a/MATRIX_DEFINITIONS.md 与 REPORT.md，区分曲率逆、固定先验噪声传播与均值偏移；不作为实际测量精度证据。

结论：有人工现场坐标和安装记录，但尚无足够材料把仿真survey偏移、.5/.05m Gaussian标准差或.05m确定半径赋予实际平台误差含义。测距重复性、锚点坐标小数位、标量卷尺估计和机器人四维先验不是同一种证据。下一步先整理已有工具/坐标定义/重复读数及外参对应资料，不要求本轮重新采集，不改历史记录。
