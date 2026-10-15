# Car2 快速启动与关机指南

现场版本日期：2026-10-11；归档更新：2026-10-15。所有下面的 SSH 命令均在虚拟机终端执行；不需要小车屏幕。底盘、UWB 各开独立终端，控制窗口选择键盘或可选自动脚本，另开一个终端检查和录包。

这份指南根据现场输出整理。底盘、UWB node_0 测距及键盘已验证；相对运动脚本完成过一次原地转向和一次 L 形流程。每次启动仍须核验实际设备和数据。本文包含可选实车运动命令，离线数据整理不需要执行这些命令。

## 固定信息

| 项目 | 当前值 |
|---|---|
| Car2 SSH | wheeltec@192.168.31.24 |
| ROS Master | http://192.168.31.24:11311 |
| VM ROS_IP | 192.168.31.182 |
| Car2 ROS | Noetic |
| VM ROS | Melodic |
| Car2 UWB 工作空间 | /home/wheeltec/candy/uwb-coop-localization-ros1/ros_ws |
| Car2 底盘工作空间 | /home/wheeltec/wheeltec_robot |
| Car2 UWB | P-A0 / node_0；此前拔插验证串口 /dev/ttyCH343USB1 |
| 底盘串口 | /dev/wheeltec_controller，115200 baud |
| UWB 波特率 | 921600 baud |
| 车型 | V550_mec |

IP 或 USB 接线变化后，应核对并更新下面对应的命令。UWB 不使用曾误选的 /dev/ttyCH343USB3。不要把 VM 的串口驱动切换命令照搬到 Car2。

## 0. 开机与远程连接

小车开机并连回实验 Wi-Fi 后执行。若出现密码提示，输入小车密码。

```bash
ssh -o ConnectTimeout=5 wheeltec@192.168.31.24 'hostname -I; uptime'
```

SSH 失败时先查网络与当前 IP；未启动 ROS Master 不影响 SSH 登录。不要因 ROS Master 不通而重装驱动。

## 1. 窗口 A：底盘、Odom、IMU、电压

命令启动后保持窗口运行。成功标志：Data ready、wheeltec_robot serial port opened。

```bash
ssh -t wheeltec@192.168.31.24 '
source /opt/ros/noetic/setup.bash || exit 1
source /home/wheeltec/wheeltec_robot/devel/setup.bash || exit 1
export ROS_MASTER_URI=http://192.168.31.24:11311
export ROS_IP=192.168.31.24
export ROS_NAMESPACE=/car2
unset ROS_HOSTNAME

roslaunch \
  /home/wheeltec/wheeltec_robot/src/turn_on_wheeltec_robot/launch/include/base_serial.launch \
  car_mode:=V550_mec \
  odom_frame_id:=car2/odom_combined
'
```

只启动底盘采集节点；IMU 随底盘启动。该最小 launch 没有提供完整 TF，不代表已经建立车体和 UWB 外参。

## 2. 窗口 B：UWB

加载 candy 下的工作空间；它已能找到 uwb_coop_localization 和 nlink_parser。保持窗口运行。不要再次叠加 ROS_NAMESPACE=/car2，因为 launch 自己设置命名空间。

```bash
ssh -t wheeltec@192.168.31.24 '
source /opt/ros/noetic/setup.bash || exit 1
source /home/wheeltec/candy/uwb-coop-localization-ros1/ros_ws/devel/setup.bash || exit 1
export ROS_MASTER_URI=http://192.168.31.24:11311
export ROS_IP=192.168.31.24
unset ROS_HOSTNAME ROS_NAMESPACE

roslaunch uwb_coop_localization vehicle_nlink_frame3_bridge.launch \
  vehicle_namespace:=car2 \
  port:=/dev/ttyCH343USB1 \
  baudrate:=921600
'
```

串口打开只说明设备文件可读，仍需检查 /car2/uwb/ranges 出现 tag_id: node_0 及参考节点距离。若串口编号变化，先按下方只读命令核对；不能仅凭打开成功认定接对设备。

```bash
ssh wheeltec@192.168.31.24 '
ls -l /dev/ttyCH343USB* /dev/wheeltec_controller /dev/serial/by-id/* 2>/dev/null
fuser -v /dev/ttyCH343USB1 2>&1 || true
udevadm info --query=property --name=/dev/ttyCH343USB1 \
  | grep -E "^(ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL_SHORT)="
'
```


如果出现 IO Exception (13): Permission denied，且设备为 root:dialout、权限 crw-rw----，说明启动进程没有足够的串口访问权限。本次恢复遇到过该错误；当时 USB1 的 ID_SERIAL_SHORT 为 5725005414，处理权限后恢复了 node_0 消息。今后仍应按实际消息验证数据源。

现场快速处理：确认仍是目标 UWB 串口后，仅把这个设备文件的所有者改为 wheeltec，不扩大其他用户或其他串口权限。在 VM 执行：

```bash
ssh -t wheeltec@192.168.31.24 '
sudo chown wheeltec /dev/ttyCH343USB1 &&
ls -l /dev/ttyCH343USB1
'
```

随后使用新的 SSH 连接重新执行本节 UWB 启动命令。此所有权变更可能在拔插或重启后失效；权限处理与 UWB 固件配置无关。长期可检查 wheeltec 是否加入 dialout 组；如需加入，执行 sudo usermod -aG dialout wheeltec 后，新登录会话才获得新增组权限。该长期配置尚未在此次现场执行验证。

## 3. 窗口 C：键盘

先保持静止。充电时不按运动键。正式试动前拔掉充电线，车轮着地并留出通道。

```bash
ssh -t wheeltec@192.168.31.24 '
source /opt/ros/noetic/setup.bash || exit 1
source /home/wheeltec/wheeltec_robot/devel/setup.bash || exit 1
export ROS_MASTER_URI=http://192.168.31.24:11311
export ROS_IP=192.168.31.24
export ROS_NAMESPACE=/car2
unset ROS_HOSTNAME

rosrun wheeltec_robot_rc turtlebot_teleop_key.py \
  __name:=turtlebot_teleop_keyboard \
  /car2/turtlebot_teleop_keyboard/cmd_vel:=/car2/cmd_vel
'
```

每次重启键盘后速度恢复 0.2 m/s、转速 0.5 rad/s。按 x 14 次，确认显示 speed 约 0.04575；然后按 k。键盘窗口必须获得焦点。多按一次 x 可按一次 w 回到接近原速度；两次缩放相乘为 0.99，并非精确逆操作，需看显示值。

| 键 | 默认 CommonMode 的行为 |
|---|---|
| i | 前进 |
| , | 后退 |
| j / l | 左转 / 右转 |
| k 或空格 | 停止；通常不打印确认文字 |
| x / w | 线速度降低 / 增加 10% |
| c | 转速降低 10% |
| Ctrl+C | 退出键盘节点，并尝试发送零速度 |

不按键约 0.5 秒后，该脚本将目标运动归零；这不是对网络中断时硬件急停的保证。本次 L 形实验使用默认 CommonMode，不按 b 切换全向模式。准备搬车时先按 k 并退出键盘。

## 4. 窗口 D：检查

每个新 VM 检查/录包终端都先加载下面环境。

```bash
cd /home/wheeltec-client/uwb-coop-localization-ros1
source /opt/ros/melodic/setup.bash
source ros_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.31.24:11311
export ROS_IP=192.168.31.182
unset ROS_HOSTNAME ROS_NAMESPACE

timeout 5 rosnode list
timeout 5 rostopic echo -n 1 /car2/PowerVoltage
timeout 8 rostopic echo -n 2 /car2/uwb/ranges
timeout 5 rostopic echo -n 1 /car2/odom/header
timeout 5 rostopic echo -n 1 /car2/imu/header
rostopic info /car2/cmd_vel
```

应看到 wheeltec_robot、nlink_linktrack、nlink_frame3_bridge、turtlebot_teleop_keyboard；cmd_vel 的发布者为键盘，订阅者为 wheeltec_robot。UWB 为 node_0，参考节点为 node_2、node_3、node_8、node_10。墙上参考节点需供电。

需要检查频率时执行：

```bash
timeout 5 rostopic hz /car2/uwb/ranges
timeout 5 rostopic hz /car2/odom
timeout 5 rostopic hz /car2/imu
```

预计 UWB 约 50 Hz，Odom/IMU 约 20 Hz。timeout 到时结束属于预期行为。

电压不能单独证明续航或动力恢复。本次 9.968–9.980 V 的一次尝试实际没有运动；约 10.072 V 时也尚未验证动力。不要将这些观测当成厂家规定阈值。正式动态录包前，先短距离试动并核对实际运动与 Odom。

## 5. 可选：L 形实验录包

先实测标记点及 UWB 天线中心高度，并拍照记录。录包开始后先静止，再执行轨迹；到每个标记点停留，最后再静止。测量的是天线中心位置；转弯时车体与天线偏移会影响比较。不要为了贴合结果更改原始 bag 或重新拟合验证数据的偏置。

```bash
run_dir=/home/wheeltec-client/uwb_field_tests/20261011
mkdir -p "$run_dir"
l_bag="$run_dir/CAR2_WALL_UWB_ODOM_IMU_key_Lshape_$(date +%Y%m%d_%H%M%S).bag"
printf '本次文件：%s\n' "$l_bag"

rosbag record --duration=110 -O "$l_bag" \
  /car2/cmd_vel \
  /car2/uwb/ranges \
  /car2/odom \
  /car2/imu \
  /car2/PowerVoltage

rosbag info "$l_bag"
sha256sum "$l_bag"
```

开始前确认所有必需话题有消息。全程用键盘窗口控制，录包窗口保持运行；提前完成可 Ctrl+C 结束录包，等待 .bag 保存。原始 bag 保留在现场数据目录，不提交 Git。

## 6. 可选：Odom 反馈相对运动

脚本位于本仓库 `tools/field_session_20261010_11/car2_relative_motion.py`，运行环境为车端 Python 3 / ROS Noetic。它控制相对当前车头的运动；房间坐标到位需要人工摆放初始位置和方向。
先退出键盘控制，保留底盘/UWB；脚本会拒绝存在其他 `/car2/cmd_vel` 发布者或缺少底盘订阅者的情况。路径清空、车轮着地、充电线断开后，先录包再试动。

在 VM 复制脚本：

```bash
scp tools/field_session_20261010_11/car2_relative_motion.py \
  wheeltec@192.168.31.24:/tmp/car2_relative_motion.py
```

不带 `--execute` 为 dry-run。原地试转的现场成功参数为 0.20 rad/s；0.15 rad/s 曾触发停滞退出。

```bash
ssh -t wheeltec@192.168.31.24 '
source /opt/ros/noetic/setup.bash || exit 1
source /home/wheeltec/wheeltec_robot/devel/setup.bash || exit 1
export ROS_MASTER_URI=http://192.168.31.24:11311
export ROS_IP=192.168.31.24
unset ROS_HOSTNAME ROS_NAMESPACE
python3 -u /tmp/car2_relative_motion.py \
  --turn-only --turn-deg -90 --turn-speed 0.20 --execute
'
```

通过实际稳定角度检查后，完整 L 形使用相同 SSH 环境，把 Python 命令换为：

```bash
python3 -u /tmp/car2_relative_motion.py \
  --distance 1.00 --turn-deg -90 \
  --linear-speed 0.045 --turn-speed 0.20 --execute
```

使用五路话题录包，预留约 180 s，开始后有 5 s 静止准备时间。完整流程为前进、停留、右转、停留、前进、静止结束。控制窗口 Ctrl+C 会尝试发送零速度；该脚本没有避障或硬件急停保证。
前进停止容差为 0.025 m。控制器打印的角度/距离是当时反馈值，仍需核验制动后的稳定位置和方向。独立转向包最终 Odom 净角度与控制器打印值存在差异，不能宣称物理转角精确到 0.2°。
先量最终天线坐标再移动车辆；计划终点不作为实际终点测量值。

## 7. 正常关机、充电

顺序：键盘窗口按 k，再 Ctrl+C；录包窗口 Ctrl+C 并等文件保存；再在 VM 执行关机命令。

```bash
ssh -t wheeltec@192.168.31.24 'sudo shutdown -h now'
```

等待主机关机后再关闭小车物理电源，按设备原有充电方式充电。SSH 因关机断开属于预期。下次重新开机后按本指南从网络检查开始。

## 保存到仓库

本文件归档位置为仓库 `docs/CAR2_QUICK_START.md`；新分支拉取后即可使用。不要将整份 Markdown 当作 shell 脚本执行，只复制当前步骤对应的代码块。现场 IP、设备路径及权限可能变化，仍需按检查步骤确认。
