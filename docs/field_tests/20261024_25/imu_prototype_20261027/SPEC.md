# IMU因果原型规格 v1（实现前登记）

共同起点d079c26ff1f279fbe5db131b43f809d77b561345；只写imu_prototype工具与本目录。PR56已合并，PR目标main。旧算法/参数/结果、公共geometry/manifest和B端目录只读。没有实包/留出/视频输入。

## 状态与四种对照

legacy_odom_pose直接调用冻结causal_baselines.model.Baseline，状态仍六维，不把其协方差填充成八维。配置缺少imu_prototype时默认此模式、IMU关闭。body_odom_rate使用同车Odom.twist的vx/vy与angular_z。body_imu_fixed_bias替换为显式轴投影的IMU角速度、残余bias固定0。body_imu_bias每车[x,y,yaw,b_gz]、联合8维；b只通过运动交叉协方差和UWB间接估计，绝不用Odom/IMU四元数作重复航向观测。

新三模式除一次预先声明的初始化外不读odom.pose/yaw，也不读IMU姿态/加速度。新运动均值为恒定body twist的SE(2)解析积分；F包含yaw与bias对XY的交叉项及F_yaw,b=-dt。测距时将涉及车辆的状态用已到达控制推进到该测量时刻，使用旋转XY杆臂与绝对天线高度的3D斜距；瞬时H_b=0，bias信息来自P的动态交叉项。独立模式拒绝全部peer、跨车协方差保持0；联合沿用固定Car1→Car2、200ms有向链路间隔、raw primary/bridge去重、60ms测距控制支持。没有套用旧六维可靠性索引。

Q使用中点朝向冻结的连续线性化A，A^3=0，以有限多项式积分exp(Aτ)Qc exp(Aτ)'；包含bias随机游走的yaw-b交叉和dt^3航向方差。均值F是解析Jacobian，Q是独立声明的局部工程近似，不把有限/PSD当校准统计或精度认证。速度密度单位m/√s，航向密度rad/√s，bias随机游走(rad/s)/√s；各组共享名义R及新表示的位姿过程密度。

## 因果输入、缺口与恢复

按receive整数ns、record_index、link_index排序，只交给滤波器已到达事件。每次接受控制前先用旧已到达控制传播到该源测量时刻，再安装新控制；不能用新端点反向积分之前区间。已越过状态时刻的晚到控制明确拒绝，不按2ms近邻回填。控制与状态同刻允许换新流，单流同刻/倒序和重复trace拒绝。

每次传播记录实际from/to整数ns、dt、所用速度/角速度的原record/header/receive与映射时刻、输入数值、bias、F/Q及传播前后4维状态。gyro轴在配置中以IMU frame内body-Z单位向量给出；缺项BLOCKED，单位/帧不符拒绝，不自动纠正符号。

控制保持最多100ms，测距还需两种控制在60ms内、源时刻不未来、到达时延≤200ms。普通控制事件只能推进到旧控制合法有效期，之后等待/失效；发布不外推到host接收时刻。单车IMU掉线不阻止另一车独立传播/墙更新，peer缺支持时拒绝。

恢复时两种新控制均到达且新源时刻合格，才显式把状态时刻移至最新控制起点：未知区间不积分、不补填零速度或Odom yaw，均值保持并加预登记gap过程不确定性，记录整个未观测区间。此后相对运动可继续；unobserved_motion_gap标志保留，imu_mode_status明确recovered_with_gap_uncertainty。valid仅表示当前控制/数值可用，不说明漏失位移已正确恢复；绝对恢复需外部观测。无静默Odom航向回退。

## B端接口与边界

CLI固定--events-jsonl/--config/--output，支持plain JSONL或.gz；单文件只含一个实验，field只允许T08/T10。baseline配置加单独严格校验的imu_prototype对象；schema与参数模板随源码冻结，所有数值附value/units/source_kind/source/frozen_before_field_run。synthetic_design不得直接用于field，需显式另存engineering_assumption及来源，不能升格成measured。时钟pending/空间初值未知按分支报告，source_odometry_motion_only允许一次源pose初值且禁用所有room测距。

必需输出run/config/estimate/decisions.gz/summary。保留旧ESTIMATE_COLUMNS，pose_covariance为3x3；8维状态/P另外命名。legacy bias/IMU字段空、legacy_not_used；fixed-bias的0只是固定参数设计，不代表真实零偏确定为0。输出保留拒绝、NaN质量、缺口及失败。不报实包ATE/RMSE，不用厂商固定协方差或静止候选调参。

## 验证与预登记

先测解析F/H有限差分、Q单位/交叉项、恒偏/时变bias、wrap/倒车/侧向、异步/同刻/重复/陈旧/未来、gap/恢复、轴/单位负例、关闭回归及独立/联合交叉。正式矩阵前冻结代码与协议提交。小smoke先行，正式最多10场景×3固定开发seed×4模式×2融合，40s/输入；包含正常、弱墙、gyro偏差、测距偏差、速度滑移/轴失配及静止/直行弱可观测性，保留全部弱效/恶化。数据/归档置Git外、控制新增结果约2GB内，批次有时限与检查点。

静止零杆臂时位置量测对yaw/bias无直接约束，b可严格不可观测；短直行/弱墙通常激励不足，转弯也不保证所有参数可辨识。估计bias可错误吸收轮速/测距失配；不强迫收敛，不把P小当真实误差小。全部是已受既有审查影响的开发设计，非盲测。
