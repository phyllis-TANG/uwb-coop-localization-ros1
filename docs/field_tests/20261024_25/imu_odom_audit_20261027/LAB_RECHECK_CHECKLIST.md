# 两车硬件与数据来源现场复核清单

编写日期：2026-10-27。现场日期由操作者另填。本文件是下次实验的待办清单，所有方框保持未完成；它不是已测量、已标定或历史部署证明。建议为硬件与信号复核预留60–90分钟；重新建立视觉空间/时间参考另留30–60分钟，时间依现场情况调整。

目标：补齐真实硬件身份、数据处理路径、物理参考点、安装外参和时钟来源。现有IMU离线原型不等待本清单全部完成。每项允许填写“未知/无法确认”，不以猜测或默认0补齐。

## 可以直接复制到现场笔记的主清单

```text
两车硬件复核
日期：________  操作者：________  记录文件夹：________

开始前
[ ] 给Car1、Car2贴清楚标签，拍车头、全车、控制板、IMU/UWB安装照片。
[ ] 先拍照和测量，再调整安装；记录哪些部件自T10以后拆装过。
[ ] 不刷固件、不恢复出厂、不改UWB参数；本清单不要求重录全部路线。

1. 身份和程序来源（两车分别记）
[ ] 控制板型号/硬件版本/标签照片；实际IMU型号及其证据。
[ ] 固件版本及来源；无法读取时填未知，不用教程年份代替。
[ ] 保存当前底盘src/include/launch、构建信息和可读活动程序SHA。
[ ] 区分“当前采集”“厂家通用设计”“实验时部署”，不合并成一个结论。

2. 串口和UWB
[ ] 当前IP、ROS发行版、master、ROS_IP、ROS_HOSTNAME、use_sim_time。
[ ] 底盘与UWB分别对应哪个端口、硬件串号、权限，是否有重复占用。
[ ] Car1标签node_1、Car2标签node_0与实体对应；墙锚ID对应实体。
[ ] 两车ranges有实际数值；检查墙锚和车间ID的出现率、空数组及长缺口。
[ ] 确认原始帧、标准ranges、Odom、IMU均有持续数据；不能只看节点名称。

3. Odom/IMU处理路径
[ ] 查明Odom的底盘Z角速度来自编码器、陀螺仪还是融合；保存公式/代码。
[ ] 确认gyro各轴确实扣除什么零点，以及发往ROS的是扣除前还是扣除后。
[ ] 记录开机校零条件、需要静止多久、校零完成指示；两车分别确认。
[ ] 确认传感器轴到车体轴的方向、单位、是否已做轴交换/符号变换。
[ ] 核对IMU四元数在哪计算，是否另运行robot_pose_ekf及其输出话题。

4. 物理原点和外参
[ ] 明确实际运动学/积分所代表的base参考点，拍照标位置并记录依据。
[ ] 从该点测到天线中心：前后x、左右y；记录两车天线中心离地高度。
[ ] 每车分别记录marker中心→天线中心、marker方向/倾斜和地面高度。
[ ] 固定天线与标记板，记录重复尺量的离散程度和读数分辨率。
[ ] 核对固定墙锚的既有坐标/高度；仅对改变、缺失或存疑的项目重测。

5. 信号短测
[ ] 若需要开机，静止等待厂家要求的校零时间后再做检查，记录实际时间。
[ ] 两车静止录60–90秒，保留gyro、accel、Odom、UWB原始帧和电压。
[ ] 安全条件允许时，每车分别做小幅左/右转和短直线，另一辆保持静止。
[ ] 独立量取实际角度/距离，检查轴、正负号、单位及Odom/gyro响应。
[ ] 本次短测用于方向/尺度诊断，不直接当作无噪声标定或精度验收。

6. 时钟与视觉（需要建立空间精度参考时完成）
[ ] 保存三台主机时钟与同步服务日志，记录各话题header到底在哪打。
[ ] 若要连续轨迹精度：同时记录能独立识别的共同事件及同步误差依据。
[ ] 每段录像固定机位，记录镜头/分辨率/帧率和该段对应的bag。
[ ] P1–P4实际坐标用于拟合，另留Q点独立检查；记录尺量误差/点位定义。
[ ] marker刚性安装且方向明确；Car2微倾需要测量或明确保留为未知。
[ ] 当前新标定只用于对应安装与机位；核对后再判断能否迁移至旧视频。

离开前
[ ] 保存两车源码/版本、照片、尺量表、短测bag、时钟日志和操作记录。
[ ] 检查bag正常关闭、关键话题有内容，记录原件SHA256。
[ ] 未确认项逐一列出，写清原因；不把缺项填0或标为已完成。
```

## 每车记录表：复制两份，分别填写

```text
车辆：Car1 / Car2
记录时刻及时间区：
主机IP / Ubuntu / ROS：
控制板型号 / 硬件版本 / 照片名：
IMU型号 / 安装方向 / 证据：
固件版本 / 来源 / 是否能证明实验时版本：
当前底盘源码SHA / 活动二进制SHA：
Odom底盘角速度来源 / 公式或代码位置：
gyro零点采集条件 / 扣除位置 / 串口发送字段：
底盘端口 / 设备串号 / UWB端口 / 设备串号：
实际base参考点定义 / 依据 / 照片名：
base→天线：x前____m，y左____m；天线中心离地____m：
marker→天线：x前____m，y左____m；marker中心离地____m：
marker相对车体朝向 / 倾斜 / 测量方法：
重复测量结果 / 尺子分辨率 / 不确定性说明：
自T10以来改变的部件及时间；依据为当时记录/照片/记忆：
静止短测bag / 转向短测bag / 独立实测角度与距离：
ROS时间模式 / Odom打戳位置 / IMU打戳位置 / UWB打戳位置：
对应照片 / 视频 / 同步事件及其误差依据：
尚未确认项：
```

## 测量和判断时要分清的参考点

- 车体系在本清单中定义为x向前、y向左、z向上；房间X/Y另行记录，不能因车头改变就混用两套坐标。
- “base原点”要有厂家机械/运动学定义或可核对的源码与机械对应依据。话题frame叫base_footprint、URDF某个TF为0、取车体几何中心，都不能单独证明物理积分原点。
- base→天线与marker→天线是两组不同的外参。测量有向水平偏移；天线高度是天线中心到地面的高度。无法确认base原点时，先保留对明确实物点的测量，并把原点对应填未知。
- 当时用户手工记录仅供核对：Car1 marker中心离地0.37m、天线0.17m，marker→天线前0.07m/右0.13m；Car2分别0.23m/0.20m，marker→天线后0.17m/左0.025m，板微倾未量角。这些不是base→天线杆臂，也不是本次现场已复测值；Car1标记板曾计划拆除，必须记录安装是否改变。
- 车间卷尺距离注明测的是天线中心、标记中心还是车体中心，以及水平距离/斜距。保留原始读数，统一单位到m时另记转换。
- 墙锚未移动且已有可信尺量记录时，确认实体ID、坐标轴与记录版本即可；有变化或证据缺失的项目才补测。不用为本清单重复测量全部固定锚。

## IMU来源复核的具体问题

厂家通用资料由用户摘录：开机阶段采集并保存陀螺仪/加速度计零点，之后读取扣零点后的数据；用户上传截图确认C30D硬件存在ICM20948与MPU6050版本分支。完整《11_IMU初始化与零点漂移》及实际MCU工程本轮未读取。这些登记为通用设计证据，两车大致采用相同流程是工作假设，不能直接指定实际芯片/历史固件。

要追踪的两组串口字段（从0计数）分别是：Odom底盘角速度索引6、7，IMU gyro_z索引18、19。应在MCU端找到填入它们的变量及赋值来源。确认gyro扣零点后，继续检查串口发送用的是否正是该变量；仅看初始化函数、变量名或“ROS负责姿态”不能完成这条追踪。

即使板端做过校零，离线模型仍可估计残余零偏与漂移。两车分别设状态和噪声假设；不把板端补偿与我们已完成定位融合混为一件事。测试旋转响应可以核对方向/量级，不能单独证明MCU内部采用纯编码器或哪种融合比例。

## 附录A：虚拟机只读检查与新建记录目录

下面命令只做诊断与写新证据，不启动底盘、UWB或运动节点。若设备尚未启动，由已验证的启动清单单独启动；不要用这段检查命令判断设备应自动启动。先核对今天IP，变化时修改三项变量。后续命令在**同一个wheeltec-client@ubuntu终端**运行。

```bash
CHECK_DIR="$(mktemp -d "$HOME/uwb_hw_recheck_XXXXXXXX")"
CAR1_IP=192.168.31.10
CAR2_IP=192.168.31.24
VM_IP=192.168.31.182
MASTER_URI="http://$CAR2_IP:11311"
printf 'CHECK_DIR=%s\n' "$CHECK_DIR"
ip -4 addr show | tee "$CHECK_DIR/vm_ip.txt"
timedatectl status | tee "$CHECK_DIR/vm_clock.txt"

source /opt/ros/melodic/setup.bash
source "$HOME/uwb-coop-localization-ros1/ros_ws/devel/setup.bash"
export ROS_MASTER_URI="$MASTER_URI" ROS_IP="$VM_IP"
unset ROS_HOSTNAME ROS_NAMESPACE

env -u ROS_HOSTNAME -u ROS_NAMESPACE \
  ROS_MASTER_URI="$MASTER_URI" ROS_IP="$VM_IP" \
  timeout 8s rosnode list -a > "$CHECK_DIR/nodes.txt" 2>&1
cat "$CHECK_DIR/nodes.txt"

env -u ROS_HOSTNAME -u ROS_NAMESPACE \
  ROS_MASTER_URI="$MASTER_URI" ROS_IP="$VM_IP" \
  timeout 5s rosparam get /use_sim_time \
  > "$CHECK_DIR/use_sim_time.txt" 2>&1
cat "$CHECK_DIR/use_sim_time.txt"
```

若use_sim_time参数不存在，保留该结果，结合节点实现和运行配置核对；参数不存在本身不作为采样时钟/延迟已标定的证明。NTP显示已同步也不提供历史同步误差界。

节点已运行后，逐话题检查实际消息并保存结果；超时或空文件是待排查，不是通过。

```bash
for topic in /car1/odom /car2/odom /car1/imu /car2/imu \
             /car1/uwb/ranges /car2/uwb/ranges
do
  key="${topic#/}"
  key="${key//\//_}"
  env -u ROS_HOSTNAME -u ROS_NAMESPACE \
    ROS_MASTER_URI="$MASTER_URI" ROS_IP="$VM_IP" \
    timeout 8s rostopic echo -n 1 "$topic" \
    > "$CHECK_DIR/$key.sample.txt" 2>&1
  result=$?
  printf '%s exit=%s\n' "$topic" "$result" | tee -a "$CHECK_DIR/topic_status.txt"
done
```

## 附录B：两车当前时钟、端口和身份（从虚拟机执行）

两次SSH可能分别询问密码。命令在远程只读身份、设备属性和日志状态，不打开串口、不发送设备指令；账号无权限的项目保留原错误。

```bash
for car in car1 car2
do
  if [ "$car" = car1 ]; then car_ip="$CAR1_IP"; else car_ip="$CAR2_IP"; fi
  ssh "wheeltec@$car_ip" '
    uname -a
    id
    date -u --iso-8601=ns
    timedatectl status
    ls -l /dev/wheeltec_controller
    for dev in /dev/ttyCH343USB* /dev/ttyACM* /dev/ttyUSB* /dev/serial/by-id/*; do
      [ -e "$dev" ] || continue
      udevadm info --query=property --name="$dev" |
        grep -E "^(DEVNAME|ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL_SHORT|ID_SERIAL)="
    done
  ' > "$CHECK_DIR/${car}_identity_ports_clock.txt" 2>&1
  result=$?
  printf '%s SSH exit=%s\n' "$car" "$result"
done
```

此前UWB身份供核对：Car1曾使用by-id含5B2E110223的设备，Car2曾使用串号5725005414；tty编号曾变化。今天以实际串号、接线及正确数据为准，不能只沿用ttyCH343USB1。源码和活动程序身份采集采用同目录[VM_COMMANDS.md](VM_COMMANDS.md)的只读采集器；活动节点未运行时允许没有二进制记录，不为取证专门启动底盘。

## 附录C：静止短测与收尾

先确认六个主要话题实际有消息、运动脚本和键盘控制已停止，车辆物理静止。以下仅录制，不发送速度或事件指令。执行期间保持静止，90秒后自动结束。

```bash
STATIC_BAG="$CHECK_DIR/HW_static_check.bag"
env -u ROS_HOSTNAME -u ROS_NAMESPACE \
  ROS_MASTER_URI="$MASTER_URI" ROS_IP="$VM_IP" \
  rosbag record --duration=90 -b 512 -O "$STATIC_BAG" \
  /car1/odom /car2/odom /car1/imu /car2/imu \
  /car1/uwb/ranges /car2/uwb/ranges \
  /car1/uwb/frame3 /car2/nlink_linktrack_nodeframe3 \
  /car1/PowerVoltage /car2/PowerVoltage \
  /car1/cmd_vel /car2/cmd_vel /rosout /tf /tf_static /clock

rosbag info "$STATIC_BAG" | tee "$STATIC_BAG.info.txt"
sha256sum "$STATIC_BAG" | tee "$STATIC_BAG.sha256"
```

订阅列表不证明每个话题有数据；按bag实际内容检查。电压按各自电池规格判断，不套用同一阈值。UWB话题约50Hz、Odom/IMU约20Hz是以往观测，不是本次自动验收阈值；同时检查有效测距、覆盖率和长缺口。

若做转向/短直线检查，另录新bag、记录实际测量与动作时间；只采用已经检查过的低速控制方法，先确认空间、人员与停止方式。本清单不提供自动运动命令，也不把这些诊断短测替代正式独立验证。

保存P/Q坐标、照片、原始视频及文件名对应关系，带回CHECK_DIR整个目录。未来记录的时钟状态、重新安装的外参或新的相机标定，均按适用时间范围登记，不能直接追认旧T10的未知项。旧数据原件与留出T09/T11/T13/T15保持原有用途；本次硬件诊断不解封其定位评价。
