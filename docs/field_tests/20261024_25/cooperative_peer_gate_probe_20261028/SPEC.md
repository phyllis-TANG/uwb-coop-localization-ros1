# 双车普通目标排除门控：开发预登记

固定读取基准`74fa210e7cf6aa322eaebce19530510edb605d22`；本分支只新增指定两个目录。研究问题是已有pseudo-Huber之外的普通门控是否足以处理本有限故障传播，以及墙距有偏时参照的代价；不是新算法。

G0=冻结D0；G1=冻结D1（已有pseudo-Huber）；G2=原G1加一次新peer因子首次入图前的二元门控。阈值硬编码q>3拒绝，否则保留，q=abs(本帧Car1→Car2中位数peer−独立G0辅助预测斜距)/原sigma .2m。不得用后验主图或受检peer反算参照。

辅助图从初始化起与主图各自独立先验、状态和20s边缘化，辅助update的peer始终None，永不消费主图状态/先验/权重。只共享冻结聚合后的原始两车Odom/墙距与当前接收截止。辅助未accepted、缺当前两车Odom包围端点或无有限两车天线预测时unknown，拒绝本次新peer；没有原peer聚合时missing优先单列，不制造测距。无附加墙链门控、几何阈值、迟滞、恢复FSM、在线可信性或回滚。本来受先验/墙/Odom支持的accepted辅助解仍只是工程参照，不把accepted解释为无偏/真值。

实现用自目录包装冻结JointReplay/WindowGraph，仅在G2 graph.update前运行独立辅助并将拒绝的新peer传为None。保持原1s等待、方向、sigma、六维联合状态、20s窗口、外参、原float中心窗/中位数和完整QR prior。既有peer及prior不重判、不删除、不清零；测距与真实实际入图值分开记录。G0/G1原实现保持原数值路径。测试用allow_all/reject_all仅是合同测试，不作为可调方法/运行参数。

输入：原生成器与旧归档，seeds101/211/307固定且已暴露。4原场景nominal、peer_bias（Car1方向+1.2m）、wall_bias（Car1 node2 +1.2m）、peer_gap，均原[24,38)s；新增唯一场景car1_common_wall_bias：从同seed nominal原事件复制，只在[24,38)s对Car1四墙同时+.30m。其余每个scalar/时钟/身份/次序/配置/真值完全相同。保留nominal来源身份并在独立manifest声明adapter与新文件字节SHA，不把改动文件说成原文件。真值/标签仅独立评价器读取，不进入在线主/辅助图。

矩阵固定5×3×3=45条。新输入/完整索引/源码SHA在测试通过后冻结，任何缺失/重复/额外/失败不得以子集通过宣称45条完成。所有原24条如源码/输入/配置/输出SHA精确匹配则复用并注明历史耗时；不能复用则先登记受控复现，不称复用。测试不是扩展场景/种子搜索。顺序先seed101 nominal及peer_bias六条检查点，再按冻结索引其余；不按结果选seed、不扩大故障。

评价：按原state_epoch_ns精确关联，全部有限发布（含1/2s启动）、三方法共同accepted时刻分别报告；不对齐轨迹。每车base XY与天线XY、wrapped yaw；相对天线XY向量和三维间距。分段all全63发布、pre=[3,24)、fault=[24,38)、recovery=[38,48)、late=[48,63]。状态失败、缺Odom、启动、missing、unknown、available均给分母。不把原14s缺测当14个空窗，边界聚合按实际raw支持。

健康同伴Car2增量：每个方法故障场景RMSE−同seed nominal在完全相同epoch上的RMSE；另给G1/G2−G0和正常代价。对两辆都直接连接peer_bias影响的车仍称未直接改墙/Odom，不宣称未受故障量测连接。健康peer误拒绝/故障peer漏过同时按“聚合支持含注入raw”与“状态位于故障段”给分母；unknown拒绝与已知q>3分开，不把missing当漏检/故障。相关窗口/链秒均非独立试验。

真实计算仅测本机wall耗时：G2分开辅助/主图、加总更新和整cell I/O；G0/G1复用历史成本标记不可直接当同期受控速度对比。所有发布队列时刻为virtual，不写成实车实时延迟。同期留score、辅助pose/prediction/私有prior、准入、实际peer ID、活跃窗口、prior前后链/消费ID/交叉与affine。不用拟合残差代替真值误差。

必要先验测试：G0/G1同冻结原实现数值一致；单位准入=G1，全拒绝=G0（含边缘化），missing不造数据；只改peer时辅助初值/状态/prior至少跨20s不变而主图可变；receive-prefix不可回写；拒绝确实删除新目标残差/J行；每peer至多消费一次、保留完整cross/offset/constant。数值等价不通过则不运行/不解释矩阵。版本失败日志/源码保留，新版本另目录。

不得引入IMU、墙策略、oracle阈值/回滚时刻，或把本普通基线称为原创/完整性保障。结果出现或未出现都如实报告。总截止见CHECKPOINT_01，届时完成子集如实交接。
