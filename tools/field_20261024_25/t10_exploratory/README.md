# T10 条件性试跑：从实际观测得到可解释的结果

本工具不修改PR46/48数学内核，不调用/放宽B端严格入口，不修改原始或标准化记录。只消费PR51已登记的T10成功重试输入包，T09/T11/T13/T15不进入定位。

## 两条有限路径

1. 原始墙距直接估计天线XY，使用已有锚点坐标和近似天线高度；不需要base原点、room初始位姿或跨机同步。每帧斜距最小二乘是额外的观测可行性诊断，**不是统一EKF比较中的第四种融合方法**。帧内各链路被近似为同一位置，原始偏差未校正。优化器收敛不代表定位准确，距离拟合残差也不是位置误差。
2. 使用未改动的`replay.replay_events`及`model.Baseline`，运行Odom-only、independent、joint。假设软件积分点等于先前量过的近似几何中心、T10起始摆位符合指导/保持计划、ROS header epoch可用指定合并调整映射到比较时间。它们均明确标注工程假设，不是历史测量的恢复。

`protocol.json`固定7个开发配置：名义组、两车各自lever-X±5cm、Car2总时间调整±20ms。这些步长**不是已标定的误差范围**，也不是完整不确定性传播。R/Q、初始协方差、peer方向、抽样/年龄政策全部沿用原基线。安装偏移改变时，base初值按同一天线假设位置重新推导，避免把初始天线同时移动。

时钟API必须给数值`uncertainty_ns`；本工具明示其为**未验证的工程接口参数，不能解释为实际误差界**。模型目前不把这个参数完整传播入位置协方差；本工具不作协方差覆盖率、概率完好性或精度保证。严格来源配置/参考仍为BLOCKED/not_accepted。

初始化选择收到2秒以后的首个、在该假设时间模型下新鲜的自身odom记录。初始物理位置/朝向仍是假设；精确索引只是可复现绑定，不会使假设变成实测。前面输出保持未初始化，不回填过去。

## 复现

从PR51的`inputs/T10_portable_inputs_v2.tar.gz`核验登记SHA，解压到自己的新目录。使用隔离算法环境（NumPy/SciPy；不需要ROS或视频）。

```bash
"$PYTHON" -m unittest discover -s tools/field_20261024_25/t10_exploratory -p 'test_*.py' -v
"$PYTHON" tools/field_20261024_25/t10_exploratory/pilot.py \
  --packet "$EXTRACTED/T10_inputs" --output "$NEW_OUTPUT" --max-seconds 900
```

每个配置保存原格式base状态CSV、全部准入/拒绝压缩记录、诊断、假设配置、输出响应指标和独立回读。回读核验已接受odom的as-of关系、原始记录/纳秒身份、raw/bridge排除、固定peer方向、支持年龄、状态有限性及每车协方差PSD。PSD不表示统计可信。

`peer_vs_independent_output_shift_m`仅表示加入peer改变了输出多少，**不是准确度收益或损害**。末10秒输出变化也不自动成为真实静止误差。所有实测RMSE/ATE/提升均为空；T10本包的人工终点和视频没有参与初始化、拟合、阈值选择或评价。Car2的T09人工末点确实作为未验证的T10起点候选被消费；没有读取T09定位输出。

运行协议`not_used_as_inputs`里的“operator endpoint coordinates”措辞过宽，具体限定见[协议来源澄清](../../../docs/field_tests/20261024_25/t10_exploratory_20261027/PROTOCOL_CLARIFICATION.md)。正式数值配置及执行SHA保留，不覆盖历史协议或结果。

完整结果保存在Git外新目录；来源提交、实际dirty状态、代码/输入/配置/输出SHA登记在run.json。正式运行应先固定源码，再保存紧凑报告；不改原件和已完成结果。
