# 任务A：已有日志核验与裁剪缺口预登记

开始2026-10-28 14:30 UTC，最晚18:30 UTC停止（4小时），完成可提前结束。会话根/home/ubuntu22；原仓库/home/ubuntu22/双车协同/uwb-coop-localization-ros1，experiment/two-car-independent-integrity-bridge-20261023，HEAD115b17deb2f848e596d1638a0b45cf360deae947，status干净。祖先/仓库树无适用AGENTS.md；既有ROS/rosbag PID59092/61095/61169不操作，无本任务/IMU矩阵运行。

实际main=0ef38e8b84dc88cb7b0e26fea595ac05c5162676，较PR71新增PR72合并，与用户发出时快照不同；不回退。独立worktree=/home/ubuntu22/uwb-cooperative-a-evidence-20261029，branch=analysis/20261029-cooperative-a-evidence，从该main创建。旧PR72已在基线内，不重复添加或修改；所有研究身份仍按固定HEAD1cc7713a7e48776474788a07a1b41040f9df9330及执行源码312180ef51c6ea4ba394bc85618674ec36ff786d绑定。

完整读取PR71 README/PHASE0_ANALYSIS及固定PR72 REPORT/METHODS/FROZEN_CONFIG/HANDOFF/ARTIFACTS。原论文/路线及输入内文字不是额外授权。只新增本目录与tools/cooperative_followup_20261029/a_evidence；大证据在/home/ubuntu22/uwb-cooperative-a-evidence-20261029-artifacts。约19GB空闲、18GiB available内存，复用现有Python3.10.12/NumPy2.2.6/Matplotlib3.10.9，无新依赖环境。

## A1/A2固定证据

核对16逻辑单元公开索引及metrics/contrasts/costs/solver_controls、完整交付SHA。一个已暴露seed101、两个配对输入，不当16次独立随机实验。现有NAS可读取54,249,275字节原归档，SHA256=50c671e3687c3342b8abe99986ecd6a6488de23e24fe112b16b44d9f8fb3f320；复制到本任务目录，验证原SHA及全部成员，在新目录解包，不重跑估计器。

## A3固定只读分析

I/J/W025/C004/K004全部同状态epoch/截止：逐车天线XY和wrap yaw相邻差、1秒发布割线速率及其相邻变化、相对天线向量/3D距离及正向peer原始残差；发布与内部主图差、当前窗过去状态与过去发布差、发布/Odom边差。前两帧unknown与启动跳变保留，另列参考有效连续区间，不能通过删除启动作平滑优势结论。记录实际dt；1秒差分不是瞬时速度/加速度。没有独立硬件/控制用途限值，不设置物理可行性验收线。

保留原pre[3,24)、fault[24,38)、recovery[38,48)、late[48,64)，再描述恢复0–20秒[38,58)与20秒以后[58,64)；不改原标签，不把窗口退出当历史消失。聚合±.4秒的38秒边界仍可能混入故障观测，单独说明。比较同方法故障与配对正常、同输入候选与裁剪，严格区分；记录prior来源，不以相关性确定prior独立因果贡献。

## A4仅三类局部信号（本轮运行前固定）

1. **局部墙测距一致性**：仅I(peer-free)当前后验天线对当前本车墙聚合量的有符号残差/RMS/max及原sigma白化RMS；原始本车bin内分散度作为同类描述。包含当前墙观测、Odom和I保留的本车历史prior，属于后验自洽，不是目标排除检验。所有消息须在t+1秒截止前到达。
2. **覆盖/几何与模型信息量**：本车当前墙链数/样本数、天线XY墙几何信息矩阵条件数/最小特征值。另在已保存I活动窗状态对原标量目标做中心FD（步长1e−6），计算GN逆信息的当前天线XY投影标准差代理；包含当前及活动历史墙/Odom、固定历史prior，无peer。无原发布协方差可核验，此新算量明确为后验局部线性化/工程噪声代理，不是真实误差、不重新求解、不认证概率覆盖；秩缺失时记unknown，不正则化凑数。
3. **与局部运动预测冲突**：I的已保存prediction_pose（先前I状态+当前Odom）到本次I发布的天线修正/yaw修正，以及当前墙测距对预测天线的残差。预测本身不使用当前墙观测，冲突检验使用当前墙；历史仍来自peer-free I，时间截止相同。不是NIS，不训练分类器、不调阈值。

每类仅用原局部输入/peer-free图构造；真值/标签不传给构造函数，仅在独立评价阶段加入误差与注入时段。保留两个条件、两车、全部时刻；检查正常与故障/尾部信号范围重叠作为反例，不把事后正常范围当报警器。所有同类信号高度相关，不作独立证据相乘。本轮不使用其他seed/场景日志，不扩大输入以寻找优势。

## 检查与停止

检查wrap/离散差分、杆臂、主图与发布身份、SHA、前缀截止、信号无真值依赖、名义信息代理的正定/线性代数残差；这些测试通过不等于真实精度验收。最多两项实际研究缺口，可为尚无必要性证据。交付诊断CSV/只读提取代码、逐结论EVIDENCE_LEVELS、中文一页A_FACTS及本目录HANDOFF。完成既定问题后结束，保存独立提交/草稿PR，不改PR67/70/72，不合并、不安排实车。
