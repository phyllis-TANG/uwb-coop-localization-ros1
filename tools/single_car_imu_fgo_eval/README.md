# B端历史单车IMU因子图输入与核验

遵循`112586c`的[FGO_REDIRECT.md](../../docs/field_tests/20261024_25/imu_parallel_20261027/FGO_REDIRECT.md)。本工具没有定位内核；已准备004023/005135并复现旧图，接入A冻结接口后完成F0–F3条件性运行与独立核验。[中文HANDOFF](../../docs/field_tests/20261024_25/single_car_imu_fgo_eval_20261027/HANDOFF.md)。

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

原IMU占位仅留在legacy视图用于证明F0输入节奏兼容；新模型必须消费富流的实际gyro。other记录保留接收节奏和身份，不作为因子。FGO仍用原Odom pose平移量，**不是旧EKF任务的body速度传播方案**。第一阶段没有设置新gyro参数；第二阶段已采用A合成前冻结值，并把轴/时钟另列为未验证工程假设，详见下文。

`verify_packets.py`只共享IO/hash；数据解析用既有field bag_decoder，与导出器rosbags不同。它不导入在线图或Jacobian。`verify_baseline.py`按独立公式重构到达截止、插值和测距中位数，并比较原发布行；不重求图。`audit_contract.py`为待绑定的A日志提供航向来源、截止、Schur H/g/常数、因子唯一性和全分母覆盖检查；它不是优化器，也不能替代A的真实积分/残差/数值Jacobian核验。

A接口冻结后，按文档的[A_READBACK_REQUIREMENTS](../../docs/field_tests/20261024_25/single_car_imu_fgo_eval_20261027/A_READBACK_REQUIREMENTS.json)建立单独适配器，在新的组合checkout记录确切树/提交。F2/F3预测、初值、启动、回退的Odom角依赖须全部显式；若回退，单列结果。F0–F3的平移/UWB/初值/等待/评价一致，报告全部覆盖和共同有效窗，不只保留IMU可用的好片段。

## 已冻结A接口后的第二阶段（已实际完成）

上文为第一阶段说明；当前已用PR58确切`e3a20fe04a6d53973696ec055dbc71eb135e0f77`完成八个条件性F0–F3运行，不是等待A。`field_protocol.json`于`db36166`在实包前冻结；参数与未验收项见中文报告。A的全套合成不在B重复。只建立执行组合checkout，不将A合入B交付分支；实际组合`f00c8743ac9c47d967817af448d3cd3fc80e8b79`可由独立执行分支取得。

```bash
# 例：每个目标路径必须是不存在的Git外新目录；已经完成的名义运行无需重跑。
git fetch origin analysis/20261027-single-car-imu-fgo execution/20261027-fgo-e3a20fe-b-stage1
git worktree add --detach "$NEW_A_TREE" e3a20fe04a6d53973696ec055dbc71eb135e0f77
git worktree add --detach "$NEW_EXEC_TREE" f00c8743ac9c47d967817af448d3cd3fc80e8b79
"$NEW_VENV/bin/python" -m pip install jsonschema==4.25.1
"$NEW_VENV/bin/python" tools/single_car_imu_fgo_eval/adapt_field.py \
  --packets "$INPUTS" --A-checkout "$NEW_A_TREE" --output "$NEW_ADAPTED"
# 在干净执行树中，每包分别运行F0/F1/F2/F3，先F0回归；旧输出保留：
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "$NEW_VENV/bin/python" \
  "$NEW_EXEC_TREE/tools/single_car_imu_fgo/replay.py" \
  --events-jsonl "$NEW_ADAPTED/004023/events.jsonl.gz" \
  --config "$NEW_ADAPTED/004023/F3.json" --output "$NEW_F3_RUN" --max-seconds 120
# 在B工具checkout中回读完整8运行矩阵（目录名004023_F0等）：
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "$NEW_VENV/bin/python" \
  tools/single_car_imu_fgo_eval/verify_fgo.py --packets "$INPUTS" \
  --adapted "$ADAPTED" --matrix "$MATRIX" --execution-checkout "$NEW_EXEC_TREE" --output "$NEW_READBACK"
```

`verify_prefix.py`用`verification_protocol.json`冻结41秒receive截断控制，保留全部非耗时发布字段；要求`matrix.json`绑定同一干净执行提交。`negative_fgo.py`只改私有副本，重新封装SHA后核对语义拒绝；不触原结果。`summarize_fgo.py`读取通过的主回读/截断/负例，输出752行诊断、全分母/共同有效结果和bias图，不读真值或视频。不另写求解器。

实际全命令在`results/STAGE2_SOURCE_VERSIONS.json`与归档每个`run.json/matrix.json`。三个协议版本各自保留：`protocol.json`为阶段1输入，`field_protocol.json`为名义8运行，`verification_protocol.json`为8个因果控制；不能把前者的pending状态误当当前运行结论。严格物理参数仍pending，只有条件探索已执行。读取器本身不导入A在线因子、Jacobian或A审核器；F0全部回归、F1–F3全消元数值检查和源码依赖审计范围分别列明。
