# A端同六维EKF交付入口

本轮已实际完成同一六维SE(2)因果EKF的集成、89项相关测试、两版各4个48秒smoke、60个正式开发组合、全量独立回读和NAS归档取回验证。**只有合成开发层完成；T10严格room回放仍BLOCKED。** 没有现场精度结论或方法成功/安全保证。

先读[一页交接](HANDOFF.md)、[结果审阅及负结果](REPORT.md)，再读[SPEC](SPEC.md)、[冻结协议](frozen_protocol.json)、[结果索引](RESULT_INDEX.json)。执行源码提交为 `7896c82d2454b67ea388341484a93c2265a209fb`；当前PR后续提交只补审阅报告、图表和归档凭据，不改变这份执行源码。

- 80计划行=60实际共享输入+20明确去重；9方法共540条方法轨迹，5个配对seed簇。全部60完成，失败/超时0；[完整索引](results_summary/experiment_index.json)。
- [逐车/场景/阶段配对摘要](results_summary/paired_seed_summary.csv)、[重点数值](results_summary/key_findings.csv)、[精确gate发布轴转换](results_summary/gate_publication_transitions.csv)、[可用性与回退](results_summary/availability_rows.csv)。全量3240行分车指标及逐时刻结果在归档，不将全量结果提交Git。
- [独立回读](results_summary/independent_readback.json)、[去重输入SHA复核](results_summary/aliases_verified.json)、[诊断变更前后smoke等价](results_summary/smoke_diagnostic_equivalence.json)、[执行源码锁](results_summary/execution_source_lock.json)、[实际命令与耗时](results_summary/COMMANDS.json)。
- [T10精确缺项](results_summary/T10_BLOCKED.json)及[保持pending的严格配置](results_summary/T10_strict_config.json)。只核对冻结起点已有模板，未读取bag；不推断B端当前进展。
- [完整归档位置、SHA与权限范围](artifact_manifest.json)、[NAS取回与解包检查](results_summary/archive_retrieval_verification.json)。已有认证SMB共享，需LAN/VPN与NAS权限；不是公开HTTP链接。取回验证在本机新目录，未冒称另一物理机器验收。

三类图：[真值/发布轨迹](results_summary/peer_bias_trajectory.png)、[误差/监测/故障](results_summary/peer_bias_error_monitor.png)、[配对分车代价](results_summary/paired_fault_delta_reviewed.png)；另有[计算成本](results_summary/compute_cost.png)。热图色条布局修订单独保存，旧自动图在归档原样保留。报告补充脚本位于本目录，仅处理已冻结结果，不属于估计器源码变更。

## 复核与续跑

从NAS取回并核对压缩包SHA后解包，在新环境安装NumPy2.2.6（绘图另用Matplotlib3.10.9），从包根目录执行：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python source/tools/field_20261024_25/causal_reliability/verify_outputs.py --results matrix --output new_independent_readback.json
```

源码/数据路径均相对归档，不依赖原工作树或.git。本轮实际已从复制目录完整回读，并从NAS取回归档逐文件核对、用解包源码回读一条实际48s单元。

正式矩阵无剩余单元，无需重跑。仅在同一轮真正中断且所有来源/配置/依赖/输入/输出哈希匹配时，在原工作树/相同输出目录执行：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/field_20261024_25/causal_reliability/run.py --protocol docs/field_tests/20261024_25/causal_reliability_20261027/frozen_protocol.json --output <原Git外matrix目录> --resume
```

原协议截止时间绑定本轮从2026-10-26T18:15:14Z开始的6小时预算；不能通过恢复偷偷重置。未来新预算需显式另存修订协议并开新指纹/新输出。回读旧产物不受运行预算截止限制。

初始化与依赖安装失败、首次新增测试错误和修复日志均在validation/及归档checkpoints。原三基线47项回归、参数17项、最终集成25项通过；不是把重复执行累计成更多独立测试。留出T09/T11/T13/T15没有定位回放、评价或调参；不启动实车/ROS、不改原件、Release、公共几何或B端文件，不自动合并。
