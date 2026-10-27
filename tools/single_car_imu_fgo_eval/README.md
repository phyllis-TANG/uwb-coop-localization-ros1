# B端历史单车IMU因子图输入与核验

遵循`112586c`的[FGO_REDIRECT.md](../../docs/field_tests/20261024_25/imu_parallel_20261027/FGO_REDIRECT.md)。本工具没有定位内核，只准备004023/005135及核验旧因子图；A未交付冻结接口时不运行F1–F3。[中文HANDOFF](../../docs/field_tests/20261024_25/single_car_imu_fgo_eval_20261027/HANDOFF.md)。

每次输出必须为不存在的Git外目录，无`--resume`、无覆盖。使用独立venv及冻结旧依赖：

```bash
python -m venv "$NEW_VENV"
"$NEW_VENV/bin/python" -m pip install -r tools/requirements-single-car-replay.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "$NEW_VENV/bin/python" \
  tools/run_single_car_fixed_lag.py --output "$NEW_RESULTS/legacy"
"$NEW_VENV/bin/python" tools/single_car_imu_fgo_eval/prepare.py --output "$NEW_RESULTS/inputs"
"$NEW_VENV/bin/python" tools/single_car_imu_fgo_eval/verify_packets.py \
  --packets "$NEW_RESULTS/inputs" --output "$NEW_RESULTS/input_readback"
"$NEW_VENV/bin/python" tools/single_car_imu_fgo_eval/verify_baseline.py \
  --packets "$NEW_RESULTS/inputs" --baseline "$NEW_RESULTS/legacy" --output "$NEW_RESULTS/baseline_readback"
"$NEW_VENV/bin/python" tools/single_car_imu_fgo_eval/diagnose.py \
  --packets "$NEW_RESULTS/inputs" --output "$NEW_RESULTS/diagnostics"
"$NEW_VENV/bin/python" tools/single_car_imu_fgo_eval/negative_checks.py \
  --packets "$NEW_RESULTS/inputs" --output "$NEW_RESULTS/negative_checks"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "$NEW_VENV/bin/python" \
  -m unittest discover -s tools/single_car_imu_fgo_eval -p 'test_*.py' -v
```

两份bag已在冻结仓库的协议路径，可直接核对SHA；不用取得聊天中的旧机器目录。可迁移包解压后，`inputs/004023`与`inputs/005135`就是同一接口，无需重新导出。

每个输入目录包括：`events.jsonl.gz`富字段流、`legacy_events.jsonl.gz`旧事件视图、`timing_identity.json`、`input_manifest.json`。富字段每行保留case/原bag SHA、物理record_index、arrival_order_index、话题/连接、原始消息SHA、整数header/receive及相对秒；`message`含原IMU/odom/UWB字段。时间对象保留ROS1的`secs/nsecs`，非有限值存null及原路径/类型。`quality=null`不等于range无效，也不填成零质量。

原IMU占位仅留在legacy视图用于证明F0输入节奏兼容；新模型必须消费富流的实际gyro。other记录保留接收节奏和身份，不作为因子。FGO仍用原Odom pose平移量，**不是旧EKF任务的body速度传播方案**。本轮没有设置新gyro噪声、bias/RW或轴/时钟数值；这些必须等A的合成冻结协议。

`verify_packets.py`只共享IO/hash；数据解析用既有field bag_decoder，与导出器rosbags不同。它不导入在线图或Jacobian。`verify_baseline.py`按独立公式重构到达截止、插值和测距中位数，并比较原发布行；不重求图。`audit_contract.py`为待绑定的A日志提供航向来源、截止、Schur H/g/常数、因子唯一性和全分母覆盖检查；它不是优化器，也不能替代A的真实积分/残差/数值Jacobian核验。

A接口冻结后，按文档的[A_READBACK_REQUIREMENTS](../../docs/field_tests/20261024_25/single_car_imu_fgo_eval_20261027/A_READBACK_REQUIREMENTS.json)建立单独适配器，在新的组合checkout记录确切树/提交。F2/F3预测、初值、启动、回退的Odom角依赖须全部显式；若回退，单列结果。F0–F3的平移/UWB/初值/等待/评价一致，报告全部覆盖和共同有效窗，不只保留IMU可用的好片段。
