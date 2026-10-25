# A端：Codex沙盒的bag与离线解算任务书

先完成[入口页](README.md)的只读Git检查、新检出、固定`HANDOFF_COMMIT`和独立Python环境。再读[manifest.json](manifest.json)、[geometry.json](geometry.json)、[EXPERIMENTS.md](EXPERIMENTS.md)、[QC_REPORT.md](QC_REPORT.md)和[输出契约](RESULT_CONTRACT.md)。本页中的“后续实现”不是已经存在的可执行程序。

## 任务边界

可以修改`tools/field_20261024_25/`内bag/标准化/估计相关代码及对应测试，以及新建的本端紧凑报告。不要改视觉参考数值、公共`manifest.json`/`geometry.json`或其他端文件；需要修正时向协调端提交证据与建议diff。只读原始数据，不把bag/原视频/大CSV提交Git。

推荐分支：`analysis/field-bag-20261026-<工作标识>`。任务开始时从协调端固定的提交分支，不继承历史实验分支的未审查参数。

```bash
git switch -c "analysis/field-bag-20261026-$(date +%H%M%S)"
DATA_ROOT="$HOME/uwb-field-data/20261024_25"
OUTPUT_ROOT="$HOME/uwb-field-results/bag/$(date +%Y%m%d_%H%M%S)"
PYTHON="$HOME/.venvs/uwb-field-offline-bag/bin/python"
mkdir -p "$OUTPUT_ROOT"
git rev-parse HEAD > "$OUTPUT_ROOT/code_commit.txt"
git status --porcelain=v1 > "$OUTPUT_ROOT/worktree_at_start.txt"
sha256sum docs/field_tests/20261024_25/manifest.json docs/field_tests/20261024_25/geometry.json > "$OUTPUT_ROOT/config_sha256.txt"
"$PYTHON" -m pip freeze > "$OUTPUT_ROOT/python_packages.txt"
```

## A1：取得相同输入并复现已完成的验收

```bash
"$PYTHON" tools/field_20261024_25/prepare.py --data-root "$DATA_ROOT" --assets bags --extract
"$PYTHON" -m unittest discover -s tools/field_20261024_25 -p 'test_audit_bags.py' -v
"$PYTHON" tools/field_20261024_25/audit_bags.py --data-root "$DATA_ROOT" --output "$OUTPUT_ROOT/bag_qc"
```

已缓存完整附件时，在第一条加`--offline`。输出为`bag_qc/bag_qc.json`及`bag_qc/BAG_QC_REPORT.md`。输出目录非空默认拒绝；换新的运行目录，不为省事覆盖原结果。保留失败时的日志和输入身份。

验收标准：

- 正式八包路径与SHA256匹配，成功T10明确使用`184755 retry`，失败`184047`不能替代。
- 消息数量及完整schema解码复现已提交结果，总数311,144；不同则报告具体包/字段，不能修改期望值来过关。
- 原始Frame3校验和、raw/ranges同header配对、时间序列、空帧与有限正测距、预期cmd_vel/odom均有结果。
- 报告包含向每个peer的条目可用率，不能以总话题50Hz替代链路可用性。
- 接收时刻、ROS header和设备时间分开保留；接收间隔0.642s与连续设备时间不是已证实无线掉包。

## A2：新增标准化观测导出与时间诊断

这一阶段需要在本分支实现和测试，不要假设仓库已有名为`export_field_data.py`之类的命令。交付后在本页追加真实CLI和验证结果。

按[输出契约](RESULT_CONTRACT.md)导出以下文件到`OUTPUT_ROOT/normalized/`：

- `ranges.csv`：每个有向距离条目一行，保留raw/bridge来源、bag接收ns、header ns、设备时间和RSSI可用性；不要把同一raw与bridge当两次独立量测叠加。
- `odom.csv`、`imu.csv`、`commands.csv`：保留两个车体各自frame及源时间，不预先伪造room对齐。
- `time_diagnostics.json`：每车/话题的相邻时间间隔、负receive-header分布、重置/回绕/时钟不确定项、可用的时间映射方案。
- `normalization_report.md`：单位转换、Car2 odom.z处理、丢弃/标记规则、每表计数与来源核对。

必须验证读入/导出条目数、原始记录可追溯性、无符号/有符号设备时间解释、缺测/NaN保留、跨时钟不误减。不可未经识别就减去某个固定“网络延迟”。JSON无效数用`null`加原因，CSV缺失保持空值；不能写成0m或质量0。

## A3：视觉参考等待期间可做的工作

可并行做不依赖独立定位误差的事情：链路覆盖、距离分布/跳变、方向不对称、RSSI可用性、时间/到达批量性、原始桥接一致性，以及估计器接口、仿真/合成输入测试。

T14/T15的遮挡实际材料/位置/时段尚未确认。只描述“该条件下的测距现象”，不事先贴全部NLOS标签，也不以结果强弱选择保留哪包。合成偏差/缺测必须标作离线注入，不冒充新增现场实验。

## A4：满足参考门槛后再正式解算

协调端批准B端的空间/时间参考范围后，固定共同输入与参数，按同一观测/相同评价窗口运行：

1. Odom-only基线。
2. 每车独立UWB/Odom基线。
3. 固定车间测距因子的双车联合基线。
4. 有数据证据的候选可靠性机制及必要消融，最后才确定文章方法名称。

不要把历史固定滞后、全历史图优化或完整性监测工具直接默认等同于本轮正式基线；先核对因果性、初始化、frame、外参、时钟、可用锚点与参数版本。旧工具可复用经过审查的部分，但需单独记录变更。

开发包为T08/T10/T12/T14；整包留出为T09/T11/T13/T15。只可在开发包决定阈值和模型；最终留出评价一次性按冻结配置运行。已看过文件健康统计不等于定位结果仍全盲，报告应如实说明。不能使用真实终点因子、对每包独立终点拟合、Odom当真值或测试集误差调参制造改进。

若B端只通过停点/终点参考，就只评价这些独立点及测距诊断；不得写连续轨迹RMSE。每个运行保存`run.json`、`estimate.csv`、`diagnostics.json`和短报告，格式见契约。

## 连续夜间工作

需要有限预算、可恢复的离线批处理时，先读[NIGHTLY_SANDBOX.md](NIGHTLY_SANDBOX.md)：

```bash
"$PYTHON" tools/field_20261024_25/run_nightly.py --data-root "$DATA_ROOT" --output "$OUTPUT_ROOT/nightly" --max-hours 6 --plan-only
"$PYTHON" tools/field_20261024_25/run_nightly.py --data-root "$DATA_ROOT" --output "$OUTPUT_ROOT/nightly" --max-hours 6
```

首次运行不加`--resume`。只有同一路径已产生run.json、任务被中断且源码/配置指纹未变化时，才按夜间指南加`--resume`恢复；恢复保留原始截止时间，不是重新获得六小时。

该runner只执行其明列的已实现任务，不自动创造未实现的视觉/融合算法。长任务必须留下检查点、成功/失败/阻塞清单；达到预算或遇到输入/科学依赖阻塞时停止并报告。窗口关闭后能否继续取决于实际执行环境，不承诺聊天窗口天然后台运行。

## 回报与PR

给协调端的顺序为：`run.json`/来源版本 → A1验收摘要 → 标准化/时间报告 → 实现变更与测试 → 若已获批准，再给基线结果。PR只包含本端代码、测试、紧凑指标及复现说明；列出未解决项。不要自行合并PR、改公共配置或启动现场车辆。
