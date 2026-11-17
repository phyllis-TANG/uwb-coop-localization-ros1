# 本批实测处理统一入口

本目录接续PR130短窗阶段，完成PR128五包的数据处理、时序/坐标合同、四动态包全段四方法对照、旧端点诊断和统一数值恢复。历史源码、原bag与旧结果只读。

阅读顺序：REPORT.md → OBSERVATION_CONTRACT.md → DECISION_MEMO.md。PROTOCOL.md为第一批38调用协议；NUMERICAL_RECOVERY_PROTOCOL.md记录新增16调用的单次统一开发性恢复。两次均先提交后执行，不隐去原失败。

目录：
- CONFIG/ACCEPTANCE/FREEZE：参数、零求解器验收、初始来源哈希。
- RECOVERY_CONFIG/RECOVERY_FREEZE：全部16端点的P2恢复身份与预算。
- results/：P0/P1及旧六端点继续结果、全五包覆盖/时钟/静态几何、弱方向诊断。
- results_p2/：P2全16项、轨迹、偏差、残差、方法间变化及人工末点差。
- portable.json.gz：两个执行目录完整JSON回执/输入/端点，原bag不重复提交。

Python 3.10、numpy 2.2.6、scipy 1.15.3、matplotlib 3.10.9、rosbags 0.10.11。现有独立环境/home/ubuntu22/uwb-field-moon1-integration-artifacts/venv；无需GPU或ROS运行时。

零求解器复核，解包/输出路径必须不存在：

```bash
set -e
PY=/home/ubuntu22/uwb-field-moon1-integration-artifacts/venv/bin/python
$PY tools/field_moon1_integration/unpack.py docs/research/field_completion/portable.json.gz /tmp/field-completion-restore
OPENBLAS_NUM_THREADS=1 $PY tools/field_completion/readback.py /tmp/field-completion-restore/batch /tmp/field-completion-check-p1
OPENBLAS_NUM_THREADS=1 $PY tools/field_completion/recovery_readback.py /tmp/field-completion-restore/batch /tmp/field-completion-restore/recovery /tmp/field-completion-check-p2
```

完整输入重新核验（需要原bag）可用accept.py向新的JSON路径输出；不调用优化器。运行器execute.py/recover.py已经完成，不应再次运行。现有结果目录和孤立attempt均拒绝自动重跑。

F0/F1/F2/F3表示实测SE(2)目标下的四模型家族，不与Moon_1的数值目标或状态维数混同。没有连续真值、没有风险或保护级声明，formal_runs=0；同包的多个方法和时刻不增加独立实验数量。

复核在上述固定依赖环境下完成；Jacobian字节哈希是严格环境回执，不保证跨BLAS/硬件逐位相同。更换平台时应保留原回执并独立容差核对，不能据此重跑或改写旧优化结果。
