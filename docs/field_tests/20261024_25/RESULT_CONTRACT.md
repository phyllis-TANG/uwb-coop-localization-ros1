# 三端统一输出契约 v1

本契约约束**接下来的输出接口**，不是宣称所有文件已生成。已有QC JSON按当前工具的真实结构保留；不能为凑本契约改写历史验收结果。后续导出/估计/参考工具应在同一schema版本下输出，并给出字段映射。

## 共同规则

- SI单位：长度m、时间s或明确后缀`_ns`、角度rad。人工cm读数先保留原读数，再记录转换。
- ROS epoch ns以整数/十进制字符串保留，CSV不经Excel自动浮点转换。视频PTS保留其原始time_base和整数tick，同时提供转换后秒数。设备ms保留原单位和设备时钟域。
- 未知、无效、未测和未观测不能填0。JSON用`null`并写原因；CSV缺失留空，并提供状态/原因列。严格JSON不输出NaN/Infinity。
- source raw与bridge若代表同一测距，保留可追溯关系，不作为两次独立观测叠加。
- 原始观测、变换后观测、估计、独立参考分开保存；不覆盖原始数据。
- 路径使用相对数据根目录或逻辑asset_id，不在共享结果中依赖`/workspace/scratch/...`或某台电脑用户名。

## 运行来源：run.json

每个新计算/参考运行都需要来源说明；现有工具自动产生的源码/manifest哈希与下面字段可映射记录。

```json
{
  "schema_version": 1,
  "run_id": "video_reference_20261026_001",
  "role": "local_video",
  "status": "BLOCKED",
  "created_at_utc": "2026-10-26T00:00:00Z",
  "code_commit": "<actual Git commit>",
  "worktree_dirty": false,
  "source_sha256": {"<relative source path>": "<sha256>"},
  "config_sha256": {"manifest.json": "<sha256>", "geometry.json": "<sha256>"},
  "inputs": [{"asset_id": "camera_reference", "relative_path": "IMG_7364.MOV", "sha256": "<sha256>"}],
  "command_argv": ["<executable>", "<script>", "<arguments>"],
  "environment": {"python": "<actual version>", "packages_file": "python_packages.txt"},
  "outputs": [{"relative_path": "reference_validation.json", "sha256": "<sha256>"}],
  "blocked_reasons": ["Car2 marker/plane validation pending"],
  "limitations": []
}
```

示例占位符不能冒充真实值，`status`仅取`DONE`/`BLOCKED`/`FAILED`/`IN_PROGRESS`。`DONE`须有该任务的验收证据，而非只生成了文件。失败运行也保存来源、错误及已完成检查点；已完成输出不原位覆写，源码或配置变化时新建run_id。

## A端标准化观测

`ranges.csv`每个有向距离条目一行，建议字段：

| 字段 | 含义 |
| --- | --- |
| experiment_id, vehicle_id, source_asset_id, source_file_sha256 | 实验及输入身份 |
| topic, record_index, header_seq, link_index | 唯一观测追溯；不能只用浮点时间作主键 |
| receive_epoch_ns, header_epoch_ns | bag接收时间和ROS header原值 |
| device_local_time_ms, device_system_time_ms, device_clock_id | 原始设备时间；不存在时留空 |
| tag_id, target_id, link_kind | 源/目标UWB ID；wall/peer/unknown |
| range_m, fp_rssi_db, rx_rssi_db, quality | 原字段或单位换算；未知quality留空，不置0 |
| raw_frame_id, bridge_frame_id, pairing_status | raw/bridge配对身份及状态 |
| time_mapping_id, canonical_time_s | 仅在有明确时间映射后填入 |
| valid, invalid_reason | 有限正距离不等同于已通过NLOS/精度检查 |

`odom.csv`至少保留实验/车辆/来源、receive/header时间、frame_id/child_frame_id、position原字段、quaternion、速度及协方差。Car2 position.z原值可留诊断列，但需显式`position_z_semantics=driver_yaw_related_not_height`，不能输入几何高度。

`imu.csv`保留时间、frame、姿态/角速度/加速度及协方差，不把板载IMU视为与Odom完全独立的真值。`commands.csv`保留各车cmd_vel、bag时间及主题，无header时不伪造header。

## B端视觉观测与参考

`video_inventory.csv`：experiment_id（未定可为空）、asset_id、原视频相对路径/SHA、时长、编码/显示分辨率、rotation、帧率描述、PTS来源、实验对应状态。

`marker_observations.csv`：

```text
experiment_id,video_sha256,frame_index,pts_ticks,time_base_num,time_base_den,
video_time_s,coordinate_convention,marker_id,vehicle_id,detected,method_version,
corner0_x_px,corner0_y_px,corner1_x_px,corner1_y_px,corner2_x_px,corner2_y_px,
corner3_x_px,corner3_y_px,quality_flags,invalid_reason
```

`coordinate_convention`明确`encoded_pixels`或`display_pixels`及相应变换；角点顺序/单位记录在附带schema中。检测/跟踪失败仍保留该帧状态，不只保存成功帧后声称完整覆盖。人工初始化、自动解码、跟踪等方法分别标明。

`frame_transforms.json`明确变换方向，例如`T_room_camera`表示将camera坐标点变换到room。写出右/左手、轴向、长度单位、旋转表示、来源/配置哈希、估计方式和协方差/未知项。不能把body方向对齐的人工平移直接当ArUco自身frame中的已标定外参。

`time_mapping.json`每片单独记录source/destination clock、模型（例如`ros_time_s=a*video_time_s+b`）、有效区间、拟合事件/点、残差、不确定性、是否人工近似与来源。未验证的映射状态为pending，不写a=1/b=0当作同步完成。

`reference_validation.json`列明哪些P/Q参与拟合、哪些独立留出、实际点位及测量来源、每车/朝向误差、检测可用率、时空不确定性和可批准范围（`continuous`/`checkpoints_only`/`not_accepted`）。拟合残差不替代独立位置误差。

`antenna_reference.csv`（仅在对应范围验收后）：

```text
experiment_id,vehicle_id,video_sha256,frame_index,video_time_s,
time_mapping_id,canonical_time_s,frame_id,x_m,y_m,z_m,yaw_rad,
valid,quality_flags,uncertainty_model_id,reference_version
```

可增加协方差列，未估计不能填零。若只有停点，改交`checkpoints.csv`，包含点身份、人工坐标/高度、车辆/朝向、时间窗口、来源与不确定性，不能插值成整段“真值”。

## 估计器与评价接口

`estimate.csv`每次发布/估计一行：experiment_id、method_id、vehicle_id、canonical_time_s、frame_id、x/y/z（未估计z为空）、yaw、valid、diagnostic_id、source/config/reference版本。

`diagnostics.json`保留输入可用性、因子/权重/剔除原因、初始化及失败、求解预算、因果/全历史属性。候选可靠性方法不能只保存最终成功轨迹而隐藏无解时段。

评价报告必须说明：整包开发/留出划分、参考覆盖/质量、时间和空间对齐规则、有效窗与失败率、误差指标定义及每次运行结果。跨方法使用同一套有效参考和对齐规则；无连续参考时不报告全轨迹RMSE。小帧间隔只增加采样密度，不提升独立实验次数。

## 协调验收与版本回传

各端回传最少包含：短结论、可点击的代码/PR、来源版本、真实命令、测试摘要、结果目录/哈希、失败/阻塞项。大输出放外部数据附件并在仓库登记SHA，紧凑报告可提交Git。协调端确认来源和科学依赖后，将已批准参考/配置版本发给依赖端；不能让三个窗口凭各自聊天记忆继续推演。
