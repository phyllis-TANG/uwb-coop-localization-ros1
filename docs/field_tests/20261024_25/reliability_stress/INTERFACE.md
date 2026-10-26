# 与实包基线端的最小接口

本目录不修改 comparison_adapter.py、视觉工具、公共 manifest/geometry。Estimator 仅为二维合成研究，不能直接声称是已验收的现场算法。

## 上游适配层应交付

按单包、单方法创建独立 Estimator/Admission/Gate 实例。每次 step 提供递增 cutoff_ns、此前实际到达的两车 Odom、只在这次新到达的 ranges。当前实现的合成 Odom 是已知 room 对齐的两车 `[x,y,yaw]`；实包需要独立 room 初始化、body-to-antenna 变换及各自不确定性，不能照搬 synthetic 配置。base XY 是估计状态，z 不参与平面更新，天线高度只属于合成几何。

| 输入 | 必需字段/语义 |
|---|---|
| 测距身份 | experiment_id、vehicle_id、tag_id、target_id、record_index、link_index；保留 car1→node_0 / car2→node_1，不用无向距离覆盖原始身份 |
| 测距数值 | range_m、source=raw、primary_observation、valid；bridge 不能作为额外观测 |
| 时间 | sample_ns、receive_ns 均为精确整数；已验收的同一时钟域；clock_mapping_id 必须可追溯，包含不确定性 |
| Odom | 仅此前到达的采样序列，frame 校验、完整时间、每车姿态与协方差；不能把 Car2 position.z 当高度 |
| 几何 | 已验收 room anchor XYZ、天线/车体变换和协方差；未知项必须阻塞或显式增大不确定性 |

现有标准化 `receive_epoch_ns` 只有到达语义，canonical_time_s 也只是包内到达轴，不能直接当 sample_ns。本实现 Admission 故意只接受 `synthetic_exact_v1`，因此真实数据默认拒绝；最小接口变更建议是在基线端自己的适配目录验证 `time_mapping.json` 后产生 `validated_clock` 对象，再以受验证的时钟 ID 替代这项合成 guard。没有验收映射时保持 BLOCKED，不把 header 原值直接解释为同步采样。

## 可移植的候选部分

1. 保留一个只用本车 Odom/墙测距的影子状态及完整协方差；peer 更新不反馈进去。
2. 在 peer 的采样时刻，用此前已到达 Odom 搬运两车几何，计算相对影子状态的创新。误差和协方差需传播时钟、yaw、lever-arm 不确定性；当前合成模型没有完整处理这些量。
3. 每个有向来源维护异常/恢复状态；在同一 unordered pair 的相关时间窗只消费一个物理因子，跨调用保留抑制状态。200ms 窗只为本实验设置，未从实包校准，不能直接沿用。
4. peer 输出相对影子解施加每车位移上限；健康判定仅用当前墙信息矩阵/数量。0.06/0.35m 只是合成预注册值。故障来源标签和真值不得进入该接口。

`step()` 返回两车 XY 与诊断：solver_success、墙数量/最小信息量、健康判定、peer 创新/拒绝原因、位移截断、门控状态、累计线性系统次数与实际耗时。Estimate 输出遵守 RESULT_CONTRACT；诊断完整保留失败和无 peer 时段。

## 集成门槛

先只作为可插拔的 peer 因子准入/传播监控模块，不替换另一工作端的实包基线。上游提供已验收初始化/时钟/几何及四个开发包 T08/T10/T12/T14 的标准化观测后，再在独立目录验证；T09/T11/T13/T15 继续整包留出。未验收的视觉参考不能用于调参或宣称实包精度提高。当前交付结论只针对冻结的合成条件。
