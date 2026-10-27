# 单车20秒固定窗口IMU规格 v1（实现前）

起点112586ceb9ce674a083fb43f7d8afb7768a15aaf，FGO_REDIRECT覆盖旧EKF主线。独立分支analysis/20261027-single-car-imu-fgo；只写本目录与tools/single_car_imu_fgo，不改原三入口、原协议、原结果或B目录。PR57已合并，草稿PR目标main。旧EKF保存在310c815dcf95e69368c7787b8303c3ddaca646cf，37完成+1部分输出，禁止继续批处理。

F0直接运行原FixedLagReplay/WindowGraph，默认关闭新功能。F1/F2仍优化3维位姿，bias固定0；F3优化每帧[x,y,yaw,b]。继承原1秒关键帧、20秒窗口、1秒发布等待、±0.4秒range中位数、至少5样本/链路、P1 raw减一次、伪Huber量测变换、原Odom平移因子和初始外部位置/朝向。合成真起点相对该共同先验均值另加0.10m/0.10m/3deg标准差扰动，Odom源pose从[0,0,0]开始，初值不当无误差真值。F3最多21帧=84个标量，瞬时22帧=88个标量；F0–F2为63/66个标量。没有EKF、加速度双积分或IMU姿态因子。

F1使用Odom.angular_z，F2使用显式轴映射的IMU gyro且bias固定0，F3相同gyro并估计残余bias。角积分采用源时刻左保持，单样本最长保持100ms；源/接收均为整数ns，只有本次t+1s cutoff前到达的记录可见。积分[a,b]不使用source>a的记录反向积分前段，不需要未来右端点；下一源记录只分割保持段。没有覆盖的时间显式gap且本边不加角因子，不部分拼接冒充完整增量，迟到记录不能回写已发布输出。完整边记录所有源身份、区间、角增量和gap。

F3采用左端bias恒定均值近似：e_angle=wrap(yaw_j-yaw_i-alpha+b_i*dt)，e_bias=b_j-b_i。连续bias RW q_b在该间隔的联合协方差为[[q_g dt+q_b dt^3/3,-q_b dt^2/2],[-q_b dt^2/2,q_b dt]]，Cholesky联合白化，保留yaw/bias噪声相关。瞬时UWB H_b=0。初始bias0±0.03rad/s；q_b=(.0007(rad/s)/sqrt(s))²，F1/F2/F3共同q_g=(2deg/sqrt(s))²，均为冻结工程假设，非厂家协方差标定。缺角边仅保留bias RW，绝不加隐含零角度量测。

原Odom平移仍用R(-local_yaw_i)*(local_xy_j-local_xy_i)，此处依赖旧Odom航向表达、可能与gyro共享上游，明确不声称独立。新关键帧的yaw预测只来自当前角积分减左端bias；缺积分时只把上次yaw保持为优化初值，并标记missing_angular_hold_initial_guess。启动yaw来自同一外部初始朝向，失败时保留该同模式预测，不调用旧predict的Odom yaw。aligned_odom字段仅为沿用诊断，不参与新yaw初值/因子/失败回退。默认无Odom角回退；若未来允许，必须独立配置/标志/评价。

边缘化仅包含边界先验、最老帧UWB、最老到次帧的平移及角/bias边；其他保留因素不进入消元。推广原平方根投影至d维；允许缺角导致半正定边界。用带列主元的完整QR确定old列空间秩，投影消去可观测旧方向，再QR压缩边界，保留完整位置/yaw/bias交叉和非零仿射offset及丢弃常数。秩不足明确记录，不用独立对角先验补秩。非有限消元显式失败保存部分运行。

缺角仍更新相同平移/UWB并保留发布记录；当前边angular_valid=false、estimate_valid=false，覆盖损失计入总评价，不只选完整片段。缺角期间的yaw保持仅为初值，不作为测量。恢复后使用完整新边继续；累积gap标志不清除，求解全秩不足单列。accepted_graph表示求解收敛，estimate_valid另要求当前角覆盖及数值满秩，不代表实际精度/完好性。暖启动和求解失败照样发布并单列，全量有限输出与四臂共同有效区间同时评价。

正式合成前冻结源码/参数/种子。计划有限8场景×3种子×4臂，50秒/输入（跨20s边缘化并保留恢复）；包括正常、恒偏、时变bias、弱墙、偏测距/滑移失配、IMU缺口。可附静止零杆臂不可观测测试，不强迫收敛。参数不能通过两实包人工终点选择。合成真值/labels只给生成和离线评价，不交在线估计器。实际场景与数量以冻结protocol.json为准，失败和恶化保留。
