# 实包字段来源与预登记门槛

## 两旧包：conditional_development，严格物理分支BLOCKED

每包M0–M3各一个主运行，共8；原始015334/033248就地只读。raw bridge只消费/carN/uwb/ranges，反向peer只诊断，其他话题保留时序/原消息身份但不作因素。只用raw墙/peer；零P1修正。执行前旧包原SHA、全部30288消息、真实gyro三轴/协方差/Odom/UWB及原ns由rosbags生产与嵌入schema读器独立核验。

|字段|Car1|Car2|来源/批准级别|
|---|---|---|---|
|墙坐标|两车相同原17日4节点|相同|17日session_config，同日操作员墙未移位；不确定度未知|
|杆臂XY m|[+.08,−.06]|[+.12,−.08]|18日安装survey，近似几何中心；假设与odom原点重合，未验收|
|高度m|.17|.20|18日survey，原Car1 notes .20保留；不偷偷用25日相反杆臂|
|015334初始天线XYZ m/yaw deg|[1.5,4,.17]/0|[2,2,.20]/90|原notes + 历史冻结摆放假设；yaw非独立测量，不从终点求角|
|033248初始天线XYZ m/yaw deg|[1.5,4,.17]/−90|[2.95,3.04,.20]/0|原notes/前段连续摆放；yaw为冻结假设|
|IMU frame|gyro_link|gyro_link|逐包原字段；同标签不证明安装相同|
|角速度|原发布xyz rad/s|原发布xyz rad/s|sensor_msgs/Imu原值和原消息SHA；非ADC，不以固定协方差标定|
|body Z在IMU|[0,0,+1]|[0,0,+1]|逐车独立显式工程假设；Car2源码/相关性不充当Car1安装证据|
|初始bias/σ/RW|0/.03/.0007|0/.03/.0007|单车F3冻结工程假设；无真实标定/跨车迁移后验|
|角噪声密度|2deg/sqrt(s)|相同|同一冻结模型，不是实测噪声|
|共同时间|每流bag接收关联|每流bag接收关联|原双车旧候选，**非header identity、非物理同步或采样时钟验收**|

接收关联candidate在原双车README与HISTORICAL_READINESS已有明确数值定义，故可执行条件响应诊断。映射用原每条receive ns作关联源时刻；原header保留并另统计真实header dt。gyro积分用映射后实际相邻recorder接收间隔与原100ms左保持，**不把它称真实传感器采样dt**，不隐藏接收积压制造的角覆盖缺口。没有根据receive−header中位数拟合时钟，也没有用轨迹/终点补clock。该选择只是一项已披露的旧包候选，物理采样时间与误差界仍null，不能给定位精度验收。

原bag物理消息顺序有跨话题receive微回退：015334 15次最大54916ns；033248 12次最大36051ns。适配v1拒绝且保留失败；v2不重排、不改变header/receive，新增availability_epoch_ns为原物理前缀的max(receive)。只表示走到该条消息时已处理前缀的事件时钟；截止还绑定availability_prefix_max_record_index。积分支持/peer身份保存原时间与mapped/available时间。共同源时钟、微回退处理和发布语义对四组完全相同。严格接口新增负例与18项总合同通过后才冻结8索引。

每包独立启动，初帧先验固定在该包首个共同有效keyframe，不继承另一包。保留20s/1s/1s及原聚合、原权重、方向与初始化规则；M0/M1回归当前F0，不比旧全历史原型。末5个发布只作预登记的停点开发诊断，与原notes坐标/卷尺并列，量具/实际静止/时空绑定不确定度未知；无连续RMSE/ATE、真实yaw/bias精度或收益百分比。原015334 85–94.8s静止窗及033248 0–5s诊断窗另存，既有人工终点不进入模型。

## T08/T10：输入阶段允许；全局解无完整数值候选时BLOCKED

仅提取manifest精确SHA的T08及正式T10 retry。新几何geometry.json与parameter_clock_prep模板尚无已绑定odom/base→天线、完整逐车房间初始yaw和各host→共同采样时钟数值。Car2相反符号杆臂是对近似中心的操作员更正，不能代替odom原点变换；Car1不能套18日安装。T10 Car2初始yaw候选仍null；T08名义摆位/路线也不是绑定初始记录。

因此本轮可继续真实gyro/轴标签/时序/输入SHA核验，不能自行创造identity clock、Car2 +X yaw或跨日Car1杆臂凑四组。阶段B读回通过后才做T08/T10输入核验；相应8条全局运行预登记BLOCKED、NOT_RUN，既非失败也非完成。待协调冻结逐字段数值后可复用本接口另起主运行版本，不读取T09/T11/T13/T15内容或终点调参；T12/T14也不扩展。
