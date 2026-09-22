# UWB rosbag 离线分析

`analyze_uwb_bags.py` 面向 Ubuntu 18.04、ROS Melodic 和 Python 2.7。脚本只读
取 rosbag，不访问串口，也不向 UWB 发送任何命令。原始 `.bag` 文件受
`.gitignore` 保护，不应提交到 Git。

## 时间、目标和缺失值定义

- 只读取 `/uwb/ranges`。
- 目标方向默认为 `tag_id=node_1`、`anchor_id=node_0`，距离单位为米。
- 消息中没有有限的 `node_0` range 时计为 `no_usable_target`；该消息仍保留在
  明细 CSV，并在图中以红色刻线表示。
- `quality` 当前为 NaN，脚本不把它用作有效性或质量指标。
- 横轴和频率使用 bag 接收时间。脚本同时统计 `bag_time-header.stamp`，但已知约
  57,902,871 秒的偏移说明当前不能用 header 时间进行跨数据源对齐。
- 原始距离不滤波、不平滑、不裁剪，也不删除尖峰。
- 跳变定义为**连续两条 ROS 消息均包含可用目标 range**时两者的绝对差。空帧会
  中断序列，绝不把空帧前后的两个有效 range 配成一对。该定义用于复现现有基础
  结果，不应与“相邻有效测量（跳过空帧）”定义混用。
- 标准差使用总体标准差（分母为有效测量数），百分位数使用线性插值。
- `valid_frame_percent` 只表示含可用 `node_0` range 的 ROS 消息比例，不是准确率，
  也不是无线完整收包率；没有发射端真值帧计数，无法计算后者。

## 依赖与运行

```bash
source /opt/ros/melodic/setup.bash
source /path/to/ros_ws/devel/setup.bash

python2 ros_ws/src/uwb_coop_localization/scripts/analyze_uwb_bags.py \
  --output-dir ~/uwb_analysis/EXP001_004 \
  --expectations docs/field_tests/exp001_004_expected.json \
  ~/uwb_bags/EXP001_car1_static_LOS.bag \
  ~/uwb_bags/EXP002_car1_static_human_NLOS.bag \
  ~/uwb_bags/EXP003_car1_manual_push_LOS.bag \
  ~/uwb_bags/EXP004_car1_manual_push_human_NLOS.bag
```

`--expectations` 会先核对四组帧数、空帧数、均值、中位数和标准差。如果任何一项
超出清单允许的舍入误差，进程返回 2，并打印 `BASELINE FAIL`。发生这种情况时，
不得修改正式结论迎合脚本，应检查目标提取、空帧定义、时间字段和统计方法。

依赖包在 ROS Melodic 环境中通常可通过 `rosbag`、`python-numpy` 和
`python-matplotlib` 获得；统计核心本身不依赖 NumPy。

## 输出

每个输入 bag 产生：

- `<bag>.csv`：每条消息的 bag/header 时间、时间差、目标有效性和原始 range；
- `<bag>_summary.txt`：SHA256、元数据与统计摘要；
- `<bag>.png`：以 bag 接收时间为横轴的未滤波原始距离图。

输出目录还包含 `summary.csv`、`summary.json` 和未滤波的
`ranges_comparison.png`，便于四组实验比较和机器读取。
这些衍生文件可以在现场审阅后选择性归档；原始 bag 不进入仓库。

## 当前复现状态

仓库不包含四份原始 bag，云端环境因而不能独立执行最终数据复现。已知基线被
原样固化在 `exp001_004_expected.json`，且统计、目标提取和 NaN 处理有独立单元
测试。正式接受新图表前，必须在保存 bag 的现场机器运行上述带
`--expectations` 的命令并看到：

```text
Baseline verification passed for all supplied experiments
```

四份现场文件的 SHA256 已于 2026-09-22 由用户在保存原文件的虚拟机上计算并写入
对应实验报告；正式分析仍会再次计算哈希，用于确认分析输入与记录文件一致。
