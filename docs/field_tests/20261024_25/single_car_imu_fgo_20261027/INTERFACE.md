# A→B：固定窗口IMU接口 v1

本接口使用现有single_car_fixed_lag中的平移/UWB残差和原FixedLagReplay作F0，不使用八维双车EKF。旧三个入口不修改，故既有客户端默认仍完全关闭IMU。新CLI缺省arm=F0；显式F1/F2/F3才进入新角因子路径。PR57已合并，A草稿PR目标main。

## 输入与运行

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /path/to/venv/bin/python tools/single_car_imu_fgo/replay.py \
  --events-jsonl /outside/004023/events.jsonl.gz \
  --config /outside/F3.json --output /outside/new-run --max-seconds 120
```

输入为UTF-8 JSONL或.gz，保留bag原接收顺序，**不按header排序**，单文件单case_id。每行是消息级事件，不是拆分后的逐link range事件：

```json
{"kind":"odom","case_id":"004023","record_index":1,"source_file_sha256":"原bag的完整SHA256","topic":"/car2/odom","header_epoch_ns":1790000000000000001,"receive_epoch_ns":1790000000000000002,"value":{"pose":[0.0,0.0,0.0],"angular_z_rad_s":0.0}}
{"kind":"uwb","case_id":"004023","record_index":2,"source_file_sha256":"原bag的完整SHA256","topic":"/car2/uwb/ranges","header_epoch_ns":1790000000000000001,"receive_epoch_ns":1790000000000000003,"value":{"node_2":3.0,"node_3":2.8}}
{"kind":"imu","case_id":"004023","record_index":3,"source_file_sha256":"原bag的完整SHA256","topic":"/car2/imu","header_epoch_ns":1790000000000000001,"receive_epoch_ns":1790000000000000004,"value":{"angular_velocity_rad_s":[0.0,0.0,0.0],"frame_id":"需显式核实并与配置一致","units":"rad/s"}}
```

示例仅说明结构，不是现场数值或建议时钟偏移。header/receive/index必须是原始整数ns，不转float epoch。原设备时间、质量/缺失字段可额外保留，不重命名header/receive。kind=clock/other可只含case_id/index/receive/value，用于真实记录EOF；不凭空推进EOF。原读取器的IMU占位Event没有gyro，不能当融合数据。

Odom.pose的yaw来自归一化四元数/原Odom表达，仍用于**所有四臂共同的平移增量坐标变换**。Odom.angular_z只供F1；F2/F3不用其角速度/角增量作航向约束。IMU只取显式轴投影的角速度，不使用姿态/加速度。raw UWB整消息中同ID歧义按旧读取器原则由B在归一化时记录并去掉，不可把同一header拆成多条当独立消息。value保留未减P1的raw米值；内核与旧Objective一样减一次。新10/24–25场次不能套旧P1。

scope=field只允许004023、005135、T08、T10，留出拒绝；A本轮没有读取现场包。原始文件SHA和事件文件实际SHA分别保留在input_decisions/run。估计器不接受truth/fault_label/true_pose/true_bias字段；真值/故障标签只放评价文件。NaN输入经质量处理/显式拒绝，序列化null并保留nonfinite_input_fields，不能默默填0。

## 配置冻结

`tools/single_car_imu_fgo/config.template.json`为完整**合成模板，默认F0**；精确结构见同目录config.schema.json，手工附加检验在configuration.py。B复制自己已冻结的旧model/replay/optimizer/frontend参数，再加入angular与clock_maps；不得仅把模板scope改field。

- model/replay保持旧两包的起点、朝向、P1、安装、权重、20s窗口、1s关键帧/发布等待、±.4s统计窗和至少5样本规则。历史人工起点/朝向与参考不确定度未知，不能当无误差真值或调参目标。
- angular各项均含value/units/source_kind/source/frozen_before_field_run。名称为angle_noise_density_rad_sqrt_s(rad/sqrt(s))、bias_initial_rad_s(rad/s)、bias_initial_sigma_rad_s(rad/s)、bias_random_walk_rad_s_sqrt_s((rad/s)/sqrt(s))、max_hold_ns(ns整数)、body_z_in_imu_frame(dimensionless单位3向量)、imu_frame_id(frame_id字符串)。F1/F2/F3共同角噪声密度2deg/√s；F3残余bias初始0、sigma.03rad/s、RW.0007(rad/s)/√s；最大保持100ms，均为预先工程选择，不是测量校准。
- clock_maps.odom/uwb/imu各含同样5项provenance；value为source_origin_ns/destination_origin_ns/rate_numerator/rate_denominator/uncertainty_ns，全部integer。映射只用header，中心化整数仿射计算。旧“无clock correction”可明确作为engineering_assumption的identity mapping保留，不能提升为已验证同步，不能用接收负差拟合固定延迟。uncertainty_ns用于来源披露，本版未将时钟不确定性另传播为角噪声；现场结论必须条件化。IMU mount/sign未知时先记录BLOCKED缺项，禁止猜成measured。
- 新source_kind仅允许engineering_assumption/measured/manufacturer_generic/synthetic_design；field拒绝synthetic_design，须显式另存来源。几何/初值缺失不是自动补0的许可，B应留BLOCKED分支。schema验证错误在开始创建新结果目录前报错。

参数在A正式矩阵前提交冻结。B接入必须给出实际组合源码提交、输入SHA、每臂配置SHA与明确的工程继承来源；不能根据终点或未验收视频挑bias/噪声/符号。F1不需要IMU数值参加因子，但仍使用同份事件输入，避免因只删事件而更改EOF或截止顺序。

## 发布、回退与边缘化

必需输出：run.json/config.json/published.csv/updates.jsonl.gz/input_decisions.jsonl.gz/final_active_graph.json/summary.json。输出目录必须不存在、位于Git外；无静默覆盖或原地重跑。run保存命令/环境/源码/配置/输入哈希/耗时和失败。单CLI返回0完成、1失败，部分证据保留。

published.csv保留原state_time_s/availability_cutoff_s、base/antenna XY、yaw、求解状态、耗时/队列及原中位数/样本计数；现在也保留缺Odom的行，pose列为空。另有arm、整数state_epoch_ns/availability_cutoff_epoch_ns、bias_rad_s、bias_estimated、angular_valid、estimate_valid、odom_yaw_fallback、prediction_yaw_source、missing_angular_edges_cumulative、scalar_variables、state_dimension_per_keyframe、numerical_rank、angular_source。F0 bias空；F1/F2的0是设计固定，不是测量确定为0。

estimated_available_epoch_ns/publication_delay_s由原虚拟单工作者耗时/排队模型计算，含1s等待+实测update计算+估计排队；不是ROS部署实际接收时刻或硬实时保证。真实源/receive身份在input_decisions；优化只见中心化相对时间。EOF不得超出最后记录接收时刻产生cutoff。

每角区间在updates.angular_interval保留整数a/b/dt、每段左保持rate、原header/receive/index/SHA/topic、mapped_header、角增量和缺口。只有当前cutoff前到达的数据可用；等于cutoff允许，之后不回写。缺口不能用部分alpha生成完整角因子，不用Odom角度回退：预测只保持上次yaw作为初值，F3保留bias RW，平移和UWB照常进入图。缺角行estimate_valid=false，求解可能数值收敛但无角覆盖。恢复后新完整边继续；累计gap记录不清零。所有暖启动/失败/缺口都保留，汇总同时给全量有限发布、覆盖率/失败率和四臂共同有效时段。

F3每帧4变量，21帧84标量、瞬时22帧88标量；F0–F2为3变量，63/66标量。prior_matrix保留完整位置/yaw/bias相关及非零offset。marginalization_details给每次消元的线性化旧两帧、最老UWB、首边、前后prior与rank/constant；**不含保留帧UWB**。QR支持半正定边界，秩不足明确报告，不造对角先验。原历史非线性已冻结，不宣称等于完整重线性化全历史。

objective_snapshot给活动图inputs、prior、accepted/candidate states，供B独立重算目标函数；candidate_pose保持3维，bias另名。偏置只通过动态/测距间接约束，静止零杆臂可能不可观测，不能把有限解/小方差/数值秩当真实精度或完好性。

## 测试、恢复和独立读取

```bash
python tools/single_car_imu_fgo/tests.py
python -m unittest discover -s tools -p 'test_single_car_*.py' -v
python tools/single_car_imu_fgo/batch.py --output /outside/new-matrix
# 仅确切source/protocol/input/output SHA匹配且无未索引partial cell时：
python tools/single_car_imu_fgo/batch.py --output /outside/new-matrix --resume
python tools/single_car_imu_fgo/check_matrix.py \
  --experiment /outside/new-matrix --output /outside/new-readback
```

audit.py不导入在线优化器/Objective/Jacobian，自行重算原Odom插值、P1/raw统计、角积分、预测、目标函数和抽样有限差分边缘化。它与在线端仅共享JSON/哈希等I/O辅助；B仍应做自己的独立回读。原37项回归、新测试、smoke、正式矩阵与报告状态分别列出，不混淆“实现已测”和“现场精度未验收”。取包与确切SHA见HANDOFF及归档索引；不自动继续旧EKF矩阵。
