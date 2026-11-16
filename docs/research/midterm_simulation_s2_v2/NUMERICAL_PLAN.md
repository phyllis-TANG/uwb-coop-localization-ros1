# 数值候选计划（执行替代协议前登记）

仅开发，seed=26011601。formal_runs=0。不生成正式输入。

P0：逐字复用固定B generate/problem/solve；TRF，max_nfev=300，ftol=xtol=gtol=1e-10，尺度XY=1、b=.1。先保存32条件128结果及输入SHA。
P1：从每个P0终点统一继续TRF一次，max_nfev=100，三停止容差1e-14，原尺度；总预算400。不按成功与否选择是否继续，不无限重启。
P2：原始同一初值的LM，max_nfev=300，三容差1e-13，原尺度。残差数大于状态数、无边界、线性loss，适用LM。独立交叉检查，不按truth或误差挑解。
最多以上三协议，不解析消元、不多初值搜索、不改权重、不加b先验。各自保留最后解。P1预定为补充面板开发协议，若仍失败如实保留，不改阈值；P2不是择优回退。

接受仍为SciPy success、全部有限、原物理梯度无穷范数<=1e-5。额外记录尺度坐标梯度S Jᵀr；不能拿更小的尺度梯度替代原门槛。cost=0.5 rᵀr。记录实际残差/雅可比调用数、nfev/njev、求解调用耗时（P1另列累计耗时/次数）、warnings、status=0、异常。

诊断分类：相对P0代价降低>1e-6×max(1,cost0)，或任一点位置变化>.001m，或b变化>.001m，标记“仍可明显改变”；否则标记“局部稳定/停止口径差异”。这是诊断分辨率，不是新的成功阈值。弱条件/不同分支为独立标记：P1/P2位置差>.001m提示协议/分支敏感，不自动证明全局不唯一；秩在truth与终点分别保存，完整零空间及b信息另列。非有限/异常/warnings/上限分别记录。

补充：good/weak/near × static/turn，peer .3m，A survey中心，固定survey+带噪运动积分初值（不由先验中心变体重建）；no_prior、sigma=.5、sigma=.05、sigma=.5中心+delta四变体，另只在三几何static/peer增加sigma=.05中心+delta。共27条件108方法；不扩成wall/bias/profile全组合。中心对比固定sigma/start，权重对比固定center/start，统一B噪声流。near精确使用A参数。无truth参与求解或候选选择。B0/B1/B2/B3共享输入，B2已知受影响链路，B3另知补偿量。
