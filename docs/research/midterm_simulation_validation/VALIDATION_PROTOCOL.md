# 正式验证冻结协议

本交付formal_runs=0，不包含正式观测。冻结矩阵和代码交给A验收；A验收及正式运行是之后的操作，不由本交付自动启动。来源为PR101 `5e4e7ef6e2592cae5b4a4fc6462cbdbaeefb32da`，只读参照PR100 `2e28d99e8b6fa74384b795f8847ab72d5fa6e551`。源码/协议/配置/种子证据见FREEZE_MANIFEST；完整冻结提交在运行前由命令参数记录到Git外RUN.json，避免自引用。

## 唯一执行配置与模型

CONFIG.json是生成、求解、接受、统计的唯一参数源。运行时保存完整解析配置与其规范JSON SHA256，不从旧B CONFIG读取运行参数。旧B prototype.problem与PR97的model/movement只作为冻结数学目标依赖；它们的内容哈希也纳入清单。六时刻、两车XY、24或25维为此版本支持的固定结构，配置若要求其他维数会拒绝，而不是静默忽略。

状态按时刻排列[x1,y1,x2,y2]，B2末尾一个自由常值b，单位m。每时刻8墙测距+1peer，运动是房间坐标下连续XY位移，不是未知航向轮速里程计。good/weak/near锚点、起点、survey和static/turn公式全部写入CONFIG。range sigma=.04m、motion sigma=.02m，独立Gaussian白化。无偏差先验、正负约束、ridge或robust loss。

B0删除peer，目标块可分离；B1协同不增广；B2预知受影响链路，wall=Car1-anchor0或peer六时刻同一个b；B3额外知道真实注入幅值，使用显式oracle校正接口。真值仅用于生成和离线误差，不进入解的选择。常值注入与自由b平移的目标等价性不构成未知故障泛化证据。

## 冻结矩阵、噪声和初值

|组|几何|运动|链路/幅值|位置prior|条件数|
|---|---|---|---|---|---:|
|core|good/weak/near|static/turn|wall/peer × 0/.3m|固定survey，sigma=.5m|24|
|no_prior|三几何|static/turn|peer .3m|无|6|
|strong|三几何|static|peer .3m|固定survey，sigma=.05m|3|
|shifted_strong|三几何|static|peer .3m|survey+delta，sigma=.05m|3|

共36条件，CONFIG中50个新独立观测seed，对应1800配对条件、7200方法运行；P0/P1两阶段不增加n。按CONFIG矩阵顺序生成稳定c00..c35标识。两个零偏差候选链标签不增加独立重复。

噪声用PCG64，SeedSequence([seed,stream_id])，range流0（54维）、motion流1（20维）；同seed在所有条件共享同一标准正态数组，几何/运动/链路/幅值/prior不参与seed派生。每条件四方法共享一个完整输入；B0省略peer，B3独有oracle是方法定义的差异。

survey：good=[1.2,1.25,1.8,1.8]，weak/near=[1.2,.25,1.8,-.2]。初值恒为survey起点，随后积分同一带噪全局位移，不再加随机初值抖动；B2初始b=0。prior中心delta=[.3,-.3,-.3,.3]只改变中心，不重建初值；无prior/改sigma不改中心、观测或初值。不同几何族还包含不同位置起点，跨族差异不能只归因锚点布局。

SEED_REGISTRY登记新观测seed和仓库/PR查重证据；这些值只登记，没有生成观测或定位。已知B 26011601..03、A 621160101..112、PR97 16101/16102及17101..17150均为暴露开发输入。bootstrap seed与观测seed用途分离。

## 求解与失败合同

P0=TRF，max_nfev300，ftol/xtol/gtol各1e-10。每个有效P0终点统一继续一次P1=TRF，max_nfev100，三容差各1e-14；尺度位置1m、b .1m。P2不在本执行器中，无择优回退、多初值搜索或按真值选择。

有效P0终点要求状态、完整残差/Jacobian、cost及原/尺度梯度均有限；不要求已被数值接受，所以预算耗尽但有效的P0仍进入P1。P0无有效终点时P1保存SKIPPED_INVALID_P0，绝不把None送入求解器。方法最终评价使用P1；P1跳过时不把P0冒充正式最终解，P0原信息仍独立保留。

完整记录分别含execution、SciPy状态/message、termination、finite各字段、hit_budget、原/尺度梯度、accepted、warnings、exception、nfev/njev、实际函数/J调用、耗时和继续前后变化。数值接受仍为SciPy success、完整数值有限、原物理||Jᵀr||∞<=1e-5。尺度梯度DᵀJᵀr只单列，不替换门槛。category按优先级区分EXCEPTION、NONFINITE、BUDGET_EXHAUSTED、NOT_STATIONARY、其他停止失败、ACCEPTED；P1跳过另列，汇总另保留P0原因，避免把上游异常隐藏在“跳过”中。

所有计划方法保留在分母。无可用有限估计时误差为null，非B2偏差误差也是null；异常对象不缺字段。有限状态且误差可计算时可以保留误差，即使未通过数值接受；这不是成功结果。局部信息SVD失败、矩阵非有限、协方差非有限或秩亏分别标记，covariance=null，不加正则或用零代替不可用协方差。有限局部逆也不是经验证的置信区间/保护级。

## 冻结统计

逐seed逐车MSE=(1/6)sum||位置误差||²，RMSE=sqrt(MSE)。各条件分别报告seed平均MSE和seed平均RMSE，不把后者与sqrt(平均MSE)混同。D_i=MSE(method)-MSE(B0)，仅双方有可用有限估计时计算；双方数值接受的D附列，不能替代主分母。B2−B1同理分别列可用配对与双方接受配对。B2记录有符号偏差误差，不给其他方法虚设偏差0。

数值失败、二维位置RMSE>.5m、|b误差|>.1m分开计数。位置同时保留逐车超阈值及两车联合二维RMSE超阈值；.5/.1仅离线诊断阈值，不是安全界。每表列planned、completed、not_completed、valid_error_count、numerical_failures、各失败类别及误差有效分母。运行未完成不伪装为已观测数值失败，也不出区间。

独立重复单位为seed。按条件/方法/车辆逐项做配对seed bootstrap，固定PCG64重采样seed=91327061，10000次，有放回重采样有效seed，取2.5%/97.5%分位数；有配对差的指标先按同seed相减再重采样。所有组按seed排序，同seed跨条件相关，禁止将条件/车辆/时间点当独立n。区间为95%逐项区间，无多重比较家族保证。

至少30个有效seed且缺失比例<=10%、该组计划运行已全部完成才给区间。否则ci95=null并明确INSUFFICIENT_VALID_SEEDS、MISSING_EXCEEDS_LIMIT或RUN_INCOMPLETE。只要有缺失，估计和区间都明确条件于有效子集，不声称全体方法优越；成功子集仅附加。没有罕见风险、实车性能或保护级保证。

## 落盘、恢复与审计

RUN.json先保存完整计划、配置/计划哈希、完整冻结HEAD、源码文件SHA和依赖版本。每输入和每方法P0/P1单独gzip JSON，禁止NaN/Inf作为JSON数值（非有限元素存null及对应非有限标记）。文件先写临时文件、fsync，再用排他链接提交；已有结果拒绝覆盖。结果根目录排他锁防并发写。

resume要求配置、模式、源码SHA、Git提交和依赖一致，只补不存在的持久阶段。已完成的异常、非有限、预算耗尽、未驻点也视为完成，绝不为选优重跑。事件日志记录开始/完成/中断/恢复及attempt；崩溃发生在阶段落盘前时允许重试该未完成阶段并标明原因。崩溃发生在结果落盘后、完成日志前时以结果文件为准，不重算。人工失败fixture和回归分目录，不能进入正式性能汇总。

summarize只读取已有输入和阶段，不调用生成器/优化器；verify独立重算可用保存状态的欧氏残差、代价和误差，并核对梯度、配置、来源和缺失语义。真实失败允许存在，不要求所有计划状态可重算；缺失记录和不可用记录分别报告。入口不生成图表，JSON表中的缺失为null，避免作图时隐式补零。

预计单进程7200方法/最多14400阶段；按小样本文件体积估计压缩数据为百MB量级，建议留6GB磁盘与4GB内存（完整汇总含两阶段J），时间预算2小时。该预算是保守规划，不是本轮测得正式耗时；可中断恢复，不因超预算筛选结果。
