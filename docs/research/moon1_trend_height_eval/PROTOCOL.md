# M3与高度敏感性预冻结探索

固定起点0c3dbbb59a5c65087e073ad1c49eaed397f2958b；仅新增两个moon1_trend_height_eval目录。
PR114/117/120及A/B/C只读，不改轨迹、地形或历史统计；formal_runs=0，无GUI或动力学。
完整观测假设见UNCERTAINTY_CONTRACT，状态/尺度/信息见MATH，配置/seed/随机流见CONFIG、SEEDS。

## 计划与生成

采用固定PR120 reference派生的0/8/16s三窗，每窗6点dt=.2s，同窗记录逐值一致且归档与固定Git提交哈希匹配。
M0/M1/M2原目标保留；M3只加中心时间τ的线性peer bias状态，不增加先验、不读取故障类型/曲线/切换时刻。
sigma_h=0是height-oracle；非零为h_used=h_true+e，true测距始终由未改动true天线XYZ生成。
每个window/seed的两车标准高度误差来自PCG64 SeedSequence([seed,window,3])独立流；噪声range/motion/prior分别流0/1/2。
同一个标准高度误差跨所有方法、曲线和幅度共享；e在同车整个窗口内固定。记录标准值和实际e，不仅记录σ_h。
实际测量、运动、prior、初值不随高度幅度改变。估计端不知道σ_h/e，固定权重，不补偿/融合高度误差。

A：3窗×4曲线(normal/constant03/step03/ramp03)×20新seed×4方法=960。
B：3窗×2曲线(normal/ramp03)×2非零高度sigma(.05/.15m)×20同seed×4方法=960。
B的sigma0基线使用A中的sigma0_unit索引，不重复求解。输入计划共480单位、1920唯一方法，执行前随协议提交。

开发仅用PR120已暴露911170101，优先零优化器数学检查；预定w0八种条件×四方法=32运行/最多64调用。
开发总限仍为96运行/192调用；若验收阻塞只在余量内修复，不无限迭代。本轮不预先暴露20个探索seed的运行结果。
冻结后仅执行上述1920运行、最多3840调用；开发+探索真实调用≤4032，不按结果追加seed/窗口/高度。
所有有限P0均P1一次，阶段预算与接受门槛见SOLVER；不要求人为100%接受，失败完整保留。

## 持久化与输入隔离

输出根目录必须新建且持独占RUN_LOCK；普通估计入口只读measurement与不含条件曲线的EXECUTION配置。
严格schema拒绝reference/注入/quality字段和reference路径。reference、measurements、estimates分开。
调用前在BUDGET_LOCK内检查硬上限并以exclusive-create+fsync保存attempt（输入/代码/配置/阶段/起点）；已有attempt禁止重跑，即使结果缺失。
已存在结果、孤立attempt、并发锁与硬上限均用假求解器验收，不计真实优化器调用。
每阶段记录完整端点、代价、梯度、退出原因、评估数、状态、秩和局部信息；运行源文件哈希必须与冻结一致。

## 验收与冻结

独立残差/J与中心差分；M3 b1=0与M2一致；normal/constant/ramp真值匹配；step不要求零残差；range/data/total秩与协方差；输入拒绝。
高度只进入供给几何，观察/true XYZ不变；M0只需对peer注入不变，不能对高度误差不变。
开发验证后提交协议、配置、SEEDS、源码依赖hash、INPUT_PLAN、验收及预算，再自动执行。源码不在观察探索结果后调参。

## 统计与预定主要对比

逐窗逐seed逐车MSE=mean_t ||XY_est−XY_ref||²，RMSE=√MSE；相对位置误差使用两车差向量。
benefit=MSE(M0)−MSE(Mk)，正为协同改善，同一window/seed/曲线/高度配对。
主要对比1：A理想高度ramp03，ΔMSE=MSE(M3)−MSE(M2)，负为M3改善。normal/constant/step全部保留。
主要对比2：normal/ramp03，每方法ΔMSE=MSE(非零高度)−MSE(自身sigma0)，正为恶化；两个非零幅度都报告。
同时列M3−M2在各高度下的对照；不能挑有利幅度。报告正常条件误差/协方差/条件数/接受率代价。

先在同seed内等权合并三窗口的MSE，再取平方根得到seed簇RMSE；对20个seed簇汇总均值，逐窗另列。全有限与双方接受子集分开；不把失败填零。
为保持seed簇完整，主要对比的双方接受统计要求该seed三个窗口的两方均接受，否则该seed不进入该子集，并列实际分母。
普通方法接受子集同样要求三窗全部接受；协同收益的接受子集要求该方法和M0三窗全部接受。
不报告bootstrap或显著性区间，本轮仅均值、中位数/范围及全seed散点，20seed不确认稀有风险或覆盖。

peer逐时刻残差为模型预测−观测（M0为未使用的诊断量），保存六点曲线、后半−前半均值和RMS。
bias状态对normal/constant/ramp可列模型匹配参数；step没有真实线性参数，不定义拟合参照误差。
图固定第一个seed，并展示全部20seed的簇均值散点；不挑有利案例。
局部信息是给定高度的GN条件诊断，不作PL/HCPL/HMI、安全保证或检测器。
