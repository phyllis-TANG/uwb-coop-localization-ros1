# 双车 UWB 模拟预演

## 目的

`two_car_uwb_simulator.py` 在没有真实车辆和 UWB 的环境中提供最小双车数据接口，
用于提前检查命名空间、消息类型、时间戳、rosbag 录制和后续融合节点输入。它不替代
真实硬件实验，也不把 EXP001--004 的单次统计当作普适误差模型。

默认发布：

| 话题 | 类型 | 含义 |
| --- | --- | --- |
| `/car1/odom` | `nav_msgs/Odometry` | Car1 模拟里程计/真值运动 |
| `/car2/odom` | `nav_msgs/Odometry` | Car2 模拟里程计/真值运动 |
| `/car1/uwb/ranges` | `UwbRangeArray` | node_0 到 node_1 的模拟测距 |
| `/car2/uwb/ranges` | `UwbRangeArray` | node_1 到 node_0 的模拟测距 |
| `/simulation/inter_car_range_truth` | `std_msgs/Float64` | 无噪声车间真值距离 |

## 启动

```bash
cd /home/wheeltec-client/uwb-coop-localization-ros1
catkin_make -C ros_ws
source ros_ws/devel/setup.bash
roslaunch uwb_coop_localization two_car_uwb_simulator.launch
```

另开终端只读检查：

```bash
source /home/wheeltec-client/uwb-coop-localization-ros1/ros_ws/devel/setup.bash
rostopic hz /car1/uwb/ranges /car2/uwb/ranges
rostopic echo -n 1 /car1/uwb/ranges
rostopic echo -n 1 /car1/odom
```

## 可控异常

以下参数全部只作用于模拟器：

```bash
roslaunch uwb_coop_localization two_car_uwb_simulator.launch \
  range_noise_stddev:=0.03 \
  nlos_probability:=0.10 \
  nlos_bias:=0.40 \
  dropout_probability:=0.02 \
  car2_time_offset_s:=0.05
```

- `range_noise_stddev`：零均值白噪声标准差，单位米；
- `nlos_probability`：每次测量进入模拟 NLOS 的概率；
- `nlos_bias`：模拟 NLOS 正偏，单位米；
- `dropout_probability`：发布空 `ranges` 数组的概率；
- `car2_time_offset_s`：Car2 消息时间戳偏移，用于测试离线对齐。

默认 `0.40 m` NLOS 正偏只是接近 EXP002 现象的压力测试参数，不能作为真实硬件的
固定补偿值。模拟消息中的 `quality=0/1` 是场景标签；真实 LinkTrack Frame3 当前没有
厂商定义的归一化质量值。

## 建议的学校预演

1. 默认 LOS 条件录制 60 秒 bag；
2. 加入 50 ms 时间偏移，验证分析程序能发现偏移；
3. 加入 10% NLOS 和 2% 空帧，确认后续节点不会崩溃；
4. 保留原始 bag，不在采集阶段滤波；
5. 真实车辆话题确认后，只修改 launch 映射，不修改消息格式。
