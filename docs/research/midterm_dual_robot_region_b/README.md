# B端：真正双车联合区域与计算效率

确定性授权 **44/44完成**，B与锁定A检查器逐证书通过，全量零搜索读回通过（1,134,406节点）。36项开发检查通过。条件随机 **0/240执行**：P4、N4主矩阵总成本中位数分别7.253秒、6.651秒，超过各自2秒门槛。没有重跑正式输入或扩预算。

单时刻、两车XY均未知、4个已知锚点、8条锚点测距＋1条peer、一个有界peer加性偏差、已知正定对角R。J5五维原集合、P4四位置维偏差消元、N4八行无peer基线；完整噪声阈值q9=26、q8=24，来自A冻结的联合风险合同。

- [数学推导](MATH.md)、[实现合同](IMPLEMENTATION_CONTRACT.md)、[冻结协议](PROTOCOL.md)、[用户优先范围](USER_PROTOCOL_PRECEDENCE.md)
- [确定性报告](DETERMINISTIC_REPORT.md)、[成本与区域](COST_AND_REGION_COMPARISON.md)、[协同信息](COOPERATIVE_INFORMATION_REPORT.md)
- [随机跳过原因](SKIPPED_REASON.md)、[唯一下一步决策](DECISION_MEMO.md)、[文献迁移接口](LITERATURE_TRANSFER_NOTE.md)
- [交接与复核](HANDOFF.md)、[完整运行分母](results/RUNS.csv)、[来源锁](SOURCE_LOCK.json)、[输入](INPUTS.json.gz)

主矩阵平均全流程J5/P4成本比4.62，但J5有9/12次盒预算停止，不能解释成相同有限外包精度的加速保证。共线镜像保留；peer可约束联合组合，不能保证每辆车边缘必然缩小。唯一主优先项是优化独立A认证重复计算，暂不进入两时刻。

便携证据由evidence/内18个压缩分片组成；RESULTS_READY.json发布后为统一入口，固定文件哈希、执行冻结和完整分母。A归档格式要求48条，额外4条特殊N4明确NOT_RUN（不在用户授权44计划中）。源码只新增B的两个目录；不修改A或公共配置，不运行设备，不自动合并。

执行核心仅需Python3.10标准库。可重定位A来源，但须匹配SOURCE_LOCK全部哈希；详见HANDOFF。正式记录仅做零搜索读回，不能重跑改变原计时。
