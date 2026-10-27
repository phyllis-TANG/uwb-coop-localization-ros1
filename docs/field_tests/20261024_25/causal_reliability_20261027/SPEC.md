# 六维 SE(2) 因果 EKF 可靠性插件规格 v1

本规格在开发矩阵前登记。起点 32445a299b3f4674b865c4d78c4f662e51b5b857；算法基准 7128abc769121f1f39c3959ce195ac545656c86c，tools 无差异。没有调用 PR47 的四维 Estimator；只移植逐有向来源的 gate 机制与工程限幅概念。

## 不变的数学和准入

状态顺序 [x1,y1,yaw1,x2,y2,yaw2]。直接使用 causal_baselines/model.py 的 Baseline、SE(2) Odom 预测、三维天线斜距与解析 H、Joseph 更新。默认 peer_policy=None 的旧三方法计算顺序和输出字段保持原样。共用初始化、R/Q、每车不同锚点、旋转杆臂、到达顺序、raw primary、trace/bridge 去重、Car1→Car2、200ms 链路间隔、最多 60ms 已到达 twist、200ms 延迟门槛。拒绝的 peer 仍占用该次已准入链路时刻，避免 gate 因拒绝而以额外帧更新；不消费反向 peer。真值和注入标签不传给插件。

## 方法与反馈

- odom_only / independent / joint：原实现。
- huber：同六维 EKF。预更新残差 u=innovation/sqrt(R)，w=min(1,delta/abs(u))；R_eff=R/w，以当前 P 重新求 K，正常反馈均值与 Joseph 协方差。这是单次 IRLS 风格近似，不是原四维 MAP。
- gate_only：相对当前反馈状态 x-、P- 的 z=innovation/sqrt(H P- H'+R) 门控；接收时原 EKF 反馈。
- cap_only：原增益，在每次已准入 peer 事件按车缩放增益的三行 [x,y,yaw]；使本事件 XY 改变量不超过 cap。正常反馈。
- gate_cap：上述 gate 和 cap 组合，正常反馈。
- shadow_only：无 gate/cap 的非反馈控制。内部反馈状态不接受 peer；仅把本次 peer proposal 与独立状态之差作为输出修正，按下述保持政策发布。
- gate_cap_shadow：同 gate/cap，基于独立反馈状态形成 proposal；peer 不反馈至内部状态或 shadow。与 shadow_only 使用同一非反馈与保持政策，不把其复位/保持作用归因于 gate/cap。

每个候选有独立 Baseline('joint',...,peer_policy=...) 及独立 Baseline('independent') shadow；后者只接收自车 Odom/墙距，peer 全排除。shadow 的完整均值/协方差逐事件与独立组核对。每包/方法新建实例。非反馈组的内核在通过数值校验后不提交 peer proposal，因而它自己的反馈状态也逐事件等于 independent，没有偷偷重置已经污染的先验。

## Gate 与恢复

每个有向车辆来源分别保存 bad/good/closed。abs(z)>3 时当次拒绝、bad++、good=0；连续 3 个 bad 后 closed。好值时 bad=0、good++；closed 连续 4 个好值才重开，第 4 个可用。逆向被固定准入排除，不改变 gate。重复、bridge、过旧、异步支持不足都在 gate 前拒绝。缺失不虚构 good，也不自动恢复；只在下一个真正准入样本继续计数。

## Cap、yaw、协方差

每个有向 peer 事件，cap 相对该方法的事件前反馈状态，而非真值/未来/最终轨迹。每车自身 shadow 在最近 1s 的墙更新 Jacobian XY 信息 sum(Hxy Hxy'/Rwall) 最小特征值>=18 且至少 3 个不同墙链接时用 0.06m，否则 0.35m。该判据只描述局部几何，不能证明墙无偏。阈值与 cap 是未标定合成工程起点。

先保存未限幅 K、proposal、Joseph covariance。按车 alpha=min(1,cap/||Kxy innovation||)，令该车 [x,y,yaw] 增益均乘 alpha，yaw 的 peer 修正也缩放并 wrap；用实际缩放增益及 R_eff 重新计算 Joseph covariance。反馈组提交该均值和协方差。它们有限/对称/PSD 只说明数值性质：因增益依赖观测、截断及线性化，不能称校准后验、误差上界、PL 或概率完好性。

非反馈组保存 proposal 的上述协方差作诊断，内部反馈协方差保持 independent 原值。输出用独立状态加最近一次准入 peer proposal 的 room XY/yaw 修正；修正保持到接收轴 age>200ms 后归零，下次 peer 拒绝立即清零，逆向/bridge/重复不刷新有效期。不把保持修正传播成 EKF 信息。非零保持修正时发布 covariance=null，原因 output_only_held_correction_no_calibrated_covariance；零修正则给内部工程协方差。保持政策是额外工程选择，由 shadow_only 控制显式隔离。限制的是相对 shadow 的输出修正，绝不限制真实位置误差。

## 预登记矩阵与评价

8 场景：normal、weak_wall_correct_peer、peer_bias、pulse、ramp、async_missing、weak_wall_peer_bias、coherent_fault。每场景登记 car1/car2 两个角色及 5 个独立开发种子 211/223/227/229/233，共 80 个计划行。normal、peer_bias、pulse、ramp 的角色不改变输入，登记 duplicate_of 并去重，共 60 个实际组合。角色定义为墙支持变弱/受偏或丢 Odom 的车辆，不是采集方向。仅 Car1→Car2 被使用；反向注入另做未消费输入负对照测试，不声称反向更新传播。

48s 轨迹；Odom 50ms、双向距离 100ms（各偏移10/30ms）、发布100ms；故障[12,30)s，恢复18s。正常阶段[0,12)、故障期[12,30)、恢复期[30,48)分别逐车报告 XY RMSE/max/0.5m越界、相对 independent 的配对损害/收益、拒绝/clip/gate恢复、计算成本。误差只在明确的 state_epoch_ns 对合成真值评价，无事后配准。按 seed 配对，角色/帧不当独立重复；全部是开发探索证据，不包装成盲测。

不靠结果调阈值。测试、回归、小 smoke 先行；矩阵前提交源码及 frozen_protocol.json。恢复必须来源/配置/种子/输入/输出哈希全匹配，失败项也保留，新源码指纹开新目录。独立 verifier 不导入 estimator、generator 或 evaluator，逐行读取实际状态、准入、proposal、gate、cap、failure 与真值文件并重新计算数值不变量及指标。

T10 仅在严格字段齐备时使用同一入口；缺项按实际字段 BLOCKED。无参考不报告实包 ATE/RMSE。T09/T11/T13/T15 不定位回放、不调参。大输入/结果/venv 全放 Git 外；归档提供 SHA 和可取得位置。

## 正式运行前补充

计算成本分列原六维内核/策略处理和私有shadow处理的逐事件耗时，总时间另存；不把日志序列化算作车载滤波器成本。恢复前同时校验根证据清单和每条原run.json哈希。报告固定绘制开发种子211、car1角色的peer_bias轨迹与时间序列，全部组合保留分车表和配对均值/范围，不按效果挑图。T10缺项由preflight_t10.py实际调用既有严格编译器产生，未知项不替换。
