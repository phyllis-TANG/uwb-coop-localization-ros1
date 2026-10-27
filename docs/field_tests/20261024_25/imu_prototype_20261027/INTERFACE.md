# B端接入接口 v1

只实现共同合同，没有变更共享CONTRACT.json。附加字段及motion-only配置是A目录内显式扩展。旧6维算法和公共数据保持不变。先核对HANDOFF给出的执行源码提交/协议SHA，再在新组合checkout调用本目录工具；不可只复制replay.py而遗漏固定旧模块。

## 输入、配置与调用

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /path/to/venv/bin/python tools/field_20261024_25/imu_prototype/replay.py \
  --events-jsonl /outside/inputs/events.jsonl.gz \
  --config /outside/config/explicit.json --output /outside/new-run --max-seconds 90
```

事件wrapper和row字段沿用共享合同，gzip/plain JSONL均可。exact integer epoch ns和record_index，不可把epoch转成float。单文件单experiment；scope=field仅允许T08/T10。source_file_sha256是原输入来源记录，run.inputs.sha256另记录实际事件文件SHA。整个事件row保留在decisions；非有限数值输出null并在nonfinite_input_fields记录原路径/NaN表示。source/header/receive字段不互相替代。IMU额外需要frame_id；angular_velocity_units缺省按合同rad/s，显式其他单位拒绝。Odom需要carN/odom、carN/base_footprint，linear_x/y；body_odom_rate额外使用angular_z。range沿用旧raw/primary、有向tag/target、range_m/valid/link_index规则。

完整synthetic_config.json是可运行的合成模板；不能直接改scope=field当现场配置。根对象仍由冻结旧validate_config校验，新增imu_prototype对象严格遵守config.schema.json（JSON Schema2020-12）。B保留自己已冻结的初始几何、噪声、clock与来源；逐项加入新对象，数值/轴/帧/初始bias/时间门槛附value、units、source_kind、source、frozen_before_field_run。field禁止旧参数source_kind=synthetic及新参数synthetic_design。显式声明engineering_assumption不等于测量验收。参数和参数候选不得根据T10输出或未验收视频选择。

新对象必填：schema_version=1、enabled、motion_mode、fusion_methods、frame_mode、ranges_enabled、assumption_profile_id、input_correlation_assumption、parameters、vehicles。唯一例外是关闭对象可仅有schema_version/enabled=false/motion_mode=legacy_odom_pose；对象完全缺省也直接调用冻结旧六维模型。新模式fusion_methods可为independent、joint或两者；joint固定Car1→Car2，不含可靠性策略。

parameters精确名称和单位：velocity_noise(m/sqrt(s))、heading_noise(rad/sqrt(s))、bias_random_walk((rad/s)/sqrt(s))、gap_xy_noise(m/sqrt(s))、gap_yaw_noise(rad/sqrt(s))、max_control_hold_ns(ns)、max_control_latency_ns(ns)。数值见冻结模板/协议，不再拟合。

vehicles.car1/car2分别包含gyro_axis_body_z_in_imu_frame(dimensionless，3维单位向量)、imu_frame_id(frame_id，字符串)、bias_initial(rad/s)、bias_initial_sigma(rad/s)与imu_clock。轴是IMU坐标内body-Z的投影向量，不是未经验证的固定取z；符号不对自动拒绝/诊断，不会替用户标定。

imu_clock使用header_epoch_ns、integer origins、rate_numerator/rate_denominator、uncertainty_ns、source_clock_id、destination_clock_id、source/source_kind/units=ns/frozen_before_field_run；destination必须同根master_clock_id，valid_source_interval_ns可选。待核实时保留整套键，将status设pending、数值未知设null，source写准确缺项；不能删成仅status的对象。schema严格完整性用于避免B误拼字段；有效性/readiness会给BLOCKED，禁止替换为接收时间负差的未经验证固定延迟。

T08缺房间初值时，可使用frame_mode=source_odometry_motion_only、ranges_enabled=false、fusion_methods=[independent]，只从第一次绑定Odom pose初始化到各自carN/odom。仍需显式Odom/IMU时钟、初始工程协方差、轴/帧/运动参数；不需要room pose/墙几何/杆臂，不会使用任何range。T08房间定位不足继续BLOCKED，不编造geometry。

## 输出与时间语义

必需run.json/config.json/estimate.csv/decisions.jsonl.gz/summary.json。返回0=DONE；2=有BLOCKED分支（其他独立分支可能已有有效输出）；1=失败，保留run及已产生证据。输出必须是不存在的Git外目录，不能覆盖或自动续写同一个CLI输出。

保留旧ESTIMATE_COLUMNS和pose_covariance3x3；state_epoch_ns是状态实际对应的测量/推进起点，publish_receive_epoch_ns是按receive因果回放的逻辑发布cutoff，不是现实硬件可达到的实时wall-clock。运行计算耗时见run.elapsed_s，不能拿离线cutoff当部署报警时延。source_*沿用Odom来源记录；last_velocity/last_imu列是实际参与传播的记录，未使用则空，最新缓存控制另在decisions.provenance中。每段from/to及真实dt、两路source/header/receive/index、F/Q和前后状态可独立复算。

gyro_bias_rad_s/variance在legacy为空；固定bias模式0/0是设计约束，不代表真实bias确定为0；估计模式为残余bias及工程EKF方差。body_odom_rate不输出估计IMU bias。附加gyro_bias_estimated、unobserved_motion_gap、bias_semantics、state_dimension用于消除歧义。完整8维state/P位于decisions.filter_state及range_update；冻结旧模式另名legacy_state_6d/covariance_6x6，不伪造8维。

max100ms保持、range60ms支持、200ms到达门槛使用源时刻；迟到控制不回填。缺控制时只积分合法前缀，等待并valid=false。两控制恢复后显式reanchor到新的起点，未知位移不积分，均值保持并膨胀工程协方差；unobserved_motion_gap永久保留，valid恢复只表示当前控制/数值可用。缺口绝对轨迹未被恢复为真值。range几何不足另有geometry_degraded和局部rank，不把valid解释为完好性或定位可信认证。

wall_only_initial_state_linearized_gramian仅使用墙距局部H和传播Phi，不含peer、不用于滤波；噪声/滑移/缺口及线性化会限制其意义，不能据其谱声明完整联合可观测性。bias弱可观测可能吸收轮速/测距错误；禁止把小P当已校准误差界。

## 冻结、审计与恢复

正式协议protocol.json指定10场景×3固定种子×4CLI运动模式，每CLI含2融合，共120 CLI/240方法/480分车指标。输入30份相同事件；真值/labels只传给evaluate.py。smoke seed101与开发种子不同；已有设计受历史审查影响，不是盲预注册。

```bash
python tools/field_20261024_25/imu_prototype/tests.py
python tools/field_20261024_25/imu_prototype/batch.py --output /outside/new-matrix
# 中断后（只允许相同代码/协议、原输入及完成输出哈希）：
python tools/field_20261024_25/imu_prototype/batch.py --output /outside/new-matrix --resume
python tools/field_20261024_25/imu_prototype/audit.py \
  --run /outside/new-matrix/runs/nominal_seed31__body_imu_bias \
  --input /outside/new-matrix/inputs/nominal_seed31/events.jsonl.gz --output /outside/new-audit.json
```

已完成及失败cell均不自动重跑。未索引的部分cell保留并报错；先审查其run与日志，另立版本决定恢复，不可清除记录或以--resume绕过源锁。正式矩阵结束后只新增离线回读/报告，不调整模型、门槛或重写输入。
