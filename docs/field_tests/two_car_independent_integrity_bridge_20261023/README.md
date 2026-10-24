# 双车数据上的独立单车因果定位与完好性监测衔接试验

正式交付：[一页中文结论](results/CONCLUSION_ZH.md)、[逐阶段解释](results/INTERPRETATION_ZH.md)、[完整报告与三张两车诊断图](results/REPORT.md)。

实际仓库 `/home/ubuntu22/双车协同/uwb-coop-localization-ros1`，分支 `experiment/two-car-independent-integrity-bridge-20261023`。冻结基点 `5ced063043c264618d15ae6cd47b98d2487500b4`，已核对包含 PR38、PR39、PR40；检查时没有原有工作区修改。新增目录此前不存在。

## 范围、输入与冻结协议

- 仅三包×两车，共六条正式回放；每条共用一次全量定位，同时维护 M1 与四个独立排除图组成的 M2。六条全部完成，无超时或估计器失败，累计正式进程 13.053 秒，最大单条 2.818 秒。预算为每条180秒、总计1800秒，没有自动扩展。
- [protocol.json](protocol.json)、[六个纯估计器配置](configs)、[评价窗](evaluation.json)在任何正式回放前冻结。20秒窗口、1秒状态、最多21个求解状态、max_nfev=50；原先验、权重、鲁棒损失、M1=1.0、M2=0.062191200771030145m及连续两次超限规则不变。
- PR39 近零运动协方差、测距可信度均关闭。不含车间因子、联合定位、独立 IMU 因子或动态终点拟合。Odom 运动阶段只用于事后诊断，不反馈模型。
- 三包原始 SHA256、013206 和 P1 标定输入 SHA256 见 [source_lock.json](source_lock.json)。Car1/Car2 的起点、初始朝向、天线高度与水平外参均来自 PR38。朝向为未独立测量的摆放假设；几何中心是否对应 Odom 原点仍待现场核验，不能把起点/终点当作连续真值。
- [calibration.json](calibration.json)同时保留 PR38 完整精度值和独立静态包复算值。定位始终使用原归档值。当前 NumPy 环境复算几何出现约1e-15m舍入差，用1e-12m容差验证；第一次精确相等预检停止记录于 [preflight_failures.json](preflight_failures.json)，当时未创建实验目录、未启动估计器。不是重标定或参数优化。

## 时间与计算口径

这是显式的新关联版本 `bag-receipt-v1`：同一 bag 所有消息中第一条接收时间为两车共同原点；接收时间同时用于 Odom 插值和 UWB ±0.4秒统计窗。每链路至少5个有效样本，t+1秒关闭窗口，插值端点必须已到达；不重写已关闭窗口，EOF不推进虚构时钟。

原始 `header_ns` 与 `bag_receipt_ns` 均以整数纳秒保留在各运行 `sensor_provenance.jsonl`；`association_time_s` 是新关联坐标。内部兼容接口 `Event.header_s` 在本轮承载关联时间，**不代表丢弃或改写原始消息头**。原 bag、PR40 历史协议及估计器源码均未修改。两车输出范围独立记录；本次恰好一致，不能事先假定。

按接收时间关联时，已到达消息的关联时间就是其到达时间，因此本轮关闭窗“迟到”计数均为0；这不证明物理测量没有延迟，也不说明 header 时钟已同步。完整 header−receipt 差和原始记录仍可检查。

两车分别使用独立的虚拟串行工作者模型。`updates.jsonl` 中 M0/M1/M2 的可获得时间是分阶段计算完成时刻；`delivery_times.jsonl` 中 `result_available_receipt_s` 另计入本次外部诊断补充、JSON写盘与flush。1秒等待、下一条事件触发等待及计算/排队分别记录；当前输出写盘成本会进入后续事件的虚拟队列。bag解码、输入档案写盘、进程启动不计入虚拟时钟，但计入实际单条预算。正式进程串行执行，不是实车双工作者并发测试。

六条虚拟事件队列均无积压，结果年龄最大约1.800秒；050447末状态主要多等了约0.779秒才有下一条真实消息触发关闭，不是额外假造EOF，也不是单次计算耗时0.8秒。

## 结果文件

|文件|用途|
|---|---|
|`run_inventory.json`、`runs/*/run.json`|六条状态、命令、实际耗时、源码锁与输出哈希|
|`runs/*/output/updates.jsonl`|508条状态、全量/排除先验、创新、后验残差、求解状态、依赖截止和可获得时间|
|`runs/*/output/sensor_provenance.jsonl`|原始header、接收/关联时间、topic/tag/frame、墙锚原始样本与peer独立档案|
|`runs/*/output/delivery_times.jsonl`|当前输出写盘后的可获得时间、实际未限速写盘耗时|
|`results/summary.json`|逐车可用性、报警时长/比例、启动/其他不可用、成本、停止支持和冻结终点|
|`results/states.csv`|逐状态定位、Odom阶段、M1/M2、缺测原因、等待/计算/队列时间|
|`results/links.csv`|2032条墙链路记录：raw、一次修正、创新、后验残差、支持数|
|`results/exclusions.csv`|2032条分锚解分离与有效性、最大项及独立历史链哈希|
|`results/events.csv`|连续报警/不可用区间、车辆、时间段、运动阶段与最大项统计|
|`results/correspondence.csv`|全部48个PR38起终点×车辆×墙链路窗口的对应|
|`results/PR38_comparison.csv`|与旧独立/联合整包平滑的输出差，仅作信息范围不同的比较|
|`results/peer_diagnostic_only.csv`|双向车间测距独立曲线数据，从未送入本轮定位/监测|
|`results/*_diagnostics.png`、`.svg`|每包一张两车共用时间轴的七行诊断图，四墙链路完整保留|
|`verification.json`|原始样本独立重算分箱/插值、一次校正、2032条排除历史、阈值触发及时间因果性审核|
|`source_lock.json`、`final_source_hashes.json`、`ARTIFACT_SHA256SUMS.txt`|数据、源代码、配置、报告与交付产物哈希|

人工终点严格使用冻结 PR38 时刻：015334的89–93秒、033248的52–56秒、050447的104–108秒。六条均完整覆盖且记录 Odom 支持条件停止；L包Car2存在约0.008606°的累计微小航向变化，因此严格数值常值标志为false，条件停止标志为true。没有因该差异挑选新的评价窗。

没有连续真值，不提供真实全程误差、真实误报率/漏警率。M2最大排除项是解对链路的敏感度，不能当作已证实故障隔离。PR38/39是整包离线融合；本轮是独立单车因果定位，其时间关联与信息范围须分开解释。仓库未发现另一窗口新增、针对这三包的N10专项报告；该项明确“待对照”，不借历史Oct17报告猜测结果或物理原因。

## 验证、恢复与复现

复用 `/home/ubuntu22/uwb/offline-deps` 中 NumPy2.2.6、SciPy1.15.3、rosbags0.11.9、Matplotlib3.10.9，未安装依赖、未联网。所有普通缓存与测试临时目录留在项目内。环境、可见进程及工作区记录见 [environment.json](environment.json)。进程命名空间隔离，无法据本命令视图判断宿主机全部ROS/分析进程。

11项新测试及37项原单车测试通过，日志见 [adapter_tests.log](adapter_tests.log)、[reused_tests.log](reused_tests.log)；输入身份与时间递增预检见 [input_preflight.json](input_preflight.json)。本轮测试覆盖分车、共用原点与header保留、未来修改/截断、未到达插值端点、分车bias只减一次、peer隔离、M2历史独立、关闭监测定位不变，以及归档损坏/未完成项禁止自动重试。没有为验证而再跑六条正式定位。

从实际仓库根目录执行只读恢复与审核：

```bash
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 tools/run_two_car_independent_integrity.py --experiment docs/field_tests/two_car_independent_integrity_bridge_20261023 --resume-only
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_two_car_independent_integrity.py --experiment docs/field_tests/two_car_independent_integrity_bridge_20261023
```

测试复现（仅合成夹具，不启动正式bag估计）：

```bash
mkdir -p .bridge_work/tmp
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.bridge_work/tmp" python3 -m unittest discover -s tools -p test_two_car_independent_integrity.py -v
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.bridge_work/tmp" python3 -m unittest discover -s tools -p 'test_single_car_*.py' -v
```

仅从归档状态重生成图表与基础报告，输出必须是项目内尚不存在的新目录：

```bash
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR="$PWD/docs/field_tests/two_car_independent_integrity_bridge_20261023/cache" python3 tools/report_two_car_independent_integrity.py --experiment docs/field_tests/two_car_independent_integrity_bridge_20261023 --output docs/field_tests/two_car_independent_integrity_bridge_report_reproduction
```

基础报告是脚本输出；`INTERPRETATION_ZH.md`和一页结论的收尾解释为本次人工复核，不冒称脚本逐字节自动生成。计时随机器负载变化，不宣称可逐字节重现。

如需在另外一次明确授权的复现实验中从零运行，复制本目录的 `configs/`、`protocol.json`、`evaluation.json`、`calibration.json`、`source_lock.json` 到新的项目内实验目录，并只从原清单提取六个 `id/bag_id/car`，将新清单状态设为 `planned`；然后对新目录使用同一运行器的 `--run`。不复制或覆盖原 `runs/`。初始`--freeze`入口要求仍位于冻结基点；收尾提交后应使用上述精确冻结档案复现，而不是把新HEAD冒充原基点。本轮没有执行这次额外六条回放。

失败或running项保留原产物，不自动重试；源码、配置或输入哈希不符即停止并另起版本。原PR38/39/40文件与实验失败档案保持原状。本轮完成后停止扩展，不启动车辆、不推送、不合并main。
