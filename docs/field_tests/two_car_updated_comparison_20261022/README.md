# 新版双车离线对照（2026-10-22）

本轮检查：迁移当前单车因子模型后，加入车间测距对 Car1、Car2 分别产生什么影响，影响是否随本车墙节点观测可用性而变化。使用已有双车包，保持数据、权重、初始化和评价协议可追溯。

冻结设置见 [protocol.json](protocol.json)，结果见 [results/REPORT.md](results/REPORT.md)，研究判断见 [results/INTERPRETATION.md](results/INTERPRETATION.md)，全部配置和数值记录见 [results/summary.json](results/summary.json)。这是读取整包后的批量离线估计；双车顺序回放、联合固定窗口和 ROS 实时接口尚未在本轮实现。

## 输入与校正来源

- `015334`：Car1 静止、Car2 自动 L 形，人工终点来自原始 notes。
- `033248`：Car2 静止、Car1 对齐后直行，人工终点与直接卷尺距离分开评价。
- `050447`：双车同动正常重录，作为扩展开发样本；不借用首次同动包的备注。
- Car1 墙节点修正从独立静态包 `013206` 估计：每个节点的全包原始有效测距中位数减去三维几何距离。Car1 天线 `[3,3,0.17] m` 来自[用户确认 P04](../../../datasets/field_raw/provenance/user_confirmations_20261020.md)。这是本轮新增的、指定场次和位置下的暂定修正。
- Car2 保留已合并单车模型的 10.17 P1 修正，使用完整精度数值，不改为双车包的拟合值，也不把它套用到 Car1。
- `013951`、`015009`、`020151` 只检查静态迁移与车间参考差。后者共享 L 结束后的摆放，未重新量卷尺，不能称为一次新的独立测量。
- 车间测距不拟合常数修正；已知参考差会随位置/方向改变。人工终点、卷尺距离不传入优化目标，也不用于挑选权重或剔除链路。

所有 bag 先核对 SHA-256。原始数据和原始备注不改写。Car1 高度采用同日安装调查的 0.17 m，原 notes 中的 0.20 m 保留为原始记录。

## 共享模型与配对对照

每辆车复用已合并的单车 `Objective`：世界系车体 XY/yaw 状态、起点/朝向先验、车体系 Odom 增量、旋转的水平天线外参、固定天线高度及仅用于测距的有符号 pseudo-Huber 残差。独立 IMU 因子数量为零。

每个配置只生成一次共享输入，两种方法使用相同的模型、Odom、墙测距、校正、先验和 Odom 初值。联合方法额外加入车间因子：分别求两个方向的统计窗中位数，将可用方向平均为**一个**距离观测；每时刻最多一个因子，不将两个方向当成两条独立约束，也不因平均而缩小 0.2 m 的尺度。

两个单车目标的解析导数拼成块结构，车间因子包含两车天线外参对 yaw 的导数。使用 SciPy TRF、解析 Jacobian、稠密精确线性求解、最多 100 次残差评价，终止容差都是 `1e-7`。各自/联合采用相同设置。未成功收敛的结果报错，不作为有效定位输出。

旧双车模型的 XY 起点先验写在天线位置；当前单车模型写在由外部起点与初始朝向换算得到的车体位置。本轮沿用后者。因此旧版与新版的横向比较同时包含先验定义和数值求解器变化；新版每一配置内部的“各自/联合”对照只差车间因子。原版脚本保持原样，先重跑原始测距和仅 Car2 P1 修正两组，验证归档结果可复现。测试还用捕获的原版残差检查兼容先验下的数学一致性。

## 时间关联

延续旧双车离线基线，使用同一 bag 的记录接收时间轴，不把两车未同步的消息头当成统一时钟。使用整数秒状态 `1…floor(duration)-1`，墙测距和车间测距统计半窗 0.4 s，每链路至少 5 个有效样本；Odom 按接收时间插值，两端必须存在，禁止外推。

读取时保留消息头差异、frame、数据数量和重复 ID 诊断。双向观测接收时间接近不能证明同时采集；固定窗中位数也不能消除时钟偏移。两个旧场景另外核对新旧前端的时刻、插值 Odom、墙测距中位数和车间中位数一致。

## 预先指定的八种配置

| 配置 | 墙测距修正 | 车间尺度 | 目的 |
|---|---|---|---|
| raw_walls | 两车均不修正 | 0.2 m | 原始观测对照 |
| car2_p1_only | 仅 Car2 P1 | 0.2 m | 与已有单车改进的连接点 |
| per_car_walls | Car1 独立静态包＋Car2 P1 | 0.2 m | 主对照 |
| peer_sigma_0p4 | 同主对照 | 0.4 m | 降低车间约束权重的敏感性检查 |
| withhold_car1_walls | 同主对照，移除 Car1 全部墙因子 | 0.2 m | 合成墙测距缺失 |
| withhold_car2_walls | 同主对照，移除 Car2 全部墙因子 | 0.2 m | 合成墙测距缺失 |
| peer_car2_minus_0p1s | 同主对照 | 0.2 m | Car2 车间测距统计窗关联 −0.1 s |
| peer_car2_plus_0p1s | 同主对照 | 0.2 m | Car2 车间测距统计窗关联 ＋0.1 s |

所有配置运行各自/联合两种方法，完整保留正负结果，不在结果中选出最好的一组替代主对照。移除墙因子是人工合成缺测，不是实录 NLOS。时间敏感性只移动 Car2 车间观测的统计窗关联，不代表已完成全流时钟校准。独立方法在墙/Odom/先验完全相同的配置间复用同一解，并显式记录复用来源，避免把重复计算当成独立实验。

## 评价与解释边界

主指标是每辆车最后五个状态的天线 XY 中位数与人工终点之差，沿用旧双车评价窗。另存这五个时刻的 Odom 平移/航向变化，核对停止支持；`last_five_odom_stationary` 是严格数值常值检查（位移小于 1e-6 m、角度小于 1e-4°），不是实际运动判定。报告“联合终点差减各自终点差”，负数表示更接近人工终点。没有连续真值，不报告 ATE 或全程轨迹 RMSE。

静止车辆仍按相同 Odom 因子估计，不额外锁定位置。其估计轨迹长度、净位移和起点先验位移用于暴露模型不一致；不能把这些优化轨迹直接当成实际运动。分别记录每节点墙残差、两车 Odom 一致性、起点修正和因子代价账本。车间拟合残差下降只说明对已加入观测的拟合更好，不能据此证明精度改善。

人工坐标推算距离与直接卷尺值可能不一致，特别是 `033248`。二者分别保留；静态采样离散度不包含人工参考和空间迁移误差。参考点与几何中心是否一致、初始角度是否准确仍待现场核实。全部数据均属历史开发数据，不宣称盲测或论文级验收。

## 运行与输出

在仓库根目录、Python 3.12 环境中：

```bash
python -m pip install -r tools/requirements-single-car-replay.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest discover -s tools -p 'test_two_car*.py' -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run_two_car_updated_comparison.py \
  --archive /path/to/field_tests_20261018.tar.gz --output dual-comparison-results
python tools/plot_two_car_updated_comparison.py dual-comparison-results
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/analyze_two_car_comparison_results.py dual-comparison-results
```

协议中的原始 bag 应位于仓库对应路径。归档压缩包仅供原版脚本复现，校验原 SHA-256；新模型直接读 dataset 中的 bag。`--dependency-path` 可指定额外 rosbags 安装目录，在导入 NumPy/SciPy 后追加。输出目录必须不存在。此程序不启动 ROS、不访问串口、不下发运动命令。

- `comparison.csv` / `summary.json`：全部配置的分车指标和配对变化。
- `trajectories.csv`：每个配置、方法和车辆的完整离线状态及天线轨迹。
- 各包的 `*_inputs.json`：实际输入，包含校正、支持样本及双向聚合记录；`*_comparison.json` 保存评价和输入指纹。
- `calibration.json`、`static_wall_transfer.csv`、`static_peer_reference_checks.csv`：独立校正来源、迁移检查和未经拟合的车间参考差。
- `legacy_reproduction.json`：旧模型复现；`input_manifest.json`：数据、源代码、协议哈希及实际环境，检查运行期间源代码和协议未变。
- `wall_reference_diagnostics.csv` / `peer_reference_diagnostics.csv`：仅在求解后，用起终点参考检查窗口测距；不反向供给优化器。
- `DERIVED_VERIFICATION.json`：输入指纹、因子数量、轨迹 CSV 与汇总终点一致性及实际求解/复用次数；`peer_time_association_sensitivity.json` 保存时间扰动引起的全程估计变化。

本轮用于决定双车下一步最该处理的误差来源。顺序回放和联合窗口应在配对对照可解释后推进，单车 20 秒窗口的相关边界先验不能直接拆成两车互不相关的先验。
