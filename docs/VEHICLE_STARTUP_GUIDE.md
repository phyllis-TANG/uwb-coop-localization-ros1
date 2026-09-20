# WHEELTEC 小车 ROS 1 / UWB 启动指南

## 适用环境

- Ubuntu 18.04
- ROS Melodic
- VMware ROS 1 虚拟机
- WHEELTEC 小车板载 Ubuntu
- Nooploop LinkTrack P-B UWB

当前已验证的网络参数：

| 项目 | 值 |
| --- | --- |
| 虚拟机 | `192.168.0.136` |
| 小车 | `192.168.0.100` |
| ROS Master | `http://192.168.0.100:11311` |
| 小车 SSH 用户 | `wheeltec` |

## 0. 安全原则

仅进行 UWB 静态测试时，小车必须保持静止。禁止启动：

- `keyboard_teleop`
- `navigation`
- `move_base`
- 自动导航
- `/cmd_vel` 发布
- 任何主动让车轮运动的程序

UWB 静态测试不需要让小车运动。

## 1. 打开小车

打开小车总电源，然后确认：

- 小车板载电脑已启动；
- UWB P-B 指示灯正常；
- P-B Type-C 已连接小车 USB；
- 小车保持静止。

## 2. 电脑连接小车网络

Windows 连接对应的 WHEELTEC 小车 Wi-Fi，然后进入 Ubuntu ROS 1 虚拟机。

当前现场扫描到并已保存配置的候选 SSID 是 `WHEELTEC_TEST`。连接前仍应根据
小车标签或现场管理信息确认它属于当前小车；不要猜测或公开 Wi-Fi 密码。

## 3. 测试小车网络

在 Ubuntu 虚拟机执行：

```bash
ping -c 4 192.168.0.100
```

正常应出现：

```text
64 bytes from 192.168.0.100
0% packet loss
```

偶尔出现少量无线丢包时可以继续观察；如果完全无法 ping 通，不要继续 ROS
步骤。

## 4. SSH 连接小车

实验室中可能有多辆小车共用 `192.168.0.100`，因此不要删除原来的整个
`~/.ssh/known_hosts`。使用临时 SSH 主机记录：

```bash
rm -f /tmp/wheeltec_test_known_hosts
ssh \
  -o UserKnownHostsFile=/tmp/wheeltec_test_known_hosts \
  -o StrictHostKeyChecking=accept-new \
  wheeltec@192.168.0.100
```

输入小车密码。成功后，提示符应变为：

```text
wheeltec@wheeltec:~$
```

只有看到 `wheeltec@wheeltec`，才表示当前命令在小车板载电脑上执行。
`wheeltec-client@ubuntu` 表示当前仍在 ROS 虚拟机中。

## 5. 检查小车 ROS 环境

在小车提示符 `wheeltec@wheeltec:~$` 下执行：

```bash
echo "$ROS_MASTER_URI"
echo "$ROS_HOSTNAME"
```

预期为：

```text
http://192.168.0.100:11311
192.168.0.100
```

## 6. 检查 ROS Master 是否已经运行

在小车上执行：

```bash
ps -ef | grep -E '[r]oscore|[r]osmaster'
ss -lnt | grep 11311
```

如果两条命令都没有输出，说明 ROS Master 尚未启动。

## 7. 必要时启动 ROS Master

先确认提示符为 `wheeltec@wheeltec:~$`，且第 6 步确认没有现有 Master，再执行：

```bash
roscore
```

正常应看到：

```text
ROS_MASTER_URI=http://192.168.0.100:11311
started core service [/rosout]
```

保持该终端打开，不要按 `Ctrl+C`。

## 8. 虚拟机验证 ROS Master

回到提示符为 `wheeltec-client@ubuntu:~$` 的 Ubuntu 虚拟机，执行：

```bash
echo "$ROS_MASTER_URI"
rostopic list
```

`ROS_MASTER_URI` 应显示：

```text
http://192.168.0.100:11311
```

如果当前只有 `roscore`，话题列表至少应包含：

```text
/rosout
/rosout_agg
```

这表示虚拟机已经通过网络连接到小车 ROS Master。

## 9. 检查 UWB P-B

P-B USB serial：

```text
5B2E110223
```

使用内核通用 `cdc_acm` 驱动时，推荐的稳定路径是：

```text
/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B2E110223-if00
```

在**物理连接 P-B USB 的那台 Linux 计算机**上检查：

```bash
ls -l /dev/serial/by-id/
readlink -f \
  /dev/serial/by-id/usb-1a86_USB_Single_Serial_5B2E110223-if00
```

使用 `cdc_acm` 时，现场曾解析为 `/dev/ttyACM0`。程序应优先使用
`/dev/serial/by-id/...`，不要写死 `/dev/ttyACM0`，因为编号可能在重新插 USB
后改变。

> 注意：现场临时加载 WCH 官方 `ch343` 驱动时，设备节点为
> `/dev/ttyCH343USB0`，且未生成 `/dev/serial/by-id`。必须先确认当前驱动和
> 设备节点，不能把两种路径混用。

## 10. 当前 P-B 已验证状态

| 项目 | 值 |
| --- | --- |
| Model | `LinkTrack_P_B` |
| USB serial | `5B2E110223` |
| Mode | `DR_MODE0` |
| Role | `NODE` |
| ID | `N1` |
| Protocol | `Node_Frame3` |
| Baudrate | `921600` |
| Update rate | `50 Hz` |

已验证 `node_1 -> node_0` 的真实 UWB 测距正常。

## 11. 厂商 ROS 包

已确认厂商包路径：

```text
/home/wheeltec/wheeltec_robot/src/turn_on_wheeltec_robot
```

历史中曾使用：

```bash
roslaunch turn_on_wheeltec_robot turn_on_wheeltec_robot.launch
```

正式检查 launch 文件内容之前，不要自动执行该命令。它可能同时启动底盘、
IMU、雷达、串口或其他控制节点；静态 UWB 测试目前不需要启动整车系统。

## 12. 静态 UWB 实验的最小启动流程

仅做 UWB 静态采集时：

1. 打开小车电源；
2. 连接小车 Wi-Fi；
3. ping `192.168.0.100`；
4. SSH 进入小车；
5. 确认并在必要时启动小车 `roscore`；
6. 在虚拟机执行 `rostopic list`；
7. 在物理连接 P-B 的计算机上确认串口；
8. 启动 UWB ROS driver；
9. `rostopic echo` 检查 UWB 数据；
10. 启动 `rosbag record`；
11. 全程保持小车静止。

不需要启动导航或键盘控制。

## 13. 常见问题

### ping 不通

检查：

- Windows 是否连接正确的小车 Wi-Fi；
- 小车是否开机；
- Ubuntu 虚拟机是否仍有 `192.168.0.x` 网卡。

### SSH 提示 `REMOTE HOST IDENTIFICATION HAS CHANGED`

这可能表示以前连接过另一台使用相同 IP 的小车。不要删除整个
`known_hosts`，使用第 4 节的临时记录命令。

### `rostopic list` 显示 `Unable to communicate with master`

先在小车上检查：

```bash
ps -ef | grep -E '[r]oscore|[r]osmaster'
ss -lnt | grep 11311
```

没有输出表示 `roscore` 尚未启动。

### 出现 `Connection refused`

通常表示 `192.168.0.100` 可以访问，但端口 `11311` 没有 ROS Master 监听。

### UWB 串口找不到

使用 `cdc_acm` 时执行：

```bash
ls -l /dev/serial/by-id/
```

寻找包含 `5B2E110223` 的设备。若当前使用官方 `ch343` 驱动，则改为检查：

```bash
ls -l /dev/ttyCH343USB*
```

## 14. 关闭顺序

实验结束时：

1. 用 `Ctrl+C` 停止 UWB ROS 节点；
2. 用 `Ctrl+C` 停止 `rosbag`；
3. 用 `Ctrl+C` 停止本次实验单独启动的 `roscore`；
4. 确认所有测试程序结束后关闭小车。

不要停止并非本次实验启动、且可能被其他系统使用的 ROS Master。

## 15. 当前项目原则

每次只增加一个新的系统层：

```text
网络
  ↓
SSH
  ↓
ROS Master
  ↓
UWB 串口
  ↓
UWB ROS topic
  ↓
静态 rosbag
  ↓
人工手推测试
  ↓
底盘传感器
  ↓
双车
  ↓
协同定位
```

不要跨步骤同时排查多个问题。
