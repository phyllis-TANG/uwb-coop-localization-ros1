# 接手与边界

固定起点PR117 `27b0ecf4d76124d54912d26d33432e1718dca494`。
任务一冻结 `02af736734e272cd524cf38afb9991bb0b240f48`；任务二冻结 `7a22287b199060b4a7a6c0b68ea4ba9f5953eef9`。
不修改PR114/117代码、资产或结果，不修改A/B/C。原始数据源本轮为PR117便携reference，不是新NPZ复建。

## 已完成与预算

- 旧180端点独立读回，169/11不变；精确H、GN、Newton局部预测与longdouble代价诊断。
- 11失败+11分层对照统一继续，各一次，22/22优化器调用。
- 无优化器输入/模型验收及假求解器持久化验收。
- 已暴露seed开发12方法/24调用。
- 新10seed探索360方法/720调用，P0/P1全保留，最终349接受/11未接受。
- 完整便携读回不调用优化器，复原原始JSON哈希、指标与图。

合计实际SciPy调用766，formal_runs=0。硬预算已经使用，不在本任务下自动增加实验或重跑。

## 不可回填的历史

任务一的2个转接受只是新继续结果，PR117的11个原NOT_STATIONARY不重命名。
任务二P0/P1最终规则已冻结，不从两个端点中按误差择优。
所有11个新未接受状态都是有限结果；报告包含它们，同时另报双方接受子集。
若遇到attempt而无result，必须保留为可能已调用的孤立记录，不自动重试；本次没有此情形。

## 下一阶段接口

ordinary worker只读measurement和SOLVER；reference仅生成/评价读取。不得把故障类型、注入曲线或quality加入定位权重。
M2仍是单常bias，不要在此结果上默认为时变估计器。step/ramp均值不是可用的真实常参数目标。
所有状态、梯度、残差与阶段调用在estimates归档；PER_RUN/PEER_RESIDUALS/STAGES/SUMMARY给出紧凑证据。
如新增模型，要在新目录/新协议中增加，不修改本轮冻结结果。

未实现：时变bias求解器、故障检测、保护级、完整性风险估计、物理车辆/土壤动力学或GUI验收。
仍缺可信高度与设施误差、真实运动观测、UWB偏差时间结构/相关性、实车参数及正式风险评价依据。
建议按DECISION_MEMO先补观测不确定性契约，再决定最小时变建模与检测的独立验证协议。

## 本机位置（不是跨主机假设）

worktree `/home/ubuntu22/uwb-moon1-numerics-timevarying-bias`；Git外数据 `/home/ubuntu22/uwb-moon1-numerics-timevarying-bias-artifacts`。
诊断diagnosis001，继续continuation001，开发smoke001，探索explore001，原始/便携读回readback001/portable_readback001。
这些目录不覆盖历史资产。无上述目录时，提交的结果包仍可独立读回；再生成使用固定提交和全新输出目录。
