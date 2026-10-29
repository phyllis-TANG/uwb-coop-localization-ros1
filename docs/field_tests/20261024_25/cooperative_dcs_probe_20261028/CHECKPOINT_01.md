# 现场、复用与预登记检查点

2026-10-28 07:58 UTC启动，预算截止10:58 UTC。完整读取桌面《最小DCS对照任务书_20261028.txt》，适用祖先/仓库无AGENTS.md。旧检出/home/ubuntu22/双车协同/uwb-coop-localization-ros1干净，分支experiment/two-car-independent-integrity-bridge-20261023，HEAD115b17deb2f848e596d1638a0b45cf360deae947，未切换。远端main实查ca8fbac4dbdf678074be5fb80bf6aff472d258e6。新独立检出/home/ubuntu22/uwb-peer-dcs-minimal-20261028，分支analysis/20261028-peer-dcs-minimal，从该main开始。

未发现同等DCS分支/产物/运行检查点。本机已有ROS/rosbag PID59092/61095/61169等持续运行但不操作；无本任务或双车IMU矩阵进程。磁盘21GB可用、内存18GiB available。已有外部Python3.10.12、NumPy2.2.6、SciPy1.15.3、matplotlib3.10.9；BLAS/OMP单线程。输出/TMPDIR=/home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts，本轮只新建tools/cooperative_dcs_probe_20261028及本目录。不推送/建PR/合并，不动PR67或已有IMU工作。

PR68本机完整归档a1c75087eb2a54ff0512e2065cca770d45f5b7d26dabf0e27d3d474c0f52a26f及matrix-v1、15份输入可读取；本轮只取nominal/peer_bias/car1_common_wall_bias与seed101/211/307。核对19基础文件、门控执行源码、输入/config与逐产物SHA一致后复用27个G0/G1/G2，重命名为D0/D1/D2仅发生在本轮评价层，不改原日志。只新增D3九单元；不读原bag/视频，不取其他故障或seed。

作者完整PDF已下载，SHA256 8df24f26e04f29e2ab3fcfeffc772b53b111b53f7bd8a9e1d903203a2327c6eb。核对III–IV节/式15及V.A默认Phi=1，**在任何D3场景结果前固定Phi=1**，不按已有故障表现选参数。工程sigma沿用.2m，Phi作用于未鲁棒白化残差平方。此为标量peer DCS适配，不宣称SLAM实验完整复现或误报概率。

实现先核验：名义peer几何/Jacobian；s与s²；连续鲁棒积分目标梯度与IRLS正半定曲率；SciPy TRF接受准则与真实目标下降；关闭peer→原D0，关闭DCS→名义peer，D0–D2回归；收前缀跨消元、全cross/affine/常数、保留因子不双算。拟使用原TRF/exact和50次/1e−7停止，只有peer从pseudo-Huber改为每次线性化DCS，不改变墙/Odom/前端。

预登记容差：D0–D2非计时数值逐值相等；名义几何J中心FD步长1e−6，atol/rtol3e−6；DCS目标梯度FD atol/rtol3e−6；加权GN H/g代数atol1e−10/rtol1e−10；Schur H atol1e−5/rtol1e−8、g1e−6/1e−8、常数1e−6；prefix非计时语义逐值相等。所有容差不按结果放宽。通过后本地提交源码、冻结配置/输入/36索引再执行D3九条。

评价每车base/天线XY、yaw、相对位置与斜距；全部有限、每车有限/accepted、四组共同accepted并列。pre[3,24)、fault[24,38)、recovery[38,48)、late[48,63]，另含启动全程。严格区分同故障输入D1/D2/D3−D0与同方法故障−同seed nominal。成本注明旧时机复用，不与新D3作同期速度结论。真值/故障标签只读入独立评价器。无新门控、IMU、回滚、DECLARE或完整性声明。
