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

## 目标虚拟机验收记录（2026-09-24）

Ubuntu 18.04、ROS Melodic、Python 2.7.17目标虚拟机完成了24项单元测试和catkin
构建，并用此前保存的两份仿真bag执行本工具。原始bag未提交Git。

### Smoke bag

- 文件：`two_car_smoke_20260923.bag`；
- SHA256：`ce95db786a253d981030ce236c96f73433ef1fc4bd82c9f2d9546c0bba38c39a`；
- 227对消息，Car1/Car2配对覆盖率为99.56%/100%，双侧测距全部有效；
- bag接收时间差均值0.149 ms，消息头时间差为0；
- Car1/Car2真值RMSE为0.0313/0.0292 m，双向均值真值RMSE为0.0213 m；
- 双向绝对差均值0.0332 m，P95为0.0885 m。

### Stress bag

- 文件：`two_car_stress_20260923.bag`；
- SHA256：`f831de9fadd826e8d69a9c9633b86ca7e34d5e64f491d0b040a32dbbd6c2522e`；
- 290对消息，仅Car1存在1个录包边界未配对帧；
- bag接收时间差均值0.076 ms，Car2消息头时间差稳定为49.99995 ms；
- 双侧同时有效率61.38%，符合两侧独立20%丢测下的有限样本表现；
- Car1/Car2真值bias为+0.0827/+0.0824 m，RMSE为0.1814/0.1834 m；
- 双向均值真值RMSE为0.1356 m，双向绝对差均值0.1527 m、P95为0.4407 m；
- 图像人工检查确认：测距跟随真值，NLOS出现约+0.4 m尖峰，丢测形成断口，
  消息头时间差保持50 ms。

这些结果验证的是分析工具对已知仿真异常的检测能力，不替代EXP005--008真实双车
硬件验收，也不能把仿真NLOS参数当作真实硬件补偿值。
