# 方法与复核口径

## 固定来源及基线

读取基准`74fa210e7cf6aa322eaebce19530510edb605d22`，新检出基底main `7b67c66f2470d23f6c876f45b6543f72fab66391`；包装执行冻结提交`d78a5df`（完整HEAD见运行manifest/交付收据）。`frozen_manifest.json`固定19个基础文件，从Git对象逐文件提取到任务Git外frozen-source并在import时逐SHA拒绝不匹配。不存在静默回退到较新main。

原PR62执行提交`1595c982bc4d6206cbe3ad6ddaad774b50898766`的19个源码SHA与读取基准完全相同。旧归档`0e0156d75374cbe8e2180ef0eb36a7f282b5c59c842b6392d1ae4ae1956c8f8b`的349文件实读匹配；24个run.json、每run输入/config/输出逐SHA核验，再读取原updates进行无估计器重算的装饰导出。旧源/产物不改，明确标记`reuse_verified_original`及历史耗时。新增共同墙场景6个G0/G1及15个G2才是21次新比较回放。测试中的同输入等价回放不称旧结果复用或额外验证cell。

## 门控只改首次新peer准入

主/辅助均为固定6维联合F0图。辅助从构造开始有私有初值、状态、窗口及完整6×6 prior，peer始终None；不消费G1/G2解、prior、权重。二图共享原聚合Odom/墙距并在同一state/cutoff输出。aux接受后用两车各自yaw、XY杆臂和天线高度算3D距离，q用原peer sigma=.2m。accepted只证明本次数值求解接受，不证明墙距正确或参照可信。

q>3新peer传None，否则保留原pseudo-Huber因子；辅助未accepted/有限pose缺失、或当前Odom包围端点不足则unknown保守拒绝。无原peer聚合时优先missing。没有递归质量控制/迟滞/FSM/恢复试用/新墙策略/IMU/回滚。test_mode只存在于合同测试；45索引从未传入它，参数固定在代码与RUN_PLAN中。

原D1残差是signed pseudo-Huber，虽least_squares内部使用loss='linear'，输入已变换的残差不是普通量测平方损失。拒绝确实省去新peer残差和J行；活动窗和已形成prior中的旧因子保留。首次值一经加入不按以后分数重判。主图21联合帧126标量；G2另有同大小独立辅助图，不合为12维状态。所有零信息/缺测均不制造假距离。

每次保留实测及反向诊断、同cutoff辅助pose/完整snapshot与prior、q/unknown/missing、候选和实际factor ID、活动peer ID、prior直接peer祖先、每次消元旧墙/peer来源ID、完整before/after矩阵与affine/constant。消元来源仅记直接被消费因子；非线性状态/线性化点也会传递影响，直接祖先数不是因果效应幅度。来源追踪是外部审计记录，不反馈估计器。无peer的G0仍可保存peer诊断值，但目标函数与prior完全不消费；G2辅助的peer列表更严格始终None。

## 数据与因果

原4场景/三seed输入字节直接复制原不可变生成物。新增唯一输入适配器从同seed nominal只改Car1四墙[24,38)s +.30m，每seed1120个scalar；其余所有字段/标量/时钟/次序/真值/config逐条精确相同。nominal来源recipe/稳定消息身份保留；改后文件bytes SHA和adapter SHA在独立manifest中，不能把旧recipe当改后文件SHA。case_id也保留nominal来源身份，不被门控解析为场景。标签另存，runner只把events/config传入执行器，未读取真值/标签内容。三方法共用同一events/config bytes。

原float中心窗abs(header_s−state_s)<=.4s的边缘舍入行为也保留，不擅自改整数窗样本数；原始整数header/receive/record ID仍保存。独立回读逐窗核验已接收支持、聚合与Odom插值。辅助不是仅在最后一次求解删peer，而是从初始化起never-peer。变更peer（两方向）后其所有状态/初值/prior跨边缘化完全不变，主图会变；接收前缀测试也跨多次消元。

## 评价与分母

15场景–seed组×3方法共45单元。每单元1–63s共63次联合发布；前两次启动预测并保留，后61次accepted。all_finite包括所有有限启动/回退，joint_common_accepted按同场景/seed三个方法accepted整数epoch交集。base XY、天线XY、wrapped yaw（rad，报告另转degree）、相对天线XY向量和3D间距均用单独真值在原房间坐标评价，不做事后对齐。

pre=[3,24)、fault=[24,38)、recovery=[38,48)、late=[48,63]，样本21/14/10/16。启动另由63−61分母单列。主增量严格使用相同epoch：每方法故障RMSE−同seed nominal RMSE，及G1/G2−G0、G2−G1。不把不同时间或更小拟合残差当真值改善。异常/缺测/unknown不冒充健康，状态失败与非有限覆盖单列。

漏过同时报告状态故障段与“聚合raw支持含注入”口径。peer_bias的24/38s各有混合raw支持；38s虽仍含8/17故障raw，median主要由健康样本决定，不能称完全+1.2m漏过。未知拒绝与已知q拒绝分开，健康约束总拒绝仍包括unknown，正常2/63不能删。missing因子不计故障漏过。每窗/秒不是独立试验，3seed及同seed跨场景强相关，不能推断误报概率或低风险上界。

旧4场景原幅度+1.2m及14s窗口未改；新共同墙只+.30m。没有扩大或组合故障去逼结论，没有按真值选择阈值、权重或回滚时刻。所有后续解释均来自预定45条完整结果。

## 检查范围及代价

10项门控合同、27项冻结回归、3项索引拒绝测试、1项24cell/1512出版无重放导出测试通过。最初无.git快照导致旧CLI三项元数据测试失败，全部日志保留；换到19文件SHA完全相同的独立Git检出后通过，不是算法修复或阈值调整。旧原有测试fixture不计作新增矩阵种子/场景搜索。

独立evaluate.py不导入graph/frontend/probe/legacy/scipy.optimize，只使用文件格式与原独立标量方程重算分数、3D天线几何、目标和有限差分Schur；全部45个运行SHA、2835窗、945辅助=G0状态/prior、876已知q、3660接受目标代价及3780逐图prior链通过。总2520次实际边缘化，仅抽各图首末共120次独立FD，不能说全2520独立重算。完整索引负测试拒绝空/缺失/重复/额外/FAILED/PLANNED，DONE子集不能冒称全集。

update_wall/主图与辅助成本是本机实测，但发布截止/估计队列均virtual。原emit测时不含两Binner的聚合和全部I/O，最终run元数据写出也在elapsed之后；整cell回放与日志的实测wall另列。复用G0/G1的旧计时不能同当前G2当作同期受控速度实验。辅助正常累计约.51s/63发布是明确新增成本，不宣称实时性或硬件部署。未启动/停止任何既有ROS、rosbag、串口或实车设置。

独立读器v2另增加侧车标签/适配器逐scalar核验（3360次改动）及归档迁移路径解析，未改任何估计器/结果；与v1六份数值表逐字节一致，v1源码和结果均保留。完整目录迁移后的回读不依赖index中记录的原主机绝对路径，原manifest SHA不被重写。所有8张同期图见FIGURES.md。
