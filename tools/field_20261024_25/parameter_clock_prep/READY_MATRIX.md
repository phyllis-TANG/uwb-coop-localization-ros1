# 四个开发包的参数就绪矩阵

这是配置/证据就绪检查，**没有重跑实包定位**。原始odom frame回放已由PR46完成。本轮分别编译了四个模板，均返回预期的BLOCKED（退出2），未把编译完成当成融合运行成功。

| 包 | 原odom frame | room Odom-only | room 独立UWB/Odom | room peer联合 | 已有起点/朝向线索与真实缺项 |
|---|---|---|---|---|---|
| T08 | 原能力仍可用，本轮不重跑 | 缺room初值及odom时间模型 | 两车均缺实际初值/记录绑定、水平杆臂、采样时间模型 | 还须两车共同时间关系 | B/A、−Y/+Y是指导；需要确认其是否代表本包所选初始化记录，或提供可追溯视频初值 |
| T10 | 同上 | 同上 | 同上 | 同上 | Car1回B/−Y是指导；Car2(2.98,3.07)是T09人工终点加“不动”计划，不能当新测T10起点；Car2本包实际车头仍需确认 |
| T12 | 同上 | **实际初始XY未知**；不可抄T13/终点 | 同上且实际XY独立列为unknown | 同上 | 首距2.00m不能决定两车位置；初始XY候选保留null，+X/+Y仅是指导朝向 |
| T14 | 同上 | 缺实际初值与时间模型 | 同T08 | 同上 | B/A、−Y/+Y为指导，首距2.09m；遮挡材料/时段另属实验标签证据，不阻塞基础几何代码 |

**四包共同已经具备的输入**：人工记录的近似天线绝对高度C1=0.17m/C2=0.20m、历史墙锚坐标、body/room轴约定、既有固定工程R/Q及回放参数。高度不确定度保持null；base高度与lever-Z不再分开索取。独立视觉精度/同步验收继续作为“现场精度评价”门槛，未列为算法代码执行的先决条件。

## 真正还缺的最小信息

1. **几何参考点**：每车相对物理odom/base原点的水平天线杆臂 `[forward,left] m`。可来自独立机械测量/明确的模型原点对应或有验证范围的标定；不能把marker偏移、近似车体中心或URDF零TF直接当成它。
2. **每包初始化**：所选初始化记录处的实际天线XY和body车头yaw，以及bag SHA、原record_index、原header ns和接收ns。给出来源、适用安装状态、误差/未知项。编译器可结合水平杆臂推导base XY，不另求一套重复base坐标；直接提供已建立的base位姿也仍受旧接口支持。若视频只能覆盖较后时段，可选后续明确的初始化记录，之前保持未初始化，不能反推补齐过去。
3. **测量时间语义**：按证据确认主机/ROS时间组、主机到共同master映射及每话题采样到header关系（或明确来源和误差说明的发布时刻近似）。raw/bridge复制的header不用另拟合。未知者保留pending，不能用NTP状态、receive−header中位数或默认零延迟代填。

第3项是PR46当前共同master、future/stale门槛和跨车测量关联接口的输入要求，不意味着必须获得“绝对UTC毫秒真值”。独立自车算法在另一种接口下可以使用确认的本机相对时钟；本轮没有为绕过未知关系而切换时钟架构。联合解必须能把两车相应状态关联到同一测量时刻。若同机共享ROS clock得到部署证实，可以共享host映射，保留各话题采样语义，不制造四套独立主机漂移参数。

## 交给未来参数提供方的文件

每包已有一份可编辑副本：[T08](results/T08_input_template.json)、[T10](results/T10_input_template.json)、[T12](results/T12_input_template.json)、[T14](results/T14_input_template.json)。只在另存的新文件填写具有来源的字段，将已提供项标`provided`；保留未知量null及其原因。候选指导值单独放在`candidate_records`，不会自动进入初值。

- 视频端若输出天线XY/body yaw，需附video SHA、frame/整数PTS/time_base、每片frame/time映射来源，以及与指定odom记录的绑定。若只输出marker pose，需另给marker→body旋转/适用平面条件，不能直接当作车头。
- 初值/外参如由参考点拟合，记录拟合点ID与另行独立检验的点ID。初值可作明确来源的探索参数，不能据此宣称同一参考已通过独立精度验证。
- 时间提供方需给source/destination clock ID、integer origins、有理数rate、有效源时间区间、采样偏移及误差界/来源；发现nlink与odom并非共享clock时可用`clock_group_ids`分开指定，不强行套共同group。
- 底盘/机械记录方需要确认物理odom原点与水平杆臂；源码/部署资料方需补Car1底盘和实际nlink打戳路径/构建身份及ROS time模式。当前不要求启动车辆或重新采集现场路线。

编译后的最小配置：[T08](results/T08_baseline_config.json)、[T10](results/T10_baseline_config.json)、[T12](results/T12_baseline_config.json)、[T14](results/T14_baseline_config.json)；机器可读矩阵：[readiness_matrix.json](results/readiness_matrix.json)。当前每车融合阻塞仅保留`initial_room_pose`、`antenna_body_xy_m`、`odom_clock`、`range_clock`，没有另加base高度或lever-Z阻塞。这里的初始base位姿可以由第2项明确推导，并不要求额外测量它。
