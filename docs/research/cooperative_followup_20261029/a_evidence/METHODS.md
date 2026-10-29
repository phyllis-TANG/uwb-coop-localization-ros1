# 证据读取合同与列口径

## 固定身份、归属

实际基线main=`0ef38e8b84dc88cb7b0e26fea595ac05c5162676`，包含PR71及之后的PR72合并，与任务下发时“PR72未合并”的快照不同。新增变化只涉及PR72专属目录；本轮不回退，不改其内容。研究读取严格固定PR72 HEAD `1cc7713a7e48776474788a07a1b41040f9df9330`，原执行源码`312180ef51c6ea4ba394bc85618674ec36ff786d`。原矩阵配置及所有输入身份见[ARCHIVE_CHECK](checks/ARCHIVE_CHECK.json)，运行索引身份见[PUBLIC_CHECK](checks/PUBLIC_CHECK.json)。

工作树`/home/ubuntu22/uwb-cooperative-a-evidence-20261029`，分支`analysis/20261029-cooperative-a-evidence`；只新增本目录和`tools/cooperative_followup_20261029/a_evidence`。源仓库分支`experiment/two-car-independent-integrity-bridge-20261023`及HEAD `115b17deb2f848e596d1638a0b45cf360deae947`未改。现场祖先/仓库树无适用AGENTS；按Linux任务输出目录保存大证据，无ROS/串口/实车操作。8项测试是读取/数学/身份检查，不是精度验收。

输入不变：seed101，nominal及Car1共同墙偏差；四墙+0.30m、原故障时段，peer正常。归档的输入SHA完全绑定原索引，没有新增生成、重放或轨迹解。I/J/W025/C004/K004为详细分析对象；U/C100/K100仅读回原公开表和数值路径对照，不添加运行。

## 原始证据及读取深度

`prepare.py`以git show读取固定HEAD公开文件，与原DELIVERY_FILES_SHA256比较；新目录复制并校验NAS归档与manifest、239成员、源码/输入/run输出SHA，验证公开表和归档表字节一致。元数据和16单元身份通过，不将它们当独立随机实验。

`extract.py`读取各`updates.jsonl.gz`的pose、main_pose、prediction_pose、snapshot、prior、bins和provenance，独立用旋转杆臂求天线三维位置，逐时刻计算错误/差分；320行metrics、480行contrasts、12行solver_controls全字段数值/分母重算通过（metrics最大绝对差0）。16行cost状态数重算，耗时数值仅身份校验。

`summarize.py`验证C径向投影、C/J快照及yaw身份、K发布=主图末帧，跟踪边缘化prior ID链及实际配对bin差异；只作表/图。`audit_semantics.py`额外读U/J和K/C的yaw差，记录原run输出清单；无独立实车发布包，发布一词仅指原离线sink的pose。

没有导入在线graph、frontend、core、optimizer/Jacobian。**共享部分**：从SHA锁定归档导入原`tools/two_car_fixed_lag_fgo_v1/audit.py`（SHA `d5c2479c5428f12f44800315ed932f77e6d9f3f5c9fd4e85aef7e5f540eeecb4`），复用它的独立标量残差、中心有限差分和bin校验。它不是在线求解器，但本轮GN量不算另一套完全独立模型实现；保存的prior数值也是共享输入，未重建历史非线性解。

## 三类局部信号

预登记提交`5d9256bf84fec445792082d3fe03228af5455a45`先于计算。`construct_local`只接收I行、本车原始UWB流和冻结模型；I snapshot peer_enabled=false，全历史peer因子集合为空，本车prior交叉块为0。构造函数不读真值、标签、联合解或peer测距，测试改变这些字段及截止后消息不影响输出。独立图在原六维路径中的共享数值停止可能产生极小浮点差，不当独立物理传播。

|类别|量|当前墙观测|历史依赖与时刻|
|---|---|---|---|
|1 墙一致性|当前后验原始距离残差均值/RMS/max、除原sigma=0.20m的RMS、bin内MAD|包含；是后验自洽，非排除目标检验|I当前状态已使用当前墙/Odom及本车prior；墙bin中心t±0.4s，仅收receive≤t+1s的支持|
|2 覆盖/几何/信息量|墙链/样本数、墙XY几何信息特征值/条件数；当前天线XY的GN逆信息代理|包含|当前和活动窗历史墙/Odom、I完整本车历史prior；没有peer历史|
|3 预测冲突|prediction_pose到I发布的天线修正/wrap yaw修正、当前墙对预测的RMS|预测本身不含当前墙，冲突计算包含当前墙|上一I状态+本次Odom预测，继承先前本车墙/Odom/prior；相同截止|

信息代理计算：在保存状态x上，用标量残差r（含原pseudo-Huber墙残差变换）中心FD `eps=1e-6`得到J，H=JᵀJ，A为末帧两车天线XY对整窗状态的几何Jacobian，P=A H⁻¹ Aᵀ，每车导出√trace(Pii)。它是残差变换的GN局部逆信息代理，不是精确Hessian、实际发布协方差、经标定噪声或保护级。检验H满秩、P正定、线性解相对残差<1e−7；无正则化凑数。122个accepted完整窗分别得两车244行代理，另8行启动proxy缺失。EXTRACTION_CHECK中历史字段`GN_proxy_computations=244`按**车行**计，非244次完整窗计算。

`wall_only_xy_trace_sigma_proxy_m`仅根据当前墙几何和名义sigma，同样不是状态估计协方差。全时序无原系统协方差可作概率校验。t=1,2未accepted，GN为空/JSON null，其他已知描述量保留并显式标状态。真值和故障注入时段仅在`local_signals_offline_join.csv`加入，既不反传信号函数，也不作在线决策。范围重叠是事后描述，不设置报警阈值；保留t≥3与t≥4两口径。

## diagnostics.csv主要列与单位

行键为scenario/method/car/state_epoch_ns（整数ns），cutoff_epoch_ns同为整数ns，t_s状态相对秒。一个共享peer/相对量在两车行重复，不增加样本量。

- finite/reference_accepted/publication_mode/main_success/joint_success/reason：有限发布、参照有效、模式、内部求解、联合成功分别记录；post_clip不计联合成功。
- antenna_x/y_m、yaw_rad：最终虚拟发布；true_error_xy_m为天线XY误差范数，true_error_yaw_rad为wrap有符号误差。相对x/y为a1−a2；antenna_distance_m为3D距离；distance_error_m为与真值距离的有符号差。
- peer_residual_published_m/peer_residual_main_m：原始未白化的预测3D距离减规定方向peer中位数；真值不参与。
- main_to_publish_xy_m/main_to_publish_yaw_rad：同状态最终发布与内部主图的差；separation_from_I_m以同状态I为中心，不是真误差。
- publish_step_xy_m：相邻发布天线XY位移范数；secant_vx/vy/speed按实际sample_dt_s相除；publish_rate_change_mps2为相邻割线速度向量差再除dt。此数据dt=1s，不能称瞬时物理速度/加速度。yaw相邻差先wrap。
- reference_pair_valid要求相邻两帧I均accepted；reference_triplet_valid要求三帧均accepted；summary中的reference_pair_valid口径对速率变化进一步检查triplet，其他量保留全部60对。all_recorded保留62个相邻差、61个速率变化含启动。
- published_odom_body_conflict_m：两次发布的底盘位姿车体系平移减对应Odom车体系平移之范数；internal_odom_body_conflict_m用当前snapshot内相邻状态。不是动力学可行性验收。
- window_previous_vs_previous_publication_xy_m：本次窗口的上一状态与上次发布差，包含正常平滑修正；clip_offset_change_m仅为两次“发布−主图”偏移的向量变化。
- local_*：同epoch/截止的I局部信号附带列，I结果被五方法共享，不是五次独立局部试验。
- prior_peer_n/window_peer_n、window_start_s、prior_cross_norm：原日志来源集合数量及矩阵交叉块描述，不代表影响大小。history_readback额外记录prior ID和累计被消费的配对改动墙因子数。无清除/回滚。

CSV缺失值一律空，JSON未知一律null；已知的零仍是0，不伪造不存在的bias/covariance。本轮F0无bias估计，不新增bias列。未输出置信度或报警器。

## 版本与限制

首次CLI漏传--evidence仅usage退出；随后analysis-v1因离线真值字典被同名列表覆盖而停止，只有已算局部CSV，无结果结论。修复提交`cb1b67b`，analysis-v2通过，原目录/失败日志保留。summary-v1中见证表把整数ns写成float表示，summary-v2改用整数并新增任意1ns精度测试；本数据整数秒的数值未变，v1未覆盖。最终8项测试通过。工具保存点`57fce43f1ebc6cc7bb1a34cb5d40567be92506d0`，各执行读器SHA以checks及交付清单为准；后增--archive和TASK_A_ARTIFACTS只改善路径可移植性，未改计算。

只有原两条件及一个seed；不开展估计器干预，不识别各历史来源的独立因果份额，不评价实际控制器/硬件，不声称新算法贡献或完整性保证。
