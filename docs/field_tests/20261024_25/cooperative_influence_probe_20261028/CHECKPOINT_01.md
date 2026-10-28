# 首轮现场、归属和预登记

2026-10-28 UTC。原检出/home/ubuntu22/双车协同/uwb-coop-localization-ros1，experiment/two-car-independent-integrity-bridge-20261023，115b17deb2f848e596d1638a0b45cf360deae947，status干净；未切换。远端main与PR71均aa6d272f9dcb7180d7548a06cb11d5d28445b2dd。新worktree=/home/ubuntu22/uwb-cooperative-influence-minimal-20261028，analysis/20261028-cooperative-influence-minimal，初始HEAD=该main，干净。祖先及仓库未找到AGENTS.md。原ROS/rosbag PID59092/61095/61169等不操作，无本任务或IMU矩阵进程。空间约20GB，available内存19GiB。Python3.10.12、NumPy2.2.6、SciPy1.15.3、matplotlib3.10.9，既有隔离venv，单线程BLAS/OMP。

完整读取PR71 README、定题与执行路线_v1.txt、PHASE0_ANALYSIS.md及解析程序。PR70只从指定d946bdcb457f7f51f93a116a359dcabf7647134c读取报告/源码锁和已有归档，未假定合入main。19个F0与10个门控源文件逐SHA仍相同。冻结旧F0不含IMU，公共模型/几何/manifest及其他目录不改。

归属仅tools/cooperative_influence_probe_20261028/与本docs目录；日志/TMP在Git外/home/ubuntu22/uwb-cooperative-influence-minimal-20261028-artifacts/。保护原始数据、旧归档和其他worktree。允许本分支提交推送、草稿PR；不自动合并，不实车/ROS，不下载bag/video，不动PR67/70。

只使用seed101的nominal和car1_common_wall_bias两个已暴露输入，沿用四墙+.30m、[24,38)与原恢复/late分段。固定信息权.25，乘在原pseudo-Huber残差外即残差/J乘.5，不改sigma。预算.04m沿PR71解释例，1m为故意宽松的关闭近似检查，均非论文主预算，不从结果调参。

16逻辑单元：每case I=独立原F0、J=原联合、W025=固定缩权、U=同SLSQP关闭控制、C004/C100=原J事后天线XY裁剪、K004/K100=图内当前天线XY预算约束。I/J共4条复用；C共4条仅从已保存解派生；W/U/K共8条新主图。每条新主图同时更新自己的私有G0参照（两车独立块），从初始化起不使用peer/main输入，不反馈裁剪/回退发布。不得依结果增加seed或预算。已有G2/DCS仅为先前机制背景，不加入本轮新矩阵。

SLSQP采用原完整pseudo-Huber目标及解析梯度，maxiter300、ftol1e−9、每次求解wall预算2秒；原TRF路径保持不动，U揭示换求解器差异。K只约束当前输出帧的旋转杆臂后天线XY，两车同预算。可行性以实际发布坐标复查，容差1e−7m。约束是本次允许位置的集合，不作为新增虚构量测或历史信息因子；旧状态、所有原因子及完整cross/affine prior保持，约束引起的历史线性化变化保留。无协方差输出，不声称任何裁剪/约束为一致联合后验。

输出合同：参照accepted且候选成功/预算通过才normal_joint；候选失败、超时或事后超预算时仅发布完整参照状态并记reference_fallback，joint_optimization_success=false；若参照未accepted/不可用则unknown，有限启动预测可单独发布但无预算认证；缺Odom未发布，不填0。内部图仍保留原状态/prior，不把回退/裁剪塞回图。启动、unknown、超时、solver_failure、budget_rejected逐条保留。2秒只是离线工程求解截止，不是实车时延保证。

预登记合同：参照peer扰动/主状态污染跨20秒边缘化不变；旧I/J回归；同solver关闭约束与原TRF的小例姿态1e−4m/rad、目标相对1e−6；实际天线XY约束/J中心FD1e−6、atol/rtol3e−6；完整Schur H atol3e−6、g/常数2e−6、rtol2e−6；prefix非计时语义精确；权0不清prior、保留因素不双算；unknown/超时/失败回退；PR71对称一维数值约束与裁剪等价。源码/测试/输入/配置与16完整索引冻结后再运行，开发失败另存版本，不按结果放宽容差。
