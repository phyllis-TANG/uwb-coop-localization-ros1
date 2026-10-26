# A端中文交接：开发层完成

分支：`analysis/a-side-se2-integration-20261027`。冻结执行提交：`7896c82d2454b67ea388341484a93c2265a209fb`；起点：`32445a299b3f4674b865c4d78c4f662e51b5b857`。交付提交见草稿PR的HEAD，后续仅报告/归档补充。

**实际完成**：同PR46/48六维SE(2) EKF的9组比较；47原基线+17参数+25集成测试=89项通过；60正式共享输入完成、20角色重复去重，估计365.36s，失败/超时0。全量回读417,300输入事件、522,720逐车发布状态及3,240指标行通过；原窗口目录保持干净。另保留两版各4个smoke及诊断变更源码，输入/发布状态/指标逐字节相同。

**主要发现（合成开发）**：持续peer偏差时Car1的joint/Huber/gate+cap/组合RMSE约.174/.139/.165/.034m，不能声称门控必胜；正确peer下弱Car2的joint=.168、组合=.224、独立=.277m，保护损失协同收益；自洽故障下受影响车仍约.8m。gate+cap实际仅1次clip，限幅单独效应证据很弱。shadow-only控制有时优于组合，全部负结果保留。5个配对seed簇不是60个独立seed；PSD/cap不是误差保护级。

**失败与BLOCKED**：ensurepip缺失已换隔离安装；首次集成测试2问题已修复，日志保留。T10实际严格编译缺14组来源字段/8个基线条件，仍BLOCKED；无bag读取/定位/现场ATE或RMSE，参考not_accepted。T09/T11/T13/T15未定位回放或调参。

**产物**：[结果与图表](REPORT.md)、[配置](frozen_protocol.json)、[测试/实验索引](RESULT_INDEX.json)、[归档与SHA](artifact_manifest.json)。完整包约672MB，位于NAS `//10.22.5.135/data/uwb_coop_artifacts/a_causal_reliability_20261027/`；已取回验证全部779个清单文件及20源码哈希，解包后实际回读通过。需LAN/VPN/NAS权限，无公开HTTP链接；不冒称另一物理机器执行验收。

**复核/续跑**：从归档根执行 `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python source/tools/field_20261024_25/causal_reliability/verify_outputs.py --results matrix --output new_readback.json`。正式矩阵已完成，无需重跑；真正中断时严格同指纹加`--resume`，详见README。累计预算从18:15:14Z计6小时，未重置。

**下一步三件事**：①协调验收B的T10实际初值/记录绑定、水平杆臂与时间来源，再接同一因果入口；②建立合格独立参考，针对墙/peer自洽错误验证，保留现场精度空值直到验收；③另起预登记的小型单因素试验，分离非反馈保持、gate和罕见cap的作用，复验弱Car2反例，继续关闭整包留出。
