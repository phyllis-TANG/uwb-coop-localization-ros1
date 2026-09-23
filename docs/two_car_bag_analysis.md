# 双车 UWB rosbag 离线评估

`analyze_two_car_bag.py` 用于比较两辆车记录的互测 UWB。脚本只读 rosbag，不打开
串口、不发送命令、不修改设备配置；原始 bag 不提交 Git。

## 统计口径

- Car1 默认为 `node_0 -> node_1`，Car2 默认为 `node_1 -> node_0`；
- 使用 **bag 接收时间**进行一对一最近邻配对，默认最大差值为 30 ms；
- `header.stamp` 不参与配对，也不自动修正，只报告
  `Car2 header - Car1 header`，便于发现跨计算机时间差；
- 空 `ranges` 消息仍参与时间配对，并分别统计“两侧有效、仅Car1有效、仅Car2有效、
  两侧均无效”；
- 不滤波、不平滑、不删除尖峰；
- 双向差定义为 `Car2 range - Car1 range`，同时报告绝对差；
- 真值可以来自仿真话题，也可以是EXP005卷尺测得的固定天线参考点距离；
- 不自动使用两车odom计算真值，因为两个独立odom通常没有共同原点和朝向。

## 仿真bag

```bash
source /opt/ros/melodic/setup.bash
source ros_ws/devel/setup.bash

python2 ros_ws/src/uwb_coop_localization/scripts/analyze_two_car_bag.py \
  ~/uwb_simulation_tests/two_car_stress_20260923.bag \
  --output-dir ~/uwb_simulation_tests/two_car_stress_paired_analysis \
  --truth-topic /simulation/inter_car_range_truth
```

50 ms的Car2消息头偏移应出现在 `header_time_delta_*_s`，而bag时间配对差应继续接近
本机发布/录包调度延迟。两者不能混为同一个时钟指标。

## EXP005卷尺真值

例如天线参考点实测为2.000 m：

```bash
python2 ros_ws/src/uwb_coop_localization/scripts/analyze_two_car_bag.py \
  ~/uwb_bags/EXP005_two_car_static_LOS_2m.bag \
  --output-dir ~/uwb_analysis/EXP005_2m \
  --truth-distance-m 2.000
```

如果两车分别本地录包：

```bash
python2 ros_ws/src/uwb_coop_localization/scripts/analyze_two_car_bag.py \
  ~/uwb_bags/EXP005_2m_car1.bag \
  --car2-bag ~/uwb_bags/EXP005_2m_car2.bag \
  --output-dir ~/uwb_analysis/EXP005_2m \
  --truth-distance-m 2.000
```

若提示没有消息能在30 ms内配对，应先检查两机时钟证据，不能仅为得到输出而任意
增大容差或覆盖系统时间。确有已记录的时间差时，再显式设计离线修正步骤。

## 输出

- `paired_measurements.csv`：逐对时间、有效性、双向距离、真值与误差；
- `summary.json`：机器可读元数据与统计；
- `summary.txt`：便于现场快速检查的同一统计；
- `two_car_comparison.png`：双向距离、双向绝对差和消息头时间差。

原始bag的SHA256写入摘要。卷尺真值必须测量两块UWB天线的统一参考点，不能用车壳、
保险杠或车轮之间的距离代替。
