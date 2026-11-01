# 双车传感器级开发入口（2026-11-01）

只启用已暴露开发 seed7。无 ROS、bag、视频、机器人连接。原工具只读，8维监测缺项见 `docs/research/two_car_sim_dev_20261101/REUSE_AND_GAPS.md`。本工具没有正式矩阵驱动器，不能通过 `development_only=false` 或换测试种子进入正式执行。

`generate.py` 写出确定性 events/config，以及独立保存的 truth/labels/generation/manifest。运行器只接收 events/config。二维 base XY/yaw，通过杆臂及天线高度计算三维墙/peer UWB。轨迹指定天线XY；默认固定 F=(1.5,4)，运动 A=(2,2)→B=(2.75,2)→C=(3.5,2)→A。参考点约定尚须本地确认。分段三次 smoothstep、独立设计yaw，不宣称非完整车辆动力学。双移动配置只作准备，未运行正式运动矩阵。

默认32秒、20Hz；故障 `[6,20)` 仅开发短例，对选定车四墙共同+.30m，peer不变。28秒注入需更长且显式配置的轨迹，短配置会拒绝越界，不能静默裁短。两车的 `trajectories` 是双移动设计；一静一动使用 car2 路径槽，`fixed_car` 可切换。噪声及初值为开发假设，详见配置和正式合同模板；没有新现场标定。

生成器 noise 的 wall fractions 按方差分解：每墙独立项 `sqrt(1-pv-pn)*epsilon`、本车共同项 `sqrt(pv)*v`、跨车共同项 `sqrt(pn)*n`，全乘 range_sigma。默认pv=pn=0，时间白噪声。peer双向噪声分别独立，只有car1→car2进图；gyro白噪声与Odom增量原始抽样独立，但Odom使用其自身测量yaw表达平移，因此不能将所有派生量当独立。gyro bias 为明确初值加RW；不输出bias给估计器。噪声标准差与估计器工程权重不同，后者原样继承。

`adapter.py` 复用M2/M3；M3W025克隆函数命名空间，用相同.25代价权重同时构造优化与消元目标，不修改原模块全局。残差/J各乘.5；完整8列QR、offset/constant和跨车/角度/bias相关保留。运行器会原样保存活动图、每次消元和gyro支持。B1纯四墙统计共享同一bins；所有阈值未校准，B1/B2 local/network都unknown。禁止把零 observed alarm 解释为零FAR。

`readback.py` 只调用原独立标量方程，加独立外乘权重后用有限差分/SVD核对所有保存的消元H/g/常数、代价和接收/gyro支持；不导入在线优化器。`evaluate.py` 不导入生成器或内核；绑定输入及结果SHA后，按完整run/每车及相同输入reference计算误差、协同配对差、unknown/失败/报警和三档AL的暴露。恢复判据未冻结，恢复时间保持null。工程state-hold时长不当独立帧试验/理论风险。

运行命令、实际检查和HANDOFF在同名 docs 目录。所有输出必须使用全新Git外目录。依赖 `numpy==2.2.6 scipy==1.15.3`，BLAS/OMP线程1。各CLI为独立Python进程使用；旧绝对导入模块名的进程内任意混装不属于本轮适配。
