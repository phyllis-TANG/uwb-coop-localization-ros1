# 阶段C：T08/T10输入通过，全局解算未运行

阶段B检查通过后，仅从Release测距数据archive提取T08和正式成功T10 retry。先搜索既有副本；无命中后只取得38,399,544字节数据archive，未下载视频。归档SHA b7cec6f75584e583e66946fd669dc7495d10e3bcbebc0b67fa480b65b53fd1bf，与manifest一致。未提取/解码其他bag、未使用中止T10原件。

|包|原bag SHA256|字节|全部消息|Car1/Car2 gyro|Car1/Car2 Odom|
|---|---|---:|---:|---:|---:|
|T08_C1static_C2L_repeat1_20261025_180633.bag|cf3b4de0f20424d02779aeeb416a4fb16d77bb1f5333344d48ebf446a3884ada|29268326|70766|4883/4867|4879/4861|
|T10_C2static_C1straight_repeat1_retry_20261025_184755.bag|f2853240661be0cef53e77cee9a5a33f74cfb1524231d2eb94b2dcacaa57c558|7002834|16998|1163/1150|1161/1145|

原始消息身份与rich字段全部双解码读回PASS。gyro为ROS angular_velocity三轴rad/s；本场次frame分别car1/gyro_link与car2/gyro_link，未沿用18日共同gyro_link配置。所有gyro/Odom/UWB header均无重复、倒序、>100ms间隔。T08 gyro header最大dt为53.704/50.597ms，T10为50.263/50.388ms；接收间隔>100ms的gyro分别5/5及1/0次，显示“有消息/原header连续”不等于接收时钟可替代采样时钟。

独立本车native-header左保持的published Z积分仅为输入诊断：T08 Car1/Car2 −.19526/−2.19180rad，T10 −.11198/−.12276rad。不跨车拼时间、未映射到房间yaw；静止标签与非零积分也不能直接当已标定bias。实际轴、符号对房间转向、采样时间到header政策、噪声与MCU独立性仍待确认。四元数归一化、Odom相关和发布固定协方差都不解除这些缺项。

## 具体阻塞

冻结基准的parameter_clock_prep/results/T08_input_template.json和T10_input_template.json逐车antenna_body_xy_m均null；initial_record_binding尚pending。T08只有名义路线初始位置/朝向，非绑定实测；T10 Car2初始yaw连完整数值候选也没有。两模板各host clock source/destination origin、rate、有效区间和uncertainty均null。新Car2的[−.12,+.08]是近似几何中心符号修正，不能冒充odom原点杆臂；Car1不能搬18日安装。T10模板中引用此前场次终点的历史候选也未被本轮估计器使用。

因此本轮没有创建新场次求解配置或虚构单位时钟，八条M0–M3全局运行明确BLOCKED/NOT_RUN，非完成、非优化失败。输入核验通过与全局模型就绪是不同门槛。原bag分别保存，不拼接、不继承bias/prior；10月17日P1与旧Car2bias不迁移。

后续须逐车/逐日确认odom/base→天线、初始状态消息绑定、物理安装轴、共同采样时钟政策及适用噪声，再经协调冻结新配置/索引后另开运行目录。不得拿T09/T11/T13/T15终点或轨迹选参数；本轮也未扩展T12/T14。完整原始时间范围、间隔、首尾覆盖及每车字段在FIELD_INPUTS.json和review/T08_input_readback.json、T10_input_readback.json。
