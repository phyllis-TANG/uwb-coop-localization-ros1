# EXP005 双车静止 LOS 现场执行手册

本手册用于第一次真实双车P-B静止测距。目标是得到1、2、3、4 m四个卷尺真值下的
双向原始测距，不启动导航、不发布 `/cmd_vel`、不修改UWB配置。

## 0. 开始前填写

| 项目 | Car1 | Car2 |
| --- | --- | --- |
| 主机名 |  |  |
| IP |  |  |
| P-B USB serial |  |  |
| 稳定串口路径 |  |  |
| LinkTrack node ID |  |  |
| UWB安装高度/朝向 |  |  |

另行记录：ROS Master地址、卷尺参考点照片、实验人员、日期、场地和天气/遮挡
情况。

两个P-B必须具有不同node ID，并在同一兼容网络参数下互相测距。若只读检查发现ID
相同、型号不符或无法互测，停止EXP005；任何配置变更都必须先备份原始配置并使用
单独审批过的步骤。

## 1. 每台Linux计算机重启后的准备

在Car1、Car2及记录电脑上分别执行。仓库路径不同的主机应替换第一行，不要猜测。

```bash
cd /home/wheeltec-client/uwb-coop-localization-ros1

git status --short --branch
git log -1 --oneline --decorate

source /opt/ros/melodic/setup.bash
source ros_ws/devel/setup.bash

printf 'host=%s\n' "$(hostname)"
printf 'ROS_MASTER_URI=%s\n' "${ROS_MASTER_URI:-unset}"
printf 'ROS_IP=%s\n' "${ROS_IP:-unset}"
printf 'ROS_HOSTNAME=%s\n' "${ROS_HOSTNAME:-unset}"
```

工作区不干净、分支不一致或ROS环境变量与现场拓扑不符时先停止，不直接拉取、
覆盖或修改配置。

## 2. 两车分别保存只读快照

Car1：

```bash
uwb_snapshot_root="/home/wheeltec-client/uwb_experiments/EXP005_snapshots/car1"

rosrun uwb_coop_localization collect_field_snapshot.sh \
  "$uwb_snapshot_root"
```

Car2将末尾目录改为 `car2` 后执行同一命令。记录电脑使用 `recorder`。保存三台
主机各自打印的文件路径，不要让不同主机写到同一个未区分名称的目录。

快照只读取主机、时间、网络、ROS话题和串口枚举状态，不打开串口。重点核对：

- 两车系统时间、时区和chrony状态；
- IP、路由、`ROS_MASTER_URI`、`ROS_IP/ROS_HOSTNAME`；
- 两个P-B的USB serial和 `/dev/serial/by-id` 路径；
- 当前ROS节点、话题、消息类型和 `/use_sim_time`；
- 两车是否意外出现相同的 `odom`、`base_link` 或UWB节点名。

## 3. 串口只读占用检查

在每个P-B物理连接的计算机上执行：

```bash
id
ls -l /dev/serial/by-id/
```

从输出复制完整稳定路径，再显式设置；不要把下面占位文字原样执行：

```bash
uwb_port="/dev/serial/by-id/替换为本机实际P-B路径"

test -e "$uwb_port" || {
  printf '%s\n' "串口路径不存在，请停止。"
  exit 1
}

fuser -v "$uwb_port" 2>&1 || true
```

若 `fuser` 显示未知程序正在占用设备，先辨认进程归属，不直接终止进程。

## 4. 启动两个只读UWB驱动

仅在节点ID、串口路径和ROS Master已确认后执行。Car1终端：

```bash
roslaunch uwb_coop_localization vehicle_uwb_driver.launch \
  vehicle_namespace:=car1 \
  port:="$uwb_port"
```

Car2终端将命名空间改为 `car2`，并使用Car2本机刚确认的 `uwb_port`。驱动只读取
Frame3并发布ROS消息，但两个终端都要保持打开并观察错误、掉线或异常重连。

## 5. 记录电脑上的双车话题验收

只有共用同一个ROS Master时，记录电脑才应同时看到以下四个话题：

```bash
rostopic type /car1/uwb/ranges
rostopic type /car1/uwb/frame3
rostopic type /car2/uwb/ranges
rostopic type /car2/uwb/frame3

rostopic echo -n 1 /car1/uwb/ranges
rostopic echo -n 1 /car2/uwb/ranges

timeout 6 rostopic hz /car1/uwb/ranges
timeout 6 rostopic hz /car2/uwb/ranges
```

必须人工确认：

- `tag_id`是两个不同node ID；
- Car1能看到Car2，Car2能看到Car1，距离随物理移动变化；
- 两侧方向互为倒置，例如 `node_0 -> node_1` 与 `node_1 -> node_0`；
- 两侧频率稳定，消息不是持续空数组；
- 话题类型分别为 `UwbRangeArray` 和 `LinktrackFrame3`。

若实际node ID方向与默认分析器不同，只记录真实方向；不要为迎合默认值修改设备。

## 6A. 共用ROS Master：集中录制一个bag

先把两车放到卷尺真值位置，记录天线参考点的实际读数。下面以实测1.000 m为例；
每个距离都使用新的文件名和输出目录。

```bash
uwb_exp_root="/home/wheeltec-client/uwb_bags/EXP005"
uwb_distance_label="1m"
uwb_truth_m="1.000"
uwb_bag="$uwb_exp_root/EXP005_two_car_static_LOS_${uwb_distance_label}.bag"

mkdir -p "$uwb_exp_root"

test ! -e "$uwb_bag" && test ! -e "${uwb_bag}.active" || {
  printf '%s\n' "目标bag或active文件已经存在，请停止。"
  exit 1
}

printf 'bag=%s\ntruth_m=%s\n' "$uwb_bag" "$uwb_truth_m"

rosbag record -O "$uwb_bag" \
  /car1/uwb/ranges \
  /car1/uwb/frame3 \
  /car2/uwb/ranges \
  /car2/uwb/frame3
```

稳定记录60--90 s后按一次 `Ctrl+C`，等待bag关闭并返回命令提示符。不要在录制期间
移动车辆或删除异常数据。

立即检查：

```bash
rosbag info "$uwb_bag"
sha256sum "$uwb_bag"
```

确认四个话题都有消息、时长正确且不存在 `.active` 文件后，才能移动到下一个
距离。

## 6B. 不共用ROS Master：两车分别本地录包

Car1本地：

```bash
rosbag record -O EXP005_two_car_static_LOS_1m_car1.bag \
  /car1/uwb/ranges \
  /car1/uwb/frame3
```

Car2本地：

```bash
rosbag record -O EXP005_two_car_static_LOS_1m_car2.bag \
  /car2/uwb/ranges \
  /car2/uwb/frame3
```

两侧在同一口头倒计时后开始，记录同一段60--90 s静止数据，并分别保存
`rosbag info`、SHA256和系统时间快照。不要通过覆盖系统时间来强行对齐。

## 7. 每个距离的离线分析

共用ROS Master的单bag示例：

```bash
uwb_analysis_dir="/home/wheeltec-client/uwb_analysis/EXP005_${uwb_distance_label}"

test ! -e "$uwb_analysis_dir" || {
  printf '%s\n' "分析目录已经存在，请停止。"
  exit 1
}

python2 ros_ws/src/uwb_coop_localization/scripts/analyze_two_car_bag.py \
  "$uwb_bag" \
  --output-dir "$uwb_analysis_dir" \
  --truth-distance-m "$uwb_truth_m"
```

根据真实node ID设置参数；例如Car1=`node_1`、Car2=`node_0`时增加：

```text
--car1-id node_1 --car2-id node_0
```

两车分别录包时，在Car1 bag后增加：

```text
--car2-bag /完整路径/EXP005_two_car_static_LOS_1m_car2.bag
```

若30 ms默认容差内无法配对，先检查两机快照和时钟差，不为了生成结果随意放大
容差。

## 8. EXP005现场通过条件

- 1、2、3、4 m均有卷尺读数、参考点照片、安装记录和完整bag；
- 两侧UWB均稳定发布非零测距，Frame3诊断话题可读；
- 每个bag均已执行 `rosbag info` 和SHA256；
- 分析输出包含配对CSV、摘要和PNG，真值参数使用实际卷尺读数；
- 没有无法解释的节点ID、时间差、串口掉线或双向测距异常。

EXP005全部通过后才进入EXP006姿态敏感性实验；任一项失败时保留证据并停止扩展到
动态实验。
