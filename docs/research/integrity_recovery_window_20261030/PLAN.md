# 运行前短计划
基于7001d33da1f77875aa9cd2adbd7ffd155bc13610；独立分支analysis/20261030-integrity-recovery-window-v1。现场46GB空闲；进程视图仅当前命名空间，不断言宿主无任务。无适用AGENTS。原Python3.10.12 numpy2.2.6 scipy1.15.3；不用Decimal。只新增本任务tools/docs。读取main上的research_convergence README/TARGET_CARD/REPRODUCTION，记录其Git blob SHA；不合并main。
仅5101 nominal/wall_long两个开发单元。原冻结核74fa210e及19文件SHA不变，原prefix config/events/truth canonical严格匹配旧INPUT，失败即停计算，不刷新SHA。原prefix事件不改任何字段/顺序/receive。无原始输入全副本保存。
独立尾段seed610301仅开发：64.05至90秒，20Hz，每车依次抽520x3 Odom增量(.002,.002,.0008)，再520x5 raw range(.04)，两条件完全相同。延续原analytic轨迹/天线，Odom从64秒累计值接续，receive延迟公式继续用原全局sample index。原DURATION_NS保持不变。尾段来源SHA引用base nominal canonical与规则/seed；truth仅评价。
预检：前缀SHA及逐字段保持、尾段两条件严格相同、1040个Odom接续用独立标量旋转计算核对（标量vs矩阵算术预登记atol1e-14，仅尾段连续性）。旧前63发布优先严格相同，声明与输入必须严格相同；若数值不精确，仅列差异，不采用新容差放行。既有独立有限差分/Schur核验保持原规则。
原primitive只至63：在64首次update追加新列，旧列顺序不变；四图prior_b右补零，绝不重置prior。这是时域索引扩展，不改噪声尺度/监测假设/算法。保存63/72/73/80/89完整四图线性/primitive/prior与活动来源；全时段保存消元证据。原监测所有源组保留。
先提交包装器/计划，再precheck并提交检查点；通过后两单元各只运行一次。若旧前缀输出不匹配标复现失败，不解读新尾段为旧运行延长。预算100MB，每单元前留10MB及500MB空闲，TEMP/TMP/TMPDIR为本目录tmp。失败不覆盖。
按实际bin中header与故障[24,52)相交、实际图活动times确定退出时刻，混合bin保留。评价pre/fault/结束后仍有故障bin/完全退出后至90；AL.05/.10/.20，不作应用容差。报告逐车分离/协方差/统计量/声明/误差，HMI及含unknown越限未报警、报警/可用、恢复代价与nominal配对。state与虚拟可获得时间/实测耗时分列，不称实车实际保护时间。
若自然恢复收缩主张；否则先检查活动源与prior/协方差，不开发恢复规则。
