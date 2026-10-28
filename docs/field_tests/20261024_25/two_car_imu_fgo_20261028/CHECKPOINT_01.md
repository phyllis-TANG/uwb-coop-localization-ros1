# 现场与预登记检查点

启动 2026-10-28 06:24 UTC；硬截止12:24 UTC。桌面《双车IMU接入指令.txt》完整读取，执行本轮双车授权，不消费PR67讨论稿。

新检出 `/home/ubuntu22/uwb-two-car-imu-fgo-20261028`，分支 `feat/20261028-two-car-imu-fgo`，起始HEAD/main `ca8fbac4dbdf678074be5fb80bf6aff472d258e6`，初始status为空。原检出 `/home/ubuntu22/双车协同/uwb-coop-localization-ros1` HEAD `115b17deb2f848e596d1638a0b45cf360deae947` 分支experiment/two-car-independent-integrity-bridge-20261023，干净未切换。祖先/仓库无适用AGENTS.md。

已有ROS/rosbag PID59092/59721/59735/61095/61169及其他Codex工作均不改动；无本任务估计器进程，不重复启动。磁盘可用22GB，内存available19GiB。Python3.10.12 / NumPy2.2.6 / SciPy1.15.3 / matplotlib3.10.9；BLAS/OMP固定单线程。依赖使用已有Git外环境，不更改共享依赖。

仅新增tools/two_car_imu_fgo/与本目录。输出与TMPDIR为新Git外目录`/home/ubuntu22/uwb-two-car-imu-fgo-20261028-artifacts`。不下载视频，不读留出包，不改公共几何、旧代码、bag及结果。不启动ROS/串口。

执行顺序：来源阅读/字段就绪→合同测试→冻结源码/参数/输入/40索引→完整合成→阶段A交接→两旧双车包→阶段B门槛→仅T08/T10。缺几何/时间证据的严格物理分支BLOCKED；显式数值候选可另登记conditional_development，不写精度验收。

合成场景/seed：nominal、gyro_constant_bias、car1_gyro_gap、peer_bias、car1_common_wall_bias；101/211；每案M0/M1/M2/M3共40。保留64s、20Hz旧轨迹/测距/odom噪声、[24,38)s原故障窗、peer+1.2m/Car1四墙+.30m。gyro从原独立轨迹产生，发布白噪声sigma=.006rad/s（单车生成器），两车不同恒偏+.025/−.015rad/s从初始化全程；Car1缺口[24,38)s。各场景共用随机数组，不扩大场景/种子/幅度。

新角参数完全沿用单车F3：角噪声密度2deg/sqrt(s)，bias初值0、sigma .03rad/s，RW .0007(rad/s)/sqrt(s)，100ms左保持上限。单位/轴/时钟逐车声明。M0/M1六维无bias=null，M2/M3八维。gyro替代所有预测与角边，缺角保持初猜且无yaw因子，不回退odom yaw；原odom yaw仍表达body平移。

预定数值容差（看本轮结果前）：关闭路径非计时数值完全相等；M2与独立F3目标H/g/c绝对1e-7/相对1e-9、固定同线性化状态一致，解位置/yaw1e-4、bias1e-5（独立/联合停止差异单列）；解析Jacobian FD步长1e-6，绝对/相对3e-6；Schur H绝对1e-5/相对1e-8、g1e-6/1e-8、二次cost1e-6；gyro积分1e-12rad，prefix非计时语义完全相等。未知不置0，不按结果放宽。

旧包原bag在仓库只读可用；已有清点数值初值/杆臂及bag接收关联候选，严格外参/物理同步未验收。T08/T10复用已有缓存与审计，核SHA后才适配，不复制其他场次模型或P1。字段来源/条件配置在实包执行前独立冻结。
