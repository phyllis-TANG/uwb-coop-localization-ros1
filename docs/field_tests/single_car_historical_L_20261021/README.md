# 三个历史 L 型包复跑（2026-10-21）

本轮固定复跑 10.11 手动 083512、10.11 自动 091958 和 10.17 自动 061540，保留各自安装时期的锚点坐标、静态 P1 标定、起点/朝向记录及原评价窗口。

`REPORT.md` 给出结论；`protocol.json` 是计算前冻结的方案；`analyze_historical.py` 是实际运行代码；`verify_results.py` 独立重建 CSV 数值；`build_report.py` 仅从已有结果计算派生统计、绘图和整理报告。

## 方法

| 名称 | 含义 |
|---|---|
| A | 历史起点/朝向对齐的 Odom；其初始位置由构造固定，不是独立验证 |
| U_raw / U_P1 | 同一批关键帧和测距中位数上的纯 UWB，分别不校正/按该场次 P1 校正；固定高度、同一鲁棒损失和三组固定初值 |
| G_raw | 新版求解器，零偏置、零水平杆臂 |
| G_old / G_new0 | 旧/新版求解器，相同历史冻结偏置与零杆臂，检查代码等价性 |
| G_P1 | 新版求解器，重新核对的全精度 P1 偏置，保留历史零水平杆臂近似 |
| G_assumedL | 新版求解器，全精度 P1，使用相对几何中心测得的 `[0.12,-0.08] m`；用户确认安装一直未变，剩余条件是几何中心等于 Odom 车体参考点，尚未核实 |

所有图的权重、鲁棒损失、初值规则和求解预算保持冻结方案。没有新增屏蔽 N10、Odom 门限或参数搜索。新旧代码零杆臂对照完全相同；P1 全精度重算仅改变历史舍入小数，不是新标定方法。

## 输入和复现

需要 Python 3、NumPy、SciPy，以及用于读取 ROS1 bag 的 rosbags（或可用的原生 rosbag）。以下命令假设仓库根目录包含已合并 PR31–33 的文件。本轮本地计算对应 main `ba16d58a08148531db136c4a96e289161dc9f1c4`。

```bash
python /path/to/historical_L_validation_20261021/analyze_historical.py \
  --repo-dir /absolute/path/uwb-coop-localization-ros1 \
  --oct11-data /absolute/path/uwb_field_tests/20261011 \
  --oct17-archive /absolute/path/uwb_20261017_field_session.tar.gz \
  --output /absolute/path/new_analysis/results
```

输出目录及相邻 `scratch_inputs` 目录必须不存在。只从已知归档成员提取 10.17 的 L 包与静态 P1 包到 `scratch_inputs`，不会覆盖输入或解包整个归档。`scratch_inputs` 是可重建的原始输入副本，不作为报告附件或普通文件 PR 的提交内容。

源码路径若与主仓库布局不同，可用 `--new-solver`、`--uwb-helper` 指定本轮归档的对应源码；`--rosbags-path` 可指定现有依赖目录。本轮输出 `results/evidence/` 保存实际用到的新旧求解器、UWB 求解辅助、两个场次配置和三个旧摘要，供核查源代码哈希。

独立复核及报告生成默认使用本目录 `results/`：

```bash
python /path/to/historical_L_validation_20261021/verify_results.py
python /path/to/historical_L_validation_20261021/build_report.py \
  --html-output /absolute/path/UWB_historical_L_validation_20261021.html
```

## 评价边界

主评价沿用旧归档的初始窗口与录包末尾五秒；补充评价统一采用最后运动停止后 `[2,7)`。两个窗口都保留，不按结果选择。各方法都对同一批关键帧的天线 X/Y 取中位数。旧报告的纯 UWB 用整窗距离中位数再做普通 LS，本轮逐关键帧鲁棒求解，因此不把二者混为同一项。

只有标记起点、人工终点和近似初始朝向；没有连续位置真值、独立物理转角或相对 Odom 车体参考点的已核实水平外参。这三个包以前已分析过，属于回顾性开发对照。单车图均为离线批处理，IMU 没有作为独立因子加入。

计算后用户确认天线在车上的位置始终未变，具体见 `MOUNT_USER_CONFIRMATION_20261021.md`。报告已据此更新：未知项收敛为几何中心与 Odom 车体参考点的关系；冻结计算方案和数值结果保留。

完整原始求解输出保留在 `results/`。派生的起终点位移统计、按链路/窗口拟合残差和已知参考点的测距残差由报告生成器计算，并记录在 `derived_verification.json`。`SHA256SUMS.txt` 不包含自身与最后生成的 `report_verification.json`，避免循环引用。
