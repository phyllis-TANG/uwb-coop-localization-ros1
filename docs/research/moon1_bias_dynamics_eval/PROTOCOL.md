# 时变偏差探索协议（运行前冻结）

固定起点PR117 `27b0ecf4d76124d54912d26d33432e1718dca494`。只新增两个moon1_bias_dynamics_eval目录。
完整保留PR114/117和A/B/C；formal_runs=0，无Isaac/GUI/动力学，无检测器，无PL/HCPL或风险保证。
任务一已完成并记录NUMERICAL_DIAGNOSIS；任务二源码/配置/seed/该结论一起提交冻结后执行。

## 输入与模型

优先使用已提交reference派生三个轨迹窗口，核对原gzip与固定Git提交哈希及每窗20条轨迹逐值一致。
不声称本轮重新验证NPZ→轨迹链。继承LuSNAR合成场景、同一GT五秒偏移、世界竖直1.16m天线简化。
0/8/16s各6点、dt=.2s，不改轨迹/时间。人工信标天线(-5,±12,1.16)、(55,±12,1.16)m，moon_map。
全部height-oracle，三维距离+24维XY（M2加自由常b）。运动观测为合成全局XY增量，不是真实/odom/轮速/IMU。
距离sigma=.04m，双车motion均.02m，正确独立Gaussian起点prior sigma=.5m，均研究假设而非月面实测。
先验中心与参考真值分开；初始化保持PR117：prior+观测增量累积+固定偏移，bias初值0。
M0删peer，M1不加bias，M2仅预定peer加一个自由常b，不知故障形状，不估时变bias。
普通入口只读measurements和SOLVER，严格拒绝reference/quality/注入字段。

## 条件与配对

normal=[0,0,0,0,0,0]，constant03=[.3,.3,.3,.3,.3,.3]，step03=[0,0,0,.3,.3,.3]，ramp03=[0,.06,.12,.18,.24,.30] m。
仅peer随局部时间改变；单向观测，未复制反向当独立样本。step从局部.6s开始。
十个新seed见CONFIG，审计范围见SEED_AUDIT。PCG64 SeedSequence([seed,window,stream])，range/motion/prior流0/1/2。
同窗同seed跨条件共享标准噪声、prior、初值和非peer观测；方法共享同一观测。
独立重复单位仅10个seed，不能把窗/车/时刻/360次方法调用当360个独立样本。

## 验收与预算

无优化器：距离/运动/prior/注入独立重建，配对检查，J中心差分，M0不变性，normal真值零残差及constant03 M2匹配零残差。
step/ramp在常bias真值处预期有残差，不修改模型/注入使其为零。
开发固定已暴露seed911170101、window0、四条件×三方法=12方法、最多24调用；不使用新seed提前试参。
任务一继续22调用；任务二360方法、P0最多300、P1对所有有限P0统一一次最多100，上限720。
SOLVER与NUMERICAL_DIAGNOSIS说明接受和最终端点规则。原1e−5标准保留，不用真值指标做接受。

每次优化器调用前独占锁并fsync持久化attempt：输入/配置/完整代码SHA及源码hash、阶段、起点。
已有attempt一律拒绝自动重跑，即使没有result。输出根目录必须新建；RUN_LOCK/METHOD_LOCK/阶段锁禁止并发。
假优化器验收覆盖已有结果、孤立attempt与并发拒绝；不依赖PR116或合并外部分支。
异常保留、不按错误率追加seed/曲线/窗口，不重复调容差；任务结束后不追加实验。

## 评价

逐车MSE=mean_t ||e_xy||²，RMSE=√MSE；相对误差为两车相对位置差。
benefit=MSE(M0)−MSE(Mk)，正值有利；保存全计划/有限/接受分母及双方接受配对子集，不以失败填零。
peer残差定义prediction+b−measurement，M0也计算但明确未用于优化；保存逐时刻米值及白化值。
描述后3点均值−前3点均值及时间斜率，检查剩余时间结构；这些不是检测统计量或风险阈值。
M2在step/ramp没有单一真实常bias；六点注入均值仅描述参照，bias−均值不是估计误差。
normal/constant03平移关系作数值一致性诊断，偏离须保留报告，不为强行一致重跑。
图固定第一个seed，另给全部seed散点；仅探索描述，不输出覆盖率/显著性。

## 来源与复算

FREEZE记录完整SHA、源码hash、环境、源reference哈希及继承PR114回执。继承回执是历史记录，本轮核实的是reference归档。
保存所有P0/P1端点/状态、attempt、dispatch与失败；压缩分别封装reference/measurements/estimates。
readback零优化器核验全部新结果及旧180端点和22继续端点；输出逐seed指标、残差、完整状态和图。
