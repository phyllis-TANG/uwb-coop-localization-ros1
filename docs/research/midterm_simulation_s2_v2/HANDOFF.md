# B端v2交接

交付分支research/midterm-s2-numerics-v2，父提交为固定B 8174445e3b8e473bef15a82d345b7a7e1d94ac05。A固定ed17e3ad177b5d52c1470e85da9f7a8645dbada9已对齐，不等待A活动分支或下一轮结果。新增内容仅tools/midterm_simulation_s2_v2和docs/research/midterm_simulation_s2_v2。

本轮共同面板：P0 45/128、P1 128/128、P2 124/128；原83次未接受在本面板中表现为状态局部稳定与停止口径差异，不能替原403次全部定性。补充P1 107/108，good/static/center_plus_weak/B2梯度1.048729e-5，仍不接受。原效果状态变化很小，但强有偏prior敏感，单seed不能确认性能收益。

formal_runs=0，未生成正式输入。继续有限诊断，暂缓正式验证，不自动合并PR。PR以B开发分支为base，便于审查仅v2新增内容；不表示授权合并B或v2。完整交付HEAD和PR链接由提交后回执给出，避免在提交中写自引用SHA。

正式验证前剩余事项：

1. 本轮A/B统一核查先验、数值残留和秩/偏差信息解释，尤其不要把整体秩亏写成b不可辨识。
2. 明确P1剩余失败政策；不为全通过反复调阈值。如需新方法，另立有限开发计划、保留本轮记录。
3. 决定受控geometry×motion主矩阵、先验主场景和压力面板；保持中心/权重/初值独立。
4. 冻结统计单位、失败分母、误差阈值、样本数、源码/依赖/配置、未暴露新种子与存储预算。
5. 得到另轮正式执行指令后才生成输入；本工具无formal模式。

原始展开目录：/home/ubuntu22/uwb-midterm-s2-numerics-v2-artifacts/run1。核心证据已压缩入库，不依赖此绝对路径才能读回。A只读checkout：/home/ubuntu22/uwb-s2-v2-a-readonly。运行/复核命令和数据字段见README。
