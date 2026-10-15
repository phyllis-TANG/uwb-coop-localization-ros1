# 离线复现与归档说明

所有分析命令仅读取 bag 和文件，不启动 ROS 节点、连接串口或发布控制指令。
Car2 运动脚本单独保存在原始脚本目录，具有不同运行环境和用途。

## 1. 输入与目录

原始备份 `field_tests_and_scripts.tar.gz` 应保留独立副本及压缩包 SHA256。
本次校验为 `09d2c71c07fe5f29c5c962ed2f9d61b7d7fd3cfc62099f8fc805895a3037f19a`。

恢复到原 VM 时，先确认目标文件是否存在，使用独立恢复目录检查，避免覆盖原始数据。
新分析需要以下结构；抬高静态报告也来自备份，不仅需要 bag：

```text
uwb_field_tests/
  20261010/
    *.bag
    ...
  20261011/
    *.bag
    P1_raised_xy_analysis/
    multipoint_xy_analysis/
    multipoint_xy_analysis_P5_corrected/
    ...
```

28 份 bag 的归档清单使用相对于 `uwb_field_tests/` 的路径：

```bash
cd /home/wheeltec-client/uwb_field_tests
sha256sum -c \
  /home/wheeltec-client/uwb-coop-localization-ros1/docs/field_tests/20261010_11/results/SHA256SUMS.txt
```

## 2. 新二维分析：VM 原生 ROS1 路线

程序沿用 Python 2.7 兼容语法和 SciPy 0.19 可用的稀疏最小二乘接口。
2026-10-15 已在目标 Melodic VM 使用 Python 2 实跑自测、七项单元测试、28 份原始 bag 回放及分段诊断，全部通过。
下列命令可用于再次回放，不需要 ROS Master 或小车在线：

```bash
cd /home/wheeltec-client/uwb-coop-localization-ros1
source /opt/ros/melodic/setup.bash
source ros_ws/devel/setup.bash

python2 tools/analyze_october_field_session.py --self-test
python2 -m unittest discover -s tools -p 'test_october_field_session.py'

python2 tools/analyze_october_field_session.py \
  --data-root /home/wheeltec-client/uwb_field_tests \
  --config docs/field_tests/20261010_11/session_config.json \
  --output-dir /home/wheeltec-client/uwb_analysis/october_session_reproduced
```

输出目录包含完整 manifest、静态校准复核、两个二维结果、关键帧轨迹 CSV、静态/遮挡摘要及图。
派生输出可重新生成；使用新输出目录以保留现场历史结果。

## 3. 新二维分析：现代 Python 路线

本次实际环境：Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0、Matplotlib 3.10.8、rosbags 0.11.7。
该路线无需安装 ROS，`rosbags` 从 bag 自带消息定义读取自定义 UwbRangeArray。
可在独立 Python 3.12 虚拟环境安装复现依赖：

```bash
python3.12 -m venv /tmp/uwb-offline-env
. /tmp/uwb-offline-env/bin/activate
python -m pip install -r tools/requirements-october-modern.txt

python tools/analyze_october_field_session.py --self-test
python -m unittest discover -s tools -p 'test_october_field_session.py'

python tools/analyze_october_field_session.py \
  --data-root /path/to/uwb_field_tests \
  --config docs/field_tests/20261010_11/session_config.json \
  --output-dir /path/to/new_analysis_output
```

分析配置固定采样窗口、权重、坐标及校准来源，实际终点仅供评价。
历史一维脚本使用录包时间；新二维使用 Car2 消息时间。跨方法比较必须保留这一差异。
这些环境没有与 VM 共用 catkin 输出，勿把现代 Python 安装路线混入现有 Melodic 系统环境。

## 4. 分段诊断

完成主分析后，以相同配置和关键帧结果运行：

```bash
python2 tools/diagnose_october_L_segments.py \
  --data-root /home/wheeltec-client/uwb_field_tests \
  --config docs/field_tests/20261010_11/session_config.json \
  --base-results /home/wheeltec-client/uwb_analysis/october_session_reproduced \
  --output-dir /home/wheeltec-client/uwb_analysis/october_segments_reproduced
```

现代环境把 `python2` 换为该环境的 `python`，并使用对应数据路径。
输出分段时间、人工起终点处链路残差、尾段截断的全部结果，以及 N8 可见性时间表。
诊断图中的“测距减 Odom 几何”属于估计间一致性，不能当作轨迹真值误差。

## 5. 四个原始脚本

位置：`tools/field_session_20261010_11/`。四个文件与用户备份字节完全一致，校验见 `results/source_scripts.json`。

| 文件 | 用途与环境 |
|---|---|
| `wall_uwb_xy_pilot.py` | 原始固定高度无权 UWB-only XY；Python 2.7 + ROS Melodic |
| `uwb_odom_1d_pilot.py` | 原始一维递推融合；Python 2.7 + ROS Melodic |
| `uwb_odom_1d_factor.py` | 原始一维因子图；Python 2.7 + ROS Melodic + SciPy |
| `car2_relative_motion.py` | 已现场试用的相对运动控制；Car2 Python 3 + ROS Noetic；默认 dry-run，`--execute` 才运动 |

一维重放示例（创建新输出目录）：

```bash
mkdir -p /home/wheeltec-client/uwb_analysis/october_1d_reproduced

python2 tools/field_session_20261010_11/uwb_odom_1d_pilot.py \
  /home/wheeltec-client/uwb_field_tests/20261011/CAR2_WALL_UWB_ODOM_IMU_key_forward_repeat_20261011_051810.bag \
  1.010 /home/wheeltec-client/uwb_analysis/october_1d_reproduced/filter_forward2.csv

python2 tools/field_session_20261010_11/uwb_odom_1d_factor.py \
  /home/wheeltec-client/uwb_field_tests/20261011/CAR2_WALL_UWB_ODOM_IMU_key_forward_repeat_20261011_051810.bag \
  1.010 /home/wheeltec-client/uwb_analysis/october_1d_reproduced/graph_forward2.csv
```

其他两份原始输入、参考长度及截断定义见报告与保留的六份 `*_summary.txt`。
现场原脚本写 CSV 使用 Python 2 二进制模式，不能直接当作现代 Python 3 脚本运行。
现代离线复现应使用配套 `tools/replay_october_1d.py` 适配器；它保留原脚本字节，只适配 bag 读取和 CSV 文本模式。

```bash
python tools/replay_october_1d.py \
  --data-root /path/to/uwb_field_tests \
  --output-dir /path/to/new_1d_replay
```

## 6. 已运行检查与剩余验收

- 28 份 bag 共 126,830 条消息全部完成离线读取，11 份已知原始校验值一致。
- 独立静态校正量复算差异均小于 0.001 m，未对两份 L 形重新校准。
- 六份一维历史摘要的位移和绝对差复现到三位小数。
- 二维合成 L 形、任意 Odom 坐标原点/旋转、朝向跨界、测距离群值、退化几何、倒车首段对齐等测试通过。
- 仓库原有 28 个硬件无关测试及新增 7 个测试在现代 Python 环境通过；新增检查包括起点静止窗口和倒车分段。
- 2026-10-15 目标 ROS Melodic VM 上，Python 2 自测通过，新增七项单元测试通过；实际回放审计了 28 份 bag，所有已配置 SHA256 和校准检查通过。
- VM 端键盘 L 形的原始 UWB / 图优化 / 对齐 Odom / 校正 UWB 终点差依次为 0.6142 / 0.2255 / 0.1265 / 0.2173 m；自动 L 形依次为 0.6711 / 0.0540 / 0.0709 / 0.0562 m，与归档表的四位小数一致。
- VM 端分段诊断的键盘起点窗口为 [0.168488, 3.877939] s，自动起点窗口为 [0.152192, 5.152192] s；10 s / 30 s / 全段终点差分别为键盘 0.2031 / 0.2364 / 0.2255 m、自动 0.0444 / 0.0473 / 0.0540 m。
- 新程序属于独立离线工具，尚未进行本次目标 VM catkin 构建；本次验收没有硬件连接或控制器实车复测。

## 7. Git 归档边界

提交：分析代码、四个原始脚本、启动指南、配置、bag SHA256、现场文本备注、紧凑关键帧 CSV、摘要和精选 PNG。
原始 `.bag`、压缩备份、逐帧原始距离 CSV、`.pyc`、catkin 生成目录继续保存在数据存储中。
本次没有把四个现场脚本加入 catkin 自动安装/启动流程，避免混淆 Python 2 分析脚本与 Python 3 实车控制脚本。
