# 2026-11-01 开发准备：复用与8维缺项

本轮目的仅为仿真输入、接口和开发核查。运行环境名称按交接为 uwb-coop-localization-ros1；实际实例 ID 为 `ccarenv_b64_Y2NhcmVudl8xY2NjYjU4MzlkMDA4MTkxOWI0N2NlNjA2NTgyZmYzZg`。启动后实际工作树 `/workspace/uwb-coop-localization-ros1` 分支 work、干净 HEAD 为 `6c8b23087739418faa2169bf08ccae80d2d884c1`。2026-11-01 本次 GitHub branches/main 与环境内 `git ls-remote origin refs/heads/main` 独立查询均返回该 SHA。这是本次观测，不保证之后 main 不变。

新增 worktree `/workspace/work/uwb-sim-imu-prep-20261101`，分支 `analysis/20261101-sim-imu-prep`。所有原工具、现场录包/部署脚本、历史结果不变；开发输入/日志在 Git 外。源文件逐项 SHA 见 `tools/two_car_sim_dev_20261101/source_lock.json`，包含原 IMU 工具、固定依赖和 B1 纯函数；每个新 run 再保存全部新增源码 SHA 和实际执行提交。

|现有资产|固定来源/复用方式|本轮边界|
|---|---|---|
|`tools/two_car_imu_fgo`|上述 main 快照；其 `pinned.py` 固定 base `ca8fbac4dbdf678074be5fb80bf6aff472d258e6`，并验证 dependency_lock|M0/M1 为原6维；M2/M3 为8维。新入口只暴露 M2/M3/M3W025，避免把换内核解释成监测收益|
|`tools/two_car_fixed_lag_fgo_v1`、`tools/single_car_imu_fgo`|原 IMU dependency_lock 核验后只读加载|原20秒窗、1秒关键帧/等待、工程权重保持；gyro 替代 Odom 角因子；缺 gyro 移除角边并 hold yaw|
|`two_car_imu_fgo/simulate.py` 及 F0 simulate|复用配置、事件协议、3D几何/杆臂约定、延迟策略、确定性 gzip 写法|旧生成器固定64秒旧轨迹，且 gyro 定义为下一个50ms区间平均值。新入口改为当前时刻解析瞬时角速度并前向保持，不复用旧轨迹/未来平均 gyro|
|`cooperative_influence_probe_20261028/core.py:WeightedObjective`|核对权重语义，适配思路相同；没有导入其6维图|外乘代价权重 .25，因此残差/J 均乘 .5；sigma 保持 .2m，不能用 sigma .4m 替代整个非线性伪 Huber 曲线|
|`tools/cooperative_integrity_baselines_20261029/monitors.py:four_anchor`|只读纯函数，经固定 SHA 独立模块加载；输入为所有方法相同 arrived bins|B1仅原始四墙统计量。原 `.2m` 工程尺度不是新噪声标定；阈值未校准，local/network 均 unknown|
|同目录 B2 `engine.py/influence.py/binding.py`|仅审阅接口和历史结果，不运行原 run.py|明确绑定原19文件 PR68核 `74fa210e7cf6aa322eaebce19530510edb605d22`、6维状态/先验、三维 Odom 行、固定 primitive 时轴；旧入口仅seed101 nominal/car1_common_wall_bias/peer_bias，完成目录禁止覆盖；不能直接接8维|
|40合成/8旧实包 IMU对照|`docs/field_tests/20261024_25/two_car_imu_fgo_20261028/REPORT.md` 等已完成资产|只引用，不重新运行整套，不接触旧实包|
|37 profile预算比较|`docs/research/cooperative_integrity_baselines_20261029/{REPORT,HANDOFF,FROZEN_SPEC}.md`|37声明profile共用原G1轨迹，不是37套定位器；历史完成，不重复计算|
|既有确认/边界资料|`docs/research/integrity_validation_20261030/REPORT.md`；followup/c_scope 与 a_evidence；本次用户交接|报告支持14秒较有利、7/28秒及另一车代价；50%校正预测失败、简单残差排序反例按用户交接保留，本checkout未定位到这两项的独立原表，不声称重新核验|

历史边界必须随交付保留：原报告7秒墙故障 Car2 B2 不报警，28秒 Car2 在 AL=.10m 仍有 HMI；14秒有利不能外推成普遍覆盖。交接中明确的“50%校正预测失败”和“简单残差排序反例”作为既有约束原样保留，相关原表/源版本仍待本地补链，不能因更换8维模型被抹去。当前引用均为历史报告或用户交接，绝非本轮新独立验证。

|8维监测缺项|现有6维实现的依赖|本轮状态与必要下一步|
|---|---|---|
|源排除子图自启动历史|B2三个子图独立状态、热启动、QR先验、仿射项与常数|**未完成**。需在 M3 同一8维模型内从起点独立排除 car1墙/car2墙/peer，禁止复制完整图当前 prior 再删活动因子|
|gyro/bias primitive 与共同噪声|旧 Primitives 初值6、每 Odom edge 3行；noise_matrix 假定旧行序|**未完成**。需加入每车初始bias、gyro样本/积分、bias RW、缺角边秩变化；记录原样本ID到积分/median支持的映射|
|同源解交叉相关|旧 separation 用 (Kfull−Ksubset)(...)ᵀ；cross=Kfull Ksubsetᵀ|**未完成**。8维必须共享 primitive 列/协方差，覆盖车辆内、跨车、跨时、Odom表示与gyro依赖；不允许把解协方差直接独立相加|
|QR prior 噪声传播|旧固定6列满秩QR、固定时轴1..63|**未完成**。8列、rank-aware pivot QR、符号/基一致性、affine和消元常数、所有 bias/跨车信息均需跟随各自历史；当前8维定位先验已保留，不等于监测灵敏度已适配|
|因果时间与发布|IMU frontend 有 receipt prefix、availability、积分支持；B2旧1秒邻接 Odom 假设|定位和B1原始输入可检查；**8维B2未完成**。所有子图/统计须同前缀，报警时间绑定物理可获得时间；状态hold评价与虚拟CPU排队不能冒充实车时延|
|B1阈值、可用性与网络声明|旧 engineering/raw/median_iid 三尺度及 local/network OR|纯统计复用，**新阈值未完成**。运动bin偏差、样本相关与同预算正常校准需单独检验；unknown不是健康|
|同模型对照和失败|原 M2 每车独立停止，但 joint transaction 保留|成功解模型上独立；全车失败发布事务仍耦合。核查无peer成功路径，不能承诺异步失败独立性；监测失败须 unknown/failure|
|风险/恢复/外部真实数据|旧阈值/AL为工程设定，没有认证界|**未完成**。A1/B1仅开发、A2/B2留出；云端没有新包。恢复判据/正式参数未冻结，不输出“恢复成功”或理论风险界|

上述 B2 缺项已在开发试跑前列明。本阶段不做 B2 vs B1 的8维效果比较，B2统一 `unknown: B2_8D_HISTORY_AND_SHARED_NOISE_NOT_ADAPTED`。短试跑只能检查定位接口、原始B1一致性及CPU/内存。

文献与可证伪预测：本轮只阅读仓库已有文献审查，未重新取得论文全文。Hafez 等 [RA-L 2020](https://doi.org/10.1109/LRA.2020.2975769) 已涉及 fixed-lag SS、故障历史/prior、相关解分离和风险/可用性；[PLANS 2020 CIM](https://doi.org/10.1109/PLANS46316.2020.9109996) 已有共同/特有源与局部/全局创新；followup/c_scope 还列出 LOO/LTO、working prior 等近邻及全文缺口。不能把 SS、源分组、完整QR历史、IMU或逐车表本身当创新。

若之后完成同模型8维适配，待冻结的可证伪预测为：P1，在同输入和同正常预算下，成熟B2对未注入车的越限未报警暴露优于B1，同时显式报告注入车与可用性代价；若无逐车净收益、预算不合格或unknown增加抵消收益，则拒绝该适用性预测。P2，固定.25缩权预期降低部分跨车扰动但可能牺牲故障车校正；任何普遍单调收益主张都可被逐车反例推翻，不预设成立。P3，当前bin恢复/退出窗不等于prior影响清零；用同seed配对正常run及各自完整先验记录检验，若无可分辨残留则不声称存在残留。效应门槛与恢复条件均待冻结，不用本轮故障输出调它们。

与近邻当前可明确的差别只是问题设定：相同8维gyro/bias模型、两种指定运动、局部墙共同偏差、逐车覆盖与协同代价共同报告。**算法新颖性尚未闭合**。如果没有额外必要需求和充分区别，正式矩阵没有自动启动依据，交付适用边界/负结果即可，不自动搜索新算法。
