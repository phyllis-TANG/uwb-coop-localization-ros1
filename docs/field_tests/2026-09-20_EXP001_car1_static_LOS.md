# EXP001 — Car1 Static LOS UWB Test

**Project:** UWB Cooperative Localization on ROS1  
**Experiment ID:** EXP001_car1_static_LOS  
**Date:** 2026-09-20  
**Platform:** WHEELTEC ROS1 vehicle + Nooploop LinkTrack UWB  
**Environment:** Ubuntu 18.04 / ROS Melodic / Python 2.7  
**Test type:** Static LOS ranging  
**Vehicle motion:** Disabled; vehicle remained stationary throughout the test

**Bag:** `EXP001_car1_static_LOS.bag`
**SHA256:** 待在保存原始 bag 的现场机器由离线脚本计算，禁止猜测

> The onboard computer displayed older system timestamps such as `Nov 19 2024`.
> Those timestamps are not the experiment date; the actual date is 2026-09-20.

## 1. Objective

Verify the complete real-data pipeline:

```text
Nooploop P-B UWB
        ↓ USB
Vehicle onboard Ubuntu
        ↓
Node_Frame3 serial parser
        ↓
ROS /uwb/ranges
        ↓ Wi-Fi / ROS1 network
Ubuntu VMware client
        ↓
rostopic / rosbag
```

The experiment covered only UWB communication and acquisition. No vehicle
motion command, keyboard teleoperation, navigation, or `/cmd_vel` was used.

## 2. UWB Configuration

### P-A

| Parameter | Value |
| --- | --- |
| Model | LinkTrack_P_A |
| USB Serial | 5725005414 |
| Mode | DR_MODE0 |
| Role | NODE |
| Node ID | N0 / node_0 |
| Protocol | Node_Frame3 |
| Capacity | 20 |
| Baudrate | 921600 |
| Update Rate | 50 Hz |

### P-B

| Parameter | Value |
| --- | --- |
| Model | LinkTrack_P_B |
| USB Serial | 5B2E110223 |
| Original Mode | LP_MODE6 |
| Original Role | ANCHOR |
| Original ID | A0 |
| Current Mode | DR_MODE0 |
| Current Role | NODE |
| Current ID | N1 / node_1 |
| Protocol | Node_Frame3 |
| Capacity | 20 |
| Baudrate | 921600 |
| Update Rate | 50 Hz |

P-B was physically mounted on Car1 and connected to the onboard computer using
USB Type-C.

## 3. Network Architecture

```text
Ubuntu VMware client (192.168.0.136)
        │ Wi-Fi / local vehicle network
        ▼
WHEELTEC onboard computer (192.168.0.100)
```

ROS Master:

```text
http://192.168.0.100:11311
```

Virtual-machine ROS environment:

```text
ROS_MASTER_URI=http://192.168.0.100:11311
ROS_HOSTNAME=192.168.0.136
```

Vehicle ROS environment:

```text
ROS_MASTER_URI=http://192.168.0.100:11311
ROS_HOSTNAME=192.168.0.100
```

The VMware Ubuntu system successfully reached the vehicle using ping and SSH.

## 4. SSH Handling

Multiple WHEELTEC robots may use `192.168.0.100`, so the normal SSH
`known_hosts` file was not modified. A temporary file was used:

```bash
rm -f /tmp/wheeltec_test_known_hosts
ssh \
  -o UserKnownHostsFile=/tmp/wheeltec_test_known_hosts \
  -o StrictHostKeyChecking=accept-new \
  wheeltec@192.168.0.100
```

Successful vehicle shell:

```text
wheeltec@wheeltec:~$
```

## 5. ROS Master Verification

Initially, neither of these checks found a ROS Master on the vehicle:

```bash
ps -ef | grep -E '[r]oscore|[r]osmaster'
ss -lnt | grep 11311
```

An early attempt accidentally started `roscore` on the VMware client
(`192.168.0.136`). The correct procedure was to SSH into the vehicle and run
`roscore` from the `wheeltec@wheeltec` shell. The VMware client then accessed
the remote Master with `rostopic list` at
`http://192.168.0.100:11311`.

## 6. UWB ROS Package Deployment

Source package path on the VMware client:

```text
/home/wheeltec-client/uwb-coop-localization-ros1/ros_ws/src/uwb_coop_localization
```

Vehicle workspace and copied package:

```text
/home/wheeltec/uwb_ws
/home/wheeltec/uwb_ws/src/uwb_coop_localization
```

Vehicle build:

```bash
source /opt/ros/melodic/setup.bash
source /home/wheeltec/wheeltec_robot/devel/setup.bash
cd /home/wheeltec/uwb_ws
catkin_make
```

The build completed successfully. The package included `UwbRange.msg`,
`UwbRangeArray.msg`, `uwb_linktrack_driver.py`, and
`uwb_linktrack_driver.launch`.

## 7. P-B USB Detection

P-B was detected by the vehicle onboard Ubuntu.

```text
Stable path: /dev/serial/by-id/usb-1a86_USB_Single_Serial_5B2E110223-if00
Kernel device: /dev/ttyACM0
Mapping: usb-1a86_USB_Single_Serial_5B2E110223-if00 -> ../../ttyACM0
```

Commands used:

```bash
ls -l /dev/serial/by-id/
readlink -f \
  /dev/serial/by-id/usb-1a86_USB_Single_Serial_5B2E110223-if00
```

The stable `/dev/serial/by-id/...` path should be preferred over hard-coding
`/dev/ttyACM0`.

## 8. Serial Permission Issue

The first driver attempt failed with `Permission denied`. Device permissions
were:

```text
crw-rw---- root dialout /dev/ttyACM0
```

The `wheeltec` user was not initially in `dialout`. Adding it to that group and
starting a new login session resolved the issue; the driver then opened the
serial device successfully.

## 9. UWB Driver

Confirmed launch parameters:

```xml
<arg name="port" />
<arg name="baudrate" default="921600" />
<arg name="topic" default="/uwb/ranges" />
<arg name="frame_id" default="uwb_linktrack" />
<arg name="node_prefix" default="node_" />
```

The read-only driver ran on the vehicle using the stable serial path and
reported:

```text
Reading LinkTrack Frame3 data from
/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B2E110223-if00
at 921600 baud onto /uwb/ranges
```

## 10. VMware Custom Message Issue

The VMware client initially detected `/uwb/ranges`, but `rostopic echo` failed:

```text
Cannot load message class for [uwb_coop_localization/UwbRangeArray]
Are your messages built?
```

The VMware-side custom messages had not been built and sourced. The fix was:

```bash
cd /home/wheeltec-client/uwb-coop-localization-ros1/ros_ws
catkin_make
source /opt/ros/melodic/setup.bash
source devel/setup.bash
```

`rosmsg show uwb_coop_localization/UwbRangeArray` then displayed:

```text
std_msgs/Header header
string tag_id
uwb_coop_localization/UwbRange[] ranges
```

The VMware client subsequently decoded `/uwb/ranges` successfully.

## 11. Real UWB Measurement

Initial messages contained:

```text
tag_id: "node_1"
ranges: []
```

After node_0 was active and in range, a real measurement appeared:

```yaml
tag_id: "node_1"
ranges:
  - anchor_id: "node_0"
    range: 0.963
    quality: nan
```

This verified real `node_1 -> node_0` ranging from the vehicle-mounted P-B.

## 12. ROS Topic Frequency

`rostopic hz /uwb/ranges` remained close to 50 Hz. Observed results included:

```text
50.058  50.037  50.025  50.020
49.862  50.015  50.008  50.006
49.983  50.000  50.007  49.999
50.004  50.005  50.001  50.003 Hz
```

This agreed with the configured 50 Hz update rate and was considered stable
enough for the first static recording.

## 13. EXP001 Static LOS Recording

Conditions:

```text
Car1: stationary
P-B / node_1: mounted on Car1
P-A / node_0: stationary
Environment: LOS
Vehicle motors: not commanded
Navigation: disabled
/cmd_vel: not published
```

Recording command:

```bash
mkdir -p ~/uwb_bags
rosbag record \
  -O ~/uwb_bags/EXP001_car1_static_LOS.bag \
  /uwb/ranges \
  /rosout
```

Bag location:

```text
/home/wheeltec-client/uwb_bags/EXP001_car1_static_LOS.bag
```

`rosbag info` reported approximately:

```text
Duration: 2:20
Total messages: 7043

/uwb/ranges: 7039 messages
type: uwb_coop_localization/UwbRangeArray

/rosout: 4 messages
```

The message count is consistent with approximately 50 Hz over 2 min 20 s.

## 14. Experiment Result

The complete vehicle-mounted acquisition pipeline passed:

```text
P-B LinkTrack
  ↓ USB serial
Vehicle onboard Ubuntu
  ↓ Node_Frame3 parser
/uwb/ranges @ ~50 Hz
  ↓ ROS1 network
Ubuntu VMware client
  ↓
rosbag
```

```text
Vehicle network communication       PASS
SSH access                          PASS
Remote ROS Master                   PASS
P-B USB detection                   PASS
Stable USB by-id mapping            PASS
Serial access permission            PASS
Node_Frame3 parsing                 PASS
Custom ROS messages                 PASS
Remote ROS topic reception          PASS
Real node_1 → node_0 ranging        PASS
~50 Hz topic rate                   PASS
Static LOS rosbag recording         PASS
```

No vehicle motion was required.

## 15. Important Lessons

- The UWB driver should run on the computer physically connected to the UWB
  device. Here P-B was connected to the vehicle onboard computer.
- The VMware client needs the ROS message definitions and network access to the
  ROS Master, but does not need direct access to the UWB USB port.
- Prefer
  `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B2E110223-if00` over
  `/dev/ttyACM0`.
- Custom ROS messages must be built and sourced on every machine that decodes
  them.
- The current single-vehicle ROS Master should remain on `192.168.0.100`.

## 16. Current Project Status

Completed stages:

```text
UWB bench ranging
  ↓ Node_Frame3 parser
ROS read-only driver
  ↓ Vehicle physical installation
Vehicle USB integration
  ↓ Vehicle ROS Master
Remote ROS topic reception
  ↓
EXP001 static LOS recording
```

The project can now move from infrastructure debugging to controlled UWB
measurement experiments.

## 17. Recommended Next Experiment

Next: `EXP002_car1_static_human_NLOS`.

Keep Car1, node_0, node_1, and their distance fixed. Introduce only one new
variable: a human body blocking the direct UWB path. Record `/uwb/ranges` for a
direct comparison with EXP001.

Possible later experiments:

```text
EXP003_car1_static_vehicle_NLOS
EXP004_car1_manual_push_LOS
EXP005_car1_manual_push_NLOS
```

Motorized tests should begin only after static and manually moved baselines are
characterized.

## 18. Safety State at End of EXP001

```text
UWB ROS driver stopped with Ctrl+C
rosbag stopped with Ctrl+C
roscore may be stopped before disconnecting
SSH session can be closed
vehicle remains stationary
no /cmd_vel commands were issued
no navigation was started
no UWB firmware/configuration was modified during acquisition
```

EXP001 status: **PASS**.

The rosbag remains local at `~/uwb_bags/EXP001_car1_static_LOS.bag` and is
intentionally not committed to GitHub.

## 19. Offline-analysis interpretation

The retained baseline contains 7,039 `/uwb/ranges` messages, including 12
messages without a usable `node_0` range. The usable-target message percentage
is 99.830%; this is not ranging accuracy and not a complete radio packet
delivery rate. The raw range mean is 0.9748 m, median 0.9750 m, population
standard deviation 0.0288 m, and range 0.8610–1.0810 m.

Adjacent-change statistics use adjacent valid target measurements, skipping a
message without a usable target: median 0.0290 m, P95 0.0850 m, P99 0.1122 m,
2.305% above 0.10 m, and maximum 0.1720 m. `quality: NaN` is not interpreted as
a valid quality score. Bag reception time is used because its offset from the
header timestamp is approximately 57,902,871 seconds. No smoothing, filtering,
spike deletion, or independent distance ground truth is applied.

The formal four-experiment comparison and reproducible command are documented
in `2026-09-20_EXP001_004_comparison.md` and `../offline_bag_analysis.md`.
