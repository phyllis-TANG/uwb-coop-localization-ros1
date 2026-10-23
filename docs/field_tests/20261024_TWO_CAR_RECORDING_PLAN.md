# 2026-10-24 上午：双车问题定位与补录清单

准备时间：2026-10-23，Asia/Shanghai。依据已合并 PR #41；这是待执行计划，不是已完成的现场记录。

## 当前状态与明早目标

单车离线/顺序回放/固定窗口原型和双车全包离线对照已有可复现结果。双车静止形变有所减少，稳定协同定位收益仍未验证；最新历史降权策略没有明显终点收益。

Car2/node_10 在两个同位置记录中的原始中位数为 3.441 m 和 4.366 m，差 92.5 cm，各包内部却基本稳定。包外的摆位、遮挡、方向、状态变化缺少同步记录。另一个限制是墙测距可污染预测位置，使车间测距被连带降权。

明早重点取得：**独立测量的参考、可重复的正常数据、带时段标记的受控遮挡、桥接前原始 UWB 帧**。按后续讨论，基础清单扩充为 13 包，增加两车同时运动的两次重复；多余时间再重复遮挡序列一包。录制本身约 20–35 分钟，含检查、测量、摆位、核查及备份预留约 1.5–2.5 小时；手机标定、架设及现场启动/排错另计。手机方案先做本文后附的可行性检查，再覆盖同批录制。

## 开始前先做三件事

1. 核对四个墙锚 ID 与当天实际位置/高度，尤其 node_10；画房间坐标原点和正方向。标记的是 **UWB 天线中心在地面的投影**，XYZ 使用当天独立测量。记录两车天线高度、安装照片及朝向，保存两天线间直接距离，注明量的是水平距离还是斜距。
2. 按 [单车现场优先排查清单](20261024_SINGLE_CAR_CHECKLIST.md) 先保存 Car2 实际 `base_serial.launch`、引用的 Odom/IMU 发布源码/配置、URDF/TF 和版本。若 Odom 运动学参考点仍未确定，明确记“待核实”，不要将几何中心自动当成该点。先保存材料，现场无需读懂全部代码。
3. 两车接入同一录制端，确认收到消息，保存实际话题、消息类型、发布节点和录制端/两车时钟状态。采集期间固定安装、锚点及驱动版本；每次重启、改参数、搬动设备均写入 notes。

已有 Car2 文件入口，仅只读查看：

```bash
sed -n '1,240p' /home/wheeltec/wheeltec_robot/src/turn_on_wheeltec_robot/launch/include/base_serial.launch
```

路径以本车实际文件为准；若不存在，保留报错，沿实际启动入口查找。

## 建议摆位与角度定义

- 复现点 A：Car2 天线中心目标 XY=(2.00,2.00) m。
- 固定点 B：Car1 天线中心目标 XY=(1.50,4.00) m。
- 新位置 C：Car2 可选 XY=(3.00,3.00) m，或现场空间合适的另一独立测量点；实际值如实记录。
- 所有坐标必须基于当天同一房间坐标系；旧点只作为复现目标，不覆盖当天测量。
- **0°=车头朝房间 +X，90°=+Y，180°=-X，270°=-Y。** 基线建议两车朝 +Y（90°）。
- Car2 旋转后重新测量/调整天线中心，使其回到 A，再开始朝向静态包；转向过程本身不当作“天线位置不变”的静态样本。

## 13 包基础清单

| ID / 建议文件名 | 实验 | 建议时长 | 必记参考与用途 |
|---|---|---:|---|
| T01_static_A_baseline_yaw090 | 两车在 A/B，无遮挡，固定朝向 | 60–90 s | 两车天线 XYZ、朝向、直接间距；基准/开发 |
| T02_static_controlled_occlusion | 保持两车不动，执行下方五段序列 | 150 s 以上 | 事件时间、遮挡物位置/照片；区分墙链路与车间链路影响 |
| T03_static_A_yaw000 | Car2 天线回 A，车头 +X；Car1 保持 B | 60 s | 转向后重测天线 XYZ；朝向诊断 |
| T04_static_A_yaw180 | 同一 A，Car2 车头 -X | 60 s | 同上 |
| T05_static_A_yaw270 | 同一 A，Car2 车头 -Y | 60 s | 同上 |
| T06_static_C_yaw090_holdout | Car2 到独立测量的新点 C，朝 +Y；Car1 保持 B | 60–90 s | 新点 XYZ、两车间距；空间迁移留出验证 |
| T07_static_return_A_yaw090_holdout | Car2 返回 A，恢复 T01 朝向与无遮挡条件 | 60–90 s | 再次独立量坐标/距离；返回重复，不参与反调修正 |
| T08_C1static_C2L_repeat1 | Car1 固定，Car2 走已标记 L 路线 | 90–180 s | 起点、至少一个中间停点、终点的实际天线坐标/朝向；开发 |
| T09_C1static_C2L_repeat2_holdout | 相同摆位和路线，独立再跑一遍 | 90–180 s | 重新测量；留出验证 |
| T10_C2static_C1straight_repeat1 | Car2 固定，Car1 走已标记直线 | 90–180 s | 同样记录实际起点/停点/终点；开发 |
| T11_C2static_C1straight_repeat2_holdout | 相同摆位和路线，独立再跑一遍 | 90–180 s | 重新测量；留出验证 |
| T12_bothmoving_clear_repeat1 | 两车在分开的路线运动，含共同运动和车间距离变化 | 90–180 s | 两车实际起点/中间停点/终点及起停事件；开发 |
| T13_bothmoving_clear_repeat2_holdout | 同样路线与设置，独立重复双动态 | 90–180 s | 重新测量；留出验证 |

动态路线使用已有验证过的控制方式，按现场空间保留车体间距和停止余量。每包出发前与结束后留 20–30 秒静止；途中停稳后测量，人员退出后另留至少 10 秒清晰静态段。测量开始/结束也做事件标记。控制目标、Odom 终点不能代替实际天线坐标。

T06/T07/T09/T11/T13 预先标为留出数据；若需用新数据调整参数，只使用其余开发数据。静态返回属于重复条件验证，不冒充新的空间点。没有连续独立真值时，评价仅覆盖人工停点等有参考的状态。

双动态先用无遮挡条件、已有控制方式和分开的路线。可错开起步并保留共同运动段，让车间距离产生变化；记录实际动作和事件。墙锚安装固定，两车到各墙锚及车间双向距离全程记录。同一包支持原模型/新模型、各自/联合等离线算法对照；真实遮挡影响仍由 T02 的受控录制提供。

### T02 五段序列（每段至少 30 秒，持续录在同一包）

1. 正常无遮挡。
2. 在 node_10 墙锚路径附近放置遮挡，记录具体位置和物体；两车不动。
3. 移走遮挡，恢复正常。
4. 在两车之间放置遮挡，记录具体位置；两车不动。
5. 移走遮挡，再恢复正常。

每次切换发布对应事件并拍照，保留切换前后过程。这里记录的是有意改变的条件；遮挡可能同时影响其他链路，实际影响范围之后根据所有测距判断，不预先标成“只有这一条坏了”。有时间完整重复一次。人员清空的正常段也要明确标记。

## 每包录哪些话题

**每包同时录两车，即使其中一辆静止。**

- `/car1/uwb/ranges`、`/car2/uwb/ranges`
- `/car1/odom`、`/car2/odom`
- `/car1/imu`、`/car2/imu`：保留原始 IMU，供之后核验/融合；采集不代表本轮已加入独立 IMU 因子。
- `/car1/cmd_vel`、`/car2/cmd_vel`，以及实际电压话题 `/car1/PowerVoltage`、`/car2/PowerVoltage`。
- `/tf`、`/tf_static`（若存在）、`/experiment/events`。
- **桥接前原始 UWB 消息**：仓库 nlink 启动文件的输入预期是 `/car1/nlink_linktrack_nodeframe3`、`/car2/nlink_linktrack_nodeframe3`；必须以现场实际话题为准。若使用原生 Python 驱动，查其实际 `raw_topic`（默认 `/uwb/frame3`，命名空间/参数可能改变）。保存原始类型定义。

仓库 `nlink_frame3_bridge.py` 和原生驱动均将简化 UWB 消息的 quality 填为 NaN；桥接还会将同一帧同 ID 的距离做中位数聚合。因此要另存桥接前数据。原始消息是否含 RSSI、设备时间、帧序号等信息，以实际消息定义和数值为准，不为采集直接更换驱动。

以下命令只供现场操作人员使用；本计划未执行任何现场命令。先检查实际话题：

```bash
rostopic list -v
rostopic info /car2/uwb/ranges
rostopic info /car2/nlink_linktrack_nodeframe3
```

确认上述原始话题存在后，可按下例录 T01；其他包只改 ID/文件名。若原始话题名称不同，先替换对应两项；已有数据使用新目录/新文件名保存。

```bash
FIELD_SESSION_DIR=~/uwb_field_20261024
mkdir -p "$FIELD_SESSION_DIR"
rostopic list -v > "$FIELD_SESSION_DIR/topics_before.txt"
rosnode list > "$FIELD_SESSION_DIR/nodes_before.txt"

rosbag record -O "$FIELD_SESSION_DIR/T01_static_A_baseline_yaw090.bag" \
  /car1/uwb/ranges /car2/uwb/ranges \
  /car1/nlink_linktrack_nodeframe3 /car2/nlink_linktrack_nodeframe3 \
  /car1/odom /car2/odom /car1/imu /car2/imu \
  /car1/cmd_vel /car2/cmd_vel /car1/PowerVoltage /car2/PowerVoltage \
  /tf /tf_static /experiment/events
```

另一个终端在**同一录制端**标记事件，例如：

```bash
rostopic pub -1 /experiment/events std_msgs/String "data: 'T02_N10_block_start'"
```

建议事件名包括 `clear_start`、`N10_block_start`、`N10_block_end`、`peer_block_start`、`peer_block_end`、`move_start`、`stop_P1`、`measure_start`、`measure_end`、`run_end`。事件保存接收时间，避免只用两车未核实同步的系统时钟手写秒数。人工切换标记仍有操作误差，按实际情况记录。

## 每包旁边必须有 notes

```text
bag_id / bag_filename:
operator / date:
condition / intended_occluded_path / event_names:
car1_antenna_start_xyz_m / heading_deg:
car2_antenna_start_xyz_m / heading_deg:
stationary_car / actual_stop_points_xyz_and_heading:
actual_end_antenna_xyz_m_for_both_cars:
direct_antenna_distance_m / horizontal_or_slant:
measurement_method / two_original_readings / estimated_uncertainty:
anchors_xyz_and_IDs / mounts_heights / photo_filenames:
driver_launch_and_source_version / raw_topic_names_and_types:
clock_status / restarts_or_parameter_changes / observed_anomalies:
role: development_or_holdout
```

建议停点/终点至少量两次，保留原始读数；XYZ 都指天线中心。为每种布置拍能看见车头、天线、标线和遮挡位置的照片。视频可作为过程辅助；未经标定不当作厘米级连续真值。

## 每录两三包就检查，离场前备份

- 正常结束录制，`rosbag info` 能打开，必要话题有实际消息，原始 UWB 也确实录到；仅看到 publisher 注册不足以验收。
- 核对两车 tag：Car1=node_1、Car2=node_0；墙节点 ID、高度与当天记录一致。静止段、运动段、事件和 notes 能对应。
- 确认人工参考/照片已保存，再继续下一组。异常原样保留并标注原因。
- 记录当日软件/启动文件、Odom/IMU 来源材料、时间状态和未解决项。至少两份副本并校验 SHA256；保留原始 bag、notes、照片及类型定义。

## 时间不足时的顺序

优先完成基础检查、T01、T02、T06、T07，以及 T08/T09 的重复动态对照。之后做 T10/T11 角色互换和 T12/T13 双动态，最后补 T03–T05 朝向组。每包独立测量和原始数据的完整性优先于数量。

## 附：手机＋车上标记板的外部测量可行性试验

目标是补充独立的位置参考，先检验手机视觉测量自身的误差，再用于评价 UWB/Odom。当前只有方案，没有实拍精度结果；手机轨迹暂不进入本轮融合优化。

### 准备与标记板

- 手机固定在稳定支架上，高位俯拍或斜俯拍整个测试区域。先拍 10–20 秒样片，检查两车最远位置、转弯和并行运动时，标记仍清晰且可见。
- 普通棋盘可用于手机内参/畸变标定。记录棋盘内角点行列数、实际格长；按原尺寸打印，量实际尺寸并贴在平整硬板上。
- 两车车顶各安装不同编号的 ArUco 或使用不重叠 marker ID 的 ChArUco 板，记录字典、ID、板布局和实测边长；画出与车头对应的方向。已有普通棋盘也可先用于单车/静态可行性检查。
- 板与车体刚性固定，记录板原点到 UWB 天线中心的三维偏移、板面高度及安装方向。安装后重新测量；在相同摆位做贴板前后短静态对照，并保持天线可见、安装条件可追溯。
- 两个窗口若分别准备图案和脚本，统一使用一份板规格文件及打印成品实测尺寸，避免行列数、格长、字典或 ID 不一致。

### 先完成三个几何对应关系

| 对应关系 | 取得方式 | 保存内容 |
|---|---|---|
| 手机像素 → 相机模型 | 用已知尺寸棋盘/ChArUco 的多视角影像标定 | 相机内参、畸变、原始标定帧、视频模式 |
| 相机坐标 → 房间坐标 | 固定手机后，用同一房间坐标系下已测的参考点/固定参考板估计外参 | 参考 XYZ、照片、相机外参及使用的参考点 |
| 车上标记 → UWB 天线中心 | 实测刚性安装偏移，随标记姿态旋转换算 | 标记坐标定义、到天线的 XYZ、安装方向与高度 |

标定至少保留 10 个位置/倾角有明显区别的清晰视角，建议采集 15–25 个以便剔除模糊帧。使用与正式录像相同的镜头、分辨率、画幅和变焦设置，尽量固定对焦，保持拍摄设置一致；记录防抖、焦距/镜头和帧率设置。优先直接从相同模式的视频取得标定帧。所有视频保留原文件和时间戳信息。

车上标记有高度，最终比较的是天线中心。处理时使用相机/标记的三维位姿和实测偏移，或明确考虑高度的几何模型；地面平面映射不能直接替代车顶/天线的三维位置换算。相机改变位置后重新确定房间外参。

### 先验证测量精度，再评价动态融合

1. 固定手机后，在地面布置至少四个分布良好、已测的参考点/板角，用于确定相机与房间的关系。
2. 另留至少三个未参与外参拟合的静态检查点，尽量覆盖近、远和侧面位置。每点停留 10–20 秒，独立测量实际天线中心；保存视觉定位偏差、静态抖动和识别掉帧率。
3. 明确测量不确定度。像素重投影误差较小不代表房间坐标误差同样小；是否能分辨当前关心的厘米级差异，以留出点结果为准。
4. 先跟踪一段短直线/短 L，确认无身份交换或明显跳变，再用同一固定机位记录 T08–T13。手机视频可覆盖已有 ROS 实验，不必为每种算法再跑一套路线。

### 视频与 bag 对应

- 记录视频文件名、对应 bag ID、镜头/分辨率/帧率和相机是否移动。保留原视频与真实帧时间戳，后处理不单靠“帧号除以标称帧率”定义时间。
- 录制开头和结尾各做一次能在手机画面看见的同步标记，并在同一录制端发布 `/experiment/events`。例如使录制端屏幕上可见的状态变化与事件对应；保存实际操作方式和时间不确定度，不默认达到毫秒同步。
- 用独立的可见事件建立时间对应，随后检查起止偏移/漂移。房间外参由已测参考点决定；保留检查点和动态终点作为评价数据。
- 人工停点、卷尺距离、照片和原始 UWB 仍按原计划保存。若视觉精度/同步尚不合格，视频先作过程参考，后续离线继续处理。

### 最小可带回的相机材料

一段多视角标定视频或原始帧、板规格与实测尺寸、固定机位的房间参考影像/坐标、标记到天线的安装偏移、三个留出静态点的视频/人工坐标、带起止同步标记的运动原视频。

方法依据：[OpenCV 相机标定](https://docs.opencv.org/4.13.0/d4/d94/tutorial_camera_calibration.html)、[ArUco 检测与位姿](https://docs.opencv.org/4.11.0/d5/dae/tutorial_aruco_detection.html)、[ChArUco 检测](https://docs.opencv.org/4.12.0/df/d4a/tutorial_charuco_detection.html)。这份附录没有新增视觉融合代码，也没有将手机系统声明为已验证的连续真值。

关联：[既有单车现场检查](20261024_SINGLE_CAR_CHECKLIST.md)、[七包诊断报告](two_car_range_diagnostics_20261023/results/REPORT.md)、[双车初版对照](two_car_updated_comparison_20261022/README.md)。
