# 方法、审计口径与复现

执行基准为2b43ec9fef0ea22f0d35318b2f11e35c646cce6c，正式执行源码为12a1d94379b58c5a759b1698425fb90d48587609。所有新增代码只在tools/single_car_quality_fgo；旧IMU内核、B目录、公共geometry/manifest不变。Q0/Q1直接调用PR58冻结F0/F3，Q2/Q3在相同骨架添加同一套UWB质量控制。所有组原伪Huber、平移/初始化/P1/窗口/发布规则一致。关闭测试覆盖跨越20秒窗口后的逐项相等。

每条因子是原关键帧±0.4秒、至少5条到达raw测距的中位数，减一次既有P1。分数由排除该锚的影子图在相同状态/截止时刻产生，计算发生在主图本次优化之前。四个影子各从同一外部先验独立初始化，从未消费各自待检锚；保有自己的状态、缓存和QR边缘化先验，其余UWB新倍率恒1，仅保留原伪Huber。它们共享Odom、gyro、初始化和其他墙误差，排除图不是真值。

工程分数为绝对斜距差/0.20m。已知且连续两次≥1.5，信息倍率降至0.10；连续两次≥3停用为0；连续三次≤0.75后以0.25恢复，再三次低分回1。unknown重置持续计数、保留上次策略倍率，初始为1但不表示健康；缺测实际倍率null。当前其他有效锚不足3、XY几何退化、解算未接受/秩不足或F3角输入缺口均unknown。没有标定预测协方差，不称NIS或PL。

信息倍率g只以sqrt(g)乘原伪Huber后的UWB残差与Jacobian一次。初入图冻结，后续重线性化与消元沿用；仅消元incident因素，保留全部位置/yaw/bias交叉项、affine与常数，保留消费factor ID防重复。g=0是显式零信息行，不能清除已进入状态和先验的故障。无历史回滚、bias锁定或定位器切换。后验残差仅诊断，不反馈本次质量判断。

开发为4场景×2种子×4组=32次加速回放，计时标记virtual；正式为8场景×3新种子×4组=96次60秒回放，每条输入四个独立进程、共享host anchor，按原receive节奏paced。开发种子101/151，正式401/419/443。同种子跨场景噪声配对、同输入各Q完全一致。合成消息的source_file_sha256是生成recipe的稳定身份，不冒称真实文件字节哈希；events文件字节SHA由run.input_sha256和完整输入索引另行锁定。三个种子不能外推长期或极低故障概率；每帧不是独立实验。

正式状态为每秒关键帧，保留原1秒等待。输出数据flush后才写availability；publication_id连接账本与available_receive_epoch_ns。该时刻来自host单调时间与声明的合成接收时钟映射，包含影子、监测、主图、写出和调度排队；不是车载ROS链路实测延迟。状态误差按状态时刻真值；另列“延迟位置直接当当前位置”的可获得时刻误差，不能把前者解释为当前保护。availability遥测自身和后续检查点写出影响后续排队；不宣称fsync持久化界。另一个计时审阅发现：冻结的complete_processor_wall_s在生成后验诊断之前截取核心耗时，再加输出sink耗时，因此遗漏两者间的后验诊断/封装；不能把该列当逐项完整CPU成本。额外独立读器以processing_cycle_start_monotonic_ns至data_flushed_host_monotonic_ns重建发布周期wall耗时，准确覆盖该周期影子/监测/主图/诊断/写出；此前消息ingest成本不在该周期内。完整端到端成本仍以实际release delay（含接收节奏/1秒等待/排队）为准。保留冻结原列，另列修正语义，不改旧日志或重跑。

误差统计包括全部有限输出、接受/有效输出覆盖和四组共同有效时段，不删unknown或失败预测。位置、yaw与有效gyro残余bias分别评价；共同角故障的bias目标是相对真值角速度的总gyro误差，物理bias另存，不能混称物理零偏。0.20m/0.20rad/0.01rad/s仅探索门限，越界秒数按每秒状态样本计，不是连续真值风险估计。

正常误降权/误停用按连续策略区间计事件，以实际相邻输出可获得时刻之差计时；末样本零外推时长。分别给每车与每链可监测/unknown分母，单车任一链事件与逐链事件不混加。故障评价包括全部链事件和有至少两个连续已知判断的可监测链事件；注入已存在的告警与新触发/升级分别记录。四链共同偏差是一个共同原因、四个相关链事件，不是四次独立故障。检出不等于误差被限制，健康链误归因和负增益全部保留。

恢复评价同时给故障结束后32–52秒及52–60秒位置误差。告警恢复要求首次normal倍率1后有两个连续已知normal确认，按首次normal输出可用时刻计；未检出/未恢复记null及删失，不填0。20秒窗口经过不能证明旧先验污染消失。

审计程序qaudit不导入在线策略/图/Jacobian，只复用PR58独立离线标量公式，独立核算工程分数、状态机、权重、成本、输入截止/原始SHA、完整影子历史/先验链，逐图每7次边缘化用有限差分核算Schur的H/g/常数。旧原生F0无逐次消元明细，该部分继承PR58/59及关闭回归证据，不冒称新增逐因子全检。额外stdlib读器从原publication和独立真值重算RMSE与正常事件分母；坏日志重封SHA后仍需拒绝。以上是同主机独立公式回读，不冒称B端外部复现。

在固定执行提交建立干净checkout及隔离venv后，依赖版本见环境/检查点。输出必须在Git外新目录：

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python tools/single_car_quality_fgo/qtests.py
python tools/single_car_quality_fgo/run_matrix.py --stage validation --output /absolute/new-experiment
python tools/single_car_quality_fgo/check_matrix.py --experiment /absolute/new-experiment --output /absolute/new-readback
python tools/single_car_quality_fgo/qreport.py --experiment /absolute/new-experiment --output /absolute/new-figures
```

这些是复现命令，本轮正式批次只执行一次。首次不加--resume；中断只能在输入/输出/协议/全部源码SHA匹配的完整case边界恢复。未索引partial目录保留并拒绝隐式重跑，不宣称恢复完整优化器内存状态。每CLI90秒、整批2700秒，无自动重试；完整实际argv见运行索引。已完成实验只需要回读，不能为改图重跑估计器。

B端的原生字段映射见A_BINDING.json；旧B中立示例评分/状态机不是本轮规则，需独立适配。历史两包本轮未运行，不能从本合成结果宣称实测误报率、全程定位提升或月球任务安全保证。原始message SHA/标量目录在B侧需保留侧车映射，缺失元数据不得编造。保留PR59参考/轴向/时钟和geometry的条件性限制。
