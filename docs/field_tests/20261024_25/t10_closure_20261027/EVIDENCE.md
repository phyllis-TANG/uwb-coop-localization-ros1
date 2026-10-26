# T10 参数、时钟与参考证据

本页只对应成功重试184755与IMG_7347。三组操作员补证已收到，见[答复记录](operator_evidence.json)；这些答复明确保留未知项，没有提供新标定。原资料、公共geometry/manifest均未改。

| 输入 | 证据与性质 | 本轮采用范围 | 真正缺少什么 |
|---|---|---|---|
| Car1天线高度0.17m、Car2 0.20m | 现场§54/55人工近似；[源码/资料核验](results/source_evidence.json) | 严格模板保留已有数值，量具不确定度null；平面模型不再分别索要base高度与杆臂Z | 安装适用性与误差仍未测准，不填零方差 |
| Car1水平偏移[+.08,−.06]m | 10/18[测量原表](../../20261018/single_car_benefit_20261021/evidence/antenna_mount_survey_20261018.txt)，原文`horizontal_reference: approximate chassis geometric center`、`odom_origin_correspondence: pending verification` | 恢复为有来源候选；不是base杆臂 | 物理odom车体参考点与该几何中心的关系，以及该记录对T10安装的适用性 |
| Car2水平偏移[−.12,+.08]m | 10/24现场纠正，操作员本轮再次确认；旧10/18表[+.12,−.08]保留作历史冲突 | 使用纠正后的**几何中心候选**，严格base值仍null | 同上，不能把旧反号直接带入T10 |
| 10/21安装未变确认 | [历史原文](../../single_car_historical_L_20261021/MOUNT_USER_CONFIRMATION_20261021.md) | 对当时历史记录成立，不能延伸成T10之后安装未变 | 如现在补量，须证明其对应原T10刚性安装 |
| URDF/驱动的base命名及模型原点 | 归档V550 URDF、base_serial.launch、wheeltec_robot.cpp均按SHA复核；URDF无天线链 | 能说明软件frame和积分代码；CAD/inertial原点、零TF不证明实际天线关系 | 物理参考点定义/机械量测，不是寻找一个“odom盒子” |
| marker→天线 | Car1[+.07,−.13,−.20]、Car2[−.17,+.025,−.03]m，体轴对齐的人工平移 | 与base杆臂分开；不替代 | marker/body旋转、板形状与安装误差用于视觉参考；不会由这些值伪造base外参 |
| Car1实际初值XY/yaw | B(1.5,4)、−Y是指导；操作员未找到成功重试前独立确认 | 严格值null；不把源odom的[0,0,0]当房间位姿 | 同一具体记录处的实际天线XY与body yaw，或直接给base位姿 |
| Car2实际初值XY/yaw | (2.98,3.07)来自T09**人工**末点并计划不动；+X由计划L推导 | 数值仅候选；+X的0rad是有含义的计划角，不是填未知默认值 | 实际位置未搬动/朝向确认及记录绑定；未处理T09定位结果 |
| 初始记录身份 | Car1 index3、Car2 index117，整数header/receive见[绑定表](results/initialization_records.json) | 已选定可复现的首到达记录身份；实际房间位姿绑定未采用 | 物理姿态与该记录的关系，不能由终点反推 |
| 视频条件性对应 | PR49未验收事件模型下，两车首记录附近均对应frame749、PTS14980、time_base1/600 | 仅供查找；不是精确同步或已采用初值 | 有界独立时间关系或已独立确认的同一静止段 |
| 固定R/Q及初始协方差 | PR46既有工程参数，未按T10误差调整 | 沿用原接口；不能作为真实标定误差 | 不额外要求先标定R/Q才准备代码，亦不声称统计可信 |

初始base推导仍为`p_base = p_antenna − R(body_yaw) lever_xy`。它需要实际天线位置、body yaw和物理base杆臂全部有来源；“两个近似中心之间未知关系”不能靠给其中一个填0消除。

## 时钟证据与接口

完整带行号片段和源文件SHA见[source_evidence.json](results/source_evidence.json)，实际T10 header覆盖与待填字段见[time_input_requirements.json](time_input_requirements.json)。原归档SHA和成功bag SHA均已实际复算；只读源码，没有执行归档脚本。

| 环节 | 能确定的来源 | 仍pending |
|---|---|---|
| Car1 UWB/raw wrapper | 驱动串口解析后`rospy.Time.now()`；wrapper复用原header，raw/bridge不是两次采样 | T10实际部署绑定、硬件测量到主机打戳的时间/误差 |
| Car2底盘 | 已归档源码先读取、计算/积分，再另取ROS时间发布odom；IMU又取一次时间 | T10运行二进制对应、板端采样时间/排队；不能把Car2代码认作Car1底盘实装 |
| Car1底盘、Car2 nlink | 话题及原header、设备ms被保留；bridge实现复制上游header | 实际底盘/nlink打戳位置和版本未找到；设备ms与UTC/逐链路测量时刻关系未知 |
| 主机→VM记录端 | 保留各车独立源域、bag receive整数ns | offset/drift、ROS time模式、有效区间、误差界；Car2运行Master不统一其他主机的时间 |
| 10/24 timedatectl | 三份顺序服务状态快照已存在并按SHA复核 | 不是10/25 T10同期偏差日志；不能相减显示时间当offset或把“已同步”当毫秒保证 |
| PR49 video→receive | `a=1`为假设，`b≈−24.954730587s`；两个原odom运动边界的最大拟合残差约0.180296316s | 正式model与总误差界仍null；不是独立同步界，更不是每话题采样时间模型 |

最小接口仍采用PR48：主机仿射关系的整数原点/有理数rate/有效区间，加每话题的有符号采样相对header偏移。两个已声明绝对误差界相加，不能凭空假设独立。复制header的raw/bridge不需要分别标定，但odom与UWB共享主机clock的部署/ROS time条件也未确认。B端严格封装要求时间误差界为有来源的正整数，未知继续null；未改A端或既有EKF门槛。

没有计算receive−header中位数作为延迟，也没有把运动拟合用于校准将来评价同一Odom/融合结果的参考。

## 参考裁决

[机器可读裁决](reference_decision.json)逐车保留范围、空间/时间未知项和禁止指标。原片8幅定向画面支持Car1位置变化、Car2在这些样本中图像位置相近的**定性描述**；不证明精确起停、零运动或房间位置。

| 用途 | 当前裁决 | 阻塞项 |
|---|---|---|
| 连续天线位置参考 | not_accepted | P/Q实际尺量与独立检查、片间/片内成像关系、安装/板形状、独立有界同步 |
| 精度停点/终点参考 | not_accepted | 空间来源与不确定度、同一次未搬动停车及记录窗未绑定；不能用名义Q误差作验收 |
| 媒体、像素及稀疏动作观察 | qualitative | 只报告所审帧，不换算成房间精度 |
| 操作员末点(1.48,2.97)m、末距1.52m | 保留人工报告，未批准精密checkpoint | 误差未知、停车记录未绑定；不参与初始化或轨迹配准 |

P1–P4仅是名义拟合坐标；Q1–Q3未参与拟合或模型选择，但实际尺量与逐片对应未建立。没有用同一批Q先选内参再证明精度。若将来独立确认同一停车且其后未搬动，可审查停点评价而不强求毫秒级连续同步；空间/安装条件依然需要通过。

三组问题及回答状态见[operator_questions.json](operator_questions.json)。当前无需再次询问已说明的偏移、轴向或缺失日志；剩余的是实际校准/历史记录，不是再让操作员重复指导值。无法追补的历史时间真值须明确保留，补录仅是一份建议，今晚不执行。
