# 时间模型证据：发布戳、采样时刻与记录时刻分别处理

## 源码与部署证据

原件来自登记的38,399,544字节现场归档，SHA256 `b7cec6f75584e583e66946fd669dc7495d10e3bcbebc0b67fa480b65b53fd1bf`。本轮重算原归档哈希后，只读其源码/时钟文件，未运行归档脚本或解析/回放bag。完整成员路径、SHA及带行号片段见[source_evidence.json](results/source_evidence.json)。

| 话题/环节 | 已有证据 | 能确定什么 | 仍pending什么 |
|---|---|---|---|
| Car1 UWB ranges | 现场源码包`car1_uwb_source_20261024_044515.tar.gz!uwb_linktrack_driver.py` L69–111；原驱动SHA与现场记录一致 | 串口读/缓冲排空→parser.feed→publish_frame；L90为`rospy.Time.now()`，是主机ROS调用时刻。循环中逐帧打戳，不能恢复串口到达前的物理采样时刻 | 与当天运行文件/进程的最终部署对应、ROS time模式、硬件采样到打戳的延迟/不确定性 |
| Car1原始JSON包装 | `car1_uwb_raw_wrapper_v2.py` L32–38、63–72，归档SHA `71d0d3d644fbf0eae1efde7e88518bc0758ed1b99da87fc288c248912b73a5a5` | 先调用原ranges publisher，再用该消息header填raw stamp；raw另发布，**没有第二次取时间**。配对raw/bridge无需另一套传感器时钟映射 | 两次消息在ROS/VM处可能不同排队和到达；相同header不意味着同时接收 |
| Car2 raw nlink | 嵌入schema和标准化设备ms、header；现场记录给出nlink部署路径，但登记归档没有相应parser源码 | 有frame local/system ms和ROS header；这些字段可分别保存 | 实际header在哪个函数生成、是否主机打戳/如何转换设备时间、运行源码/二进制对应、frame时间是否代表每个peer条目的采样时刻 |
| Car2 raw→ranges bridge | 仓库[nlink_frame3_bridge.py](../../../ros_ws/src/uwb_coop_localization/scripts/nlink_frame3_bridge.py)的`frame3_to_range_array`；四包精确header配对 | 此实现deepcopy上游header，修改frame_id不改stamp；数据支持同header关联 | 桥接源码版本与现场二进制对应仍需记录；**bridge代码不能证明上游nlink的时间生成位置** |
| Car2 odom | `car2_base_source.tar.gz!src/wheeltec_robot.cpp` L663–696、287–311 | Get_Sensor_Data_New之后取`_Now`，用其与上次差积分；随后Publish_Odom L294再次`ros::Time::now()`打header。header不是直接保存`_Now`，更不是已证明的底板采样时间 | 归档源码未与运行二进制构建哈希对应；板端采样/排队和串口解码年龄未知 |
| Car2 IMU | 同文件L258–280、692–693 | 同一上位机循环，odom发布后调用IMU，IMU再次Time::now打戳；共享控制板输入不应当作独立真值 | 物理IMU采样与板反馈对齐、固件融合及实际时间延迟 |
| Car1 odom/IMU | 现场话题/主机记录、标准化header序列；无本轮对应底盘源码归档 | 可描述接收及header序列，不能把Car2源码直接声明为Car1实际实现 | Car1实际时间戳生成代码/版本、固件/二进制对应和ROS time模式 |
| 两车主机→录包VM | 现场网络/ROS_IP拓扑；bag接收ns由记录端保留 | ROS Master在Car2只是图/连接入口，不会替Car1统一生成header；两车和VM是不同主机时钟关系 | 两个主机到记录端的offset/drift/有效区间及不确定性，没有实测上界 |
| cmd_vel | 标准化commands无header | 仅有bag记录时刻及Twist；没有伪造header | 控制命令实际生成/传输/执行时刻，不能用record时间充当确定执行时间 |
| NTP/时区 | `car1_clock.txt`、`car2_clock.txt`、`vm_clock.txt`均报告已同步/active | 10/24快照显示服务状态；时区不同不改变epoch。三次快照是顺序执行，不可拿显示秒数相减估offset | 10/25动态录制时的实际同步误差、偏差上界、时钟跳变/ROS time模式（未有`/use_sim_time`配置证据） |

## 标准化数据的新描述检查

只读取T08/T10/T12/T14的odom、imu、commands和frames表，没有运行定位。原PR45输出先验证来源/全部产物哈希。每条epoch ns先以整数读入，再对同一序列作差；没有对两个未校准主机的device时钟作减法。完整统计见[clock_diagnostics.json](results/clock_diagnostics.json)。

- 四包两车raw/ranges有60,100组相同header关联；分别发布的消息在同一VM记录端仍可有不同到达时刻。Car1在T12的bridge−raw接收差范围约−213.174至+309.534ms。它是**同一记录端的到达间隔**，不是底板采样延迟、无线掉包或新的固定时钟修正。
- 两车device system time相邻frame增量均20ms，local time主要19–21ms，支持已记录frame时间推进连续；不证明两个设备与ROS/UTC对齐，也不证明同frame所有链路为同一物理测量瞬间。
- IMU与最近odom的header差（同车离线描述性配对、最多25ms）中位数：Car1四包约29.586/30.574/30.366/30.262μs，Car2约44.832/48.096/43.393/44.961μs。这与依次发布的模式相符；Car1实现仍pending，**微秒级header间隔不代表微秒级物理同步**。
- 各话题receive−header分布及负值数量完整保留，但没有被代入任何配置时钟参数。该差混合记录端与发送端时钟差，以及打戳之后的序列化/排队/传输/接收调度；硬件采样至打戳的未知时间还在另一层。中位数不提供唯一分解。

## 最小时钟输入和可接入字段

不必为复制header的raw/bridge分别拟合clock。若部署/ROS time模式确认同一主机的odom与UWB均使用同一ROS主机时钟，可共享一个主机→记录端仿射模型；**每话题的采样/发布语义及延迟不确定性仍独立保留**。当前模板只是共享主机group的pending候选，不把nlink来源未知强行认定为同钟。`clock_group_ids={odom:...,uwb:...}`可以覆盖共享候选，给不同来源保留不同group。

接口定义：`sample_master_ns = dst_origin_ns + round((header_host_ns-src_origin_ns)*rate_numerator/rate_denominator) + sample_offset_ns`。源/目标clock ID、原点ns、有理数rate、有效source区间、来源、拟合事件与误差界必须明确；sample_offset为有符号ns，采样早于header时为负。未知状态保持pending及null，不填rate=1、offset=0或uncertainty=0作为完成标记。编译器将两个已声明绝对误差界相加，不凭空假设独立性；运行时拒绝超出已声明有效区间的映射，不无界外推。

视频端若以PTS提供参数，需保留原整数tick/time_base、video SHA与frame index，并给出每片video→目标clock的独立模型、有效区间、匹配事件/残差与不确定性；不能用帧号/30冒充PTS、不能将视频时刻直接塞入ROS header字段。初始天线位置/body yaw应绑定到明确的实际odom记录。若首条bag odom不在可用视频范围，可显式选后面的初始化记录；此前状态留空，不能用后来的初值反推填充过去。

当前没有足够证据给任何实包填写上述host或采样时刻修正。下一步需要已有部署源码/构建身份、ROS时钟模式、动态期间可追溯的clock/同步事件资料或有误差说明的显式近似模型；不要求为本轮启动小车或在线测钟。独立参考的精度/时间验收另用于评价，不能把“参考尚未通过”当作拒绝继续写接口的理由。
