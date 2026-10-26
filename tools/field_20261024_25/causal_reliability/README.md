# 同一六维SE(2) EKF的peer可靠性机制

先读 `docs/field_tests/20261024_25/causal_reliability_20261027/SPEC.md` 与冻结协议。
本目录复用 PR46/48 的原 Baseline；不导入 PR47 四维 Estimator。唯一既有代码修改是 model.py 的可选 peer_policy，默认 None；原三方法逐位回归通过。

9 个比较方法：odom_only、independent、joint、huber、gate_only、cap_only、gate_cap、shadow_only、gate_cap_shadow。后两者不反馈peer，shadow_only控制额外的输出保持/失效策略。限幅缩放三维车辆增益，使用缩放增益的Joseph协方差；工程协方差不是校准后验。

所有运行需要 `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`；Python依赖为NumPy，报告另需Matplotlib。正式执行环境/版本随run.json登记；本轮隔离版本NumPy2.2.6/Matplotlib3.10.9。大产物必须放Git外新目录。

```bash
python -m unittest discover -s tools/field_20261024_25/causal_reliability -p 'test_*.py' -v
python tools/field_20261024_25/causal_reliability/preflight_t10.py --output "$RESULT_ROOT/t10_preflight"
python tools/field_20261024_25/causal_reliability/run.py --output "$RESULT_ROOT/smoke" --smoke
python tools/field_20261024_25/causal_reliability/verify_outputs.py --results "$RESULT_ROOT/smoke" --output "$RESULT_ROOT/smoke_readback.json"
# 提交源码/协议后才启动正式矩阵；第一次不用--resume。
python tools/field_20261024_25/causal_reliability/run.py --output "$RESULT_ROOT/matrix"
python tools/field_20261024_25/causal_reliability/verify_outputs.py --results "$RESULT_ROOT/matrix" --output "$RESULT_ROOT/matrix_readback.json"
python tools/field_20261024_25/causal_reliability/report.py --results "$RESULT_ROOT/matrix" --verification "$RESULT_ROOT/matrix_readback.json" --output "$RESULT_ROOT/report"
```

run.py只按协议的原累计任务截止时间执行，不偷偷重启6小时。截止后本轮只做归档/汇报；将来新的运行预算需另存显式修订协议，不改旧证据。恢复用相同命令加 `--resume`；输入、源码、配置、依赖和既有输出/单元run.json任何哈希不符均拒绝，不覆盖旧输出。失败/未完成单元不自动重跑。T10预检查退出2表示真实BLOCKED；没有读取bag，更没有现场精度结论。

每个实际输入单元包含精确ns输入、真值/标签隔离文件、逐事件所有方法的反馈/影子状态及协方差、完整准入/门控/限幅、逐发布状态、estimate.csv、分车分阶段指标与计算时间。verify_outputs.py独立重算三维peer几何、六维Jacobian、gate恢复、增益/Joseph/cap/保持及分车指标；不导入估计器、生成器或评价器。

全部是开发证据。T09/T11/T13/T15不定位回放、不调参；T10缺初值/杆臂/时间来源时保留BLOCKED，不用Odom或未批准视觉当真值。
