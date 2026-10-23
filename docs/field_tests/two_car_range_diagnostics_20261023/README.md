# 七包测距诊断与留一链路历史降权（2026-10-23）

本轮执行“定位异常测距时段”和“增加一种有依据的可信度策略”两步。基于已合并 PR #39，main 为 `e9df6104d710b01b08282c168e2191d355a37fa2`。原模型、默认参数、旧结果与原始 bag 均未修改。

主要结果：约 92.5 cm 的 Car2/node_10 中位数差位于两次录制之间，各包内部中位数稳定；现有包未记录切换时刻。新策略能发现持续不一致，但其终点结果大多接近原模型，最大变化约 0.41 cm，尚未证实定位收益。预测端被其他坏测距污染后，也会对较正常的车间测距降权。方法保留为研究对照。

完整结果、触发时段、失败案例和三张图见 [results/REPORT.md](results/REPORT.md)。

## 两步如何执行

1. **原始诊断：** 对四个静态包和三个动态包统计每秒 ±0.4 s 测距分布、双向车间测距差、header/receipt 关联、ID、质量字段与原始 Odom。已核对读取结果与旧前端逐值一致。静态人工坐标只用于诊断参考偏差；未改写坐标。
2. **一种新策略：** 对每个待检墙测距，用只读取 Odom 和其余墙测距的预测器形成检验量；车间预测不使用任何车间测距。当前权重由前三个关键帧的检验量决定，所有权重在批量图求解前固定。原模型、固定尺度、新策略三组分别与近零运动约束开/关交叉，共六配置。各自/联合对照仅差车间因子。

诊断计划先保存；策略数值规则在新动态拟合前冻结。初版协议在任何预测/拟合前补充了一处文字澄清：静态诊断可以用静态坐标作外部起点先验，但不加入持续位置约束。修订未改变数值规则，原协议哈希保存在最终协议中。

静态诊断采用暂定 0° 起始朝向，不作为独立定位精度验证。预测器是诊断工具，其近似协方差没有做统计校准；新图结果仍来自原 SE(2) 批量模型，不是 EKF 输出。

## 复现

依赖使用 `tools/requirements-single-car-replay.txt`，按父协议准备七个未修改 bag。各工具校验 SHA256。下面从仓库根目录执行；两个输出目录必须不存在：

```bash
mkdir -p /tmp/two_car_range_diagnostics
cp docs/field_tests/two_car_range_diagnostics_20261023/diagnostic_plan.json docs/field_tests/two_car_range_diagnostics_20261023/protocol.json /tmp/two_car_range_diagnostics/
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest discover -s tools -p 'test_two_car*.py' -v
python tools/diagnose_two_car_ranges.py --output /tmp/two_car_range_diagnostics/diagnostics
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run_two_car_range_confidence.py --output /tmp/two_car_range_diagnostics/results
python tools/plot_two_car_range_confidence.py /tmp/two_car_range_diagnostics
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/analyze_two_car_range_confidence.py /tmp/two_car_range_diagnostics
```

已有独立 rosbags 安装目录时，诊断、运行与分析工具均支持 `--dependency-path`；NumPy/SciPy 在追加该路径前加载。

分析工具会复现一次仅在预测端移除 Car2/node_10 的反事实诊断；它不改变冻结权重或任何新图结果。所有数值规则和输入路径见 [protocol.json](protocol.json)。

## 验证及适用范围

32 项相关测试通过：包括被检链路不进入自身预测、车间预测不读取车间测距、未来/当前样本隔离、非零外参 Jacobian、时变尺度 Jacobian、单位权重复现、协方差正定、缺测和失败求解处理。36 次实际图求解全部接受，旧四组配置逐点复现差为 0。6,168 行轨迹与全部历史权重均独立重算核对，差为 0。

所有包是已知开发数据；未用动态终点调阈值，未声明盲测或连续轨迹精度。触发时段不是 NLOS 标签，较大的不一致分数也不能确定错误来自被检测距。静态记录之外的摆位、朝向、遮挡、设备状态仍缺独立记录。

权重在关键帧序列上只取过去分数，但前端继承居中测距窗和带括号的 Odom 插值；本轮仍是全包离线平滑，没有验证端到端在线因果性、双车固定窗口或新增 IMU 因子。
