# 2026-09-27 双车 UWB 协同测距现场实验总结

## 1. 实验目标与结论

本次实验完成了两辆 WHEELTEC 小车、两套 LinkTrack UWB 节点和一台记录电脑在同一 ROS Master 下的接入，验证了：

- 双车双向 UWB 实时测距；
- LinkTrack NodeFrame3 到 `UwbRangeArray` 的桥接与重复节点中值聚合；
- 静态 LOS 真值测距、人体 NLOS、动态人工推动及 90° 姿态对照；
- 双车 UWB、轮式里程计、板载 IMU 与电压话题的同步采集；
- 面向后续离线融合的动态输入 bag 采集。

本次结果属于“协同测距与多传感器数据接口初步验证”。尚未完成双车 TF 唯一化、UWB/Odom/IMU 状态融合或完整二维协同定位。

## 2. 系统拓扑

| 角色 | 车辆与系统 | 网络地址 | ROS | UWB节点 | 主要话题 |
|---|---|---:|---|---|---|
| Car1 | 旧车，Bash 4.4 | `192.168.31.10` | Melodic | P-B1 / `node_1` | `/car1/uwb/ranges`、`/car1/odom`、`/car1/imu` |
| Car2 | 新车，Bash 5.0 | `192.168.31.24` | Noetic | P-A0 / `node_0` | `/car2/uwb/ranges`、`/car2/odom`、`/car2/imu` |
| Recorder | Ubuntu虚拟机 | `192.168.31.182` | Melodic | 无 | rosbag记录与离线分析 |

ROS Master 运行在 Car2：`http://192.168.31.24:11311`。

串口分配未发生冲突：

- Car1 UWB：`/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B2E110223-if00`；
- Car1底盘：`/dev/wheeltec_controller`；
- Car2 UWB：`/dev/ttyCH343USB3`；
- Car2底盘：`/dev/wheeltec_controller -> /dev/ttyCH343USB0`。

## 3. 软件变更验证

现场使用的主分支包含：

- PR #21：增加 `nlink_frame3_bridge.py`，将 `nlink_parser/LinktrackNodeframe3` 转换为 `UwbRangeArray`；
- PR #22：对同一 Frame3 内重复 `anchor_id` 样本取中值，保证每个目标节点每帧只输出一条距离。

PR #22 合并提交为 `900d817`。桥接单元测试在 Python 2 和 Python 3 下通过，ROS Noetic 工作空间编译通过，并在 Car2 实机验证约 50 Hz 输出。

## 4. 单链路基线与 NLOS 现象

以下结果使用 P-A0/P-B3 单链路、中值聚合输出：

| 工况 | 真值 | 均值 | 标准差 | 有效率 | 说明 |
|---|---:|---:|---:|---:|---|
| 静态 LOS | 1.50 m | 1.5794 m | 0.0213 m | 99.90% | 重复采集后的有效记录 |
| 静态 LOS | 2.00 m | 2.1564 m | 0.0247 m | 99.80% | 正偏约 0.156 m |
| 静态 LOS | 3.00 m | 3.2676 m | 0.0244 m | 99.80% | 正偏约 0.268 m |
| 人体 NLOS | 2.00 m | 2.7521 m | 0.1000 m | 99.97% | 预先站位重复实验，出现明显正偏 |

人体遮挡显著增大了测距正偏和波动。该现象仅用于本次硬件与场景观察，不能直接作为后续 NLOS 固定补偿量。

## 5. 双车静态 LOS 真值测距

相机遮挡清除、两天线正面对准、真值 1.85 m 的 30 s 记录：

- Car1 MAE：0.0395 m；
- Car2 MAE：0.0392 m；
- 双向均值 MAE：0.0299 m；
- 双向均值 bias：约 -0.000025 m；
- 双端共同有效率：78.97%；
- 双向距离差均值：0.0529 m；
- 双向距离差 P95：0.131 m。

该记录表明双向均值在本次静态布置下达到约 3 cm MAE。共同有效率仍受安装遮挡、无线链路与配对条件影响。

## 6. 双车动态 UWB 往返

文件：`TWO_CAR_PA0_PB1_manual_push_LOS_final3_20260927_071235.bag`

SHA256：`421b4fd83e9e3fd9fb05577f2f2b6a65478ea374a4418b9a43583aa71b940bb3`

时长约 74.9 s，Car1/Car2 分别记录 3746/3726 帧。运动过程包含近端静止、远离、远端静止、返回和近端静止，两侧距离曲线趋势一致。

- 配对帧：3572；
- 双端共同有效对：3527；
- 双端共同有效率：98.74%；
- 双向距离差均值：0.0505 m；
- 双向距离差中位数：0.0450 m；
- 双向距离差 P95：0.1170 m；
- 双向距离差最大值：0.2300 m；
- bag 接收时间差 P95：0.00970 s。

## 7. EXP006 姿态敏感性 Pilot

在 2.00 m 静态距离下比较正面对准和 Car1 顺时针旋转 90°：

| 指标 | 正面对准 | Car1旋转90° |
|---|---:|---:|
| 双端共同有效率 | 99.50% | 98.97% |
| Car1 MAE | 0.0420 m | 0.0436 m |
| Car2 MAE | 0.0249 m | 0.0237 m |
| 双向差均值 | 0.0552 m | 0.0529 m |
| 双向差 P95 | 0.1220 m | 0.1103 m |
| 双向均值 MAE | 0.0207 m | 0.0214 m |

在本次距离、安装和室内环境下，旋转 90° 未造成显著性能退化。该结论仅是单次 30 s pilot，不能推广为普遍的方向不敏感结论；正式 EXP006 仍应增加重复次数、4 m 工况和两端 RSSI 记录。

## 8. 双车多传感器同步采集

### 8.1 静态接口验证

文件：`TWO_CAR_UWB_ODOM_IMU_static_interface_pilot_20260927_075002.bag`

SHA256：`a7a94e12a1f4a283a35d632fc486d244ed6236a316c6cdca38cc0c246e7ff4c8`

30 s 内记录 5533 条消息：

| 数据 | 消息数 | 约频率 |
|---|---:|---:|
| Car1 UWB | 1517 | 50.6 Hz |
| Car1 Odom | 609 | 20.3 Hz |
| Car1 IMU | 612 | 20.4 Hz |
| Car2 UWB | 1491 | 49.7 Hz |
| Car2 Odom | 599 | 20.0 Hz |
| Car2 IMU | 602 | 20.1 Hz |

### 8.2 动态融合输入 Pilot

文件：`TWO_CAR_UWB_ODOM_IMU_manual_push_LOS_GTstart2p00m_final_20260927_075537.bag`

SHA256：`86ede69d9c75eeff10d400d95bc65f2855365130cdad8f5fb9c4966e9ba8a850`

配置：Car2 静止，Car1 沿两车连线人工直线推动；初始 UWB 参考点距离 2.00 m；不启动导航，不发布 `cmd_vel`。

60 s 内记录 11056 条消息：

| 数据 | 消息数 | 约频率 |
|---|---:|---:|
| Car1 UWB | 3024 | 50.4 Hz |
| Car1 Odom | 1215 | 20.3 Hz |
| Car1 IMU | 1224 | 20.4 Hz |
| Car2 UWB | 2990 | 49.8 Hz |
| Car2 Odom | 1199 | 20.0 Hz |
| Car2 IMU | 1201 | 20.0 Hz |

该数据集可用于后续离线检查 UWB 相对距离、Car1 轮式里程计位移、IMU 运动响应与 Car2 静止基线的一致性。

## 9. 已知限制

- 原始 bag 不提交 Git，仅保存摘要、哈希和分析产物；
- 本次多传感器 bag 未录制 `/tf` 和 `/tf_static`；
- 两车 `Odometry.child_frame_id` 仍均为 `base_footprint`；
- 两车 IMU `frame_id` 仍均为 `gyro_link`；
- TF 与消息 frame 在实时融合前必须唯一化为 `car1/...` 和 `car2/...`；
- 当前 `UwbRange.quality` 为 `NaN`，尚未将 FP RSSI/RX RSSI 映射到统一消息；
- 双车协同状态估计尚未实现；现有 `robot_pose_ekf` 不能直接融合 `UwbRangeArray`；
- 记录电脑显示时间/时区与现场本地时间存在差异，原始 bag 时间证据保持不变，后续分析不得静默覆盖；
- 本次真值主要由卷尺测得，测量不确定度约 0.01 m。

## 10. 下一步

1. 为两车唯一化 `odom`、`base_footprint`、`base_link`、`gyro_link` 等 frame；
2. 回放动态多传感器 bag，提取两车 Odom、IMU 和双向 UWB 时序；
3. 估计 IMU 静止偏置并检查 Odom 位移与 UWB 距离变化的一致性；
4. 先实现 Car2 静止、Car1 一维运动条件下的离线 EKF 或因子图；
5. 再扩展到二维双车联合状态估计与实时可视化；
6. 国庆后按 EXP005--008 计划补充 1/2/3/4 m 重复实验、4 m 姿态实验、RSSI 和动态 NLOS；
7. 原始 bag 至少保留两份，并用 SHA256 清单核验。

## 11. 阶段性结论

本次工作已经建立双车协同测距与多传感器同步采集的可运行基础。双向 UWB 在静态和动态场景下均能稳定输出，两车 Odom 与 IMU 已接入同一 ROS Master 并完成同步录包。现阶段成果可用于初步汇报和后续离线融合开发，但不应表述为已经完成二维协同定位或 UWB/IMU/Odom 融合。

