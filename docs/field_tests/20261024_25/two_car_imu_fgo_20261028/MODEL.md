# 模型与接口冻结 v1

基准 `ca8fbac4dbdf678074be5fb80bf6aff472d258e6`。`dependency_lock.json`逐文件固定双车F0、单车F3及原F0依赖；临时模块别名隔离旧绝对import，旧文件不修改。M0/M1调用原JointReplay/WindowGraph，保留6维[pose1,pose2]，每车bias=null；同一到达流新增gyro仍只诊断。M1/M3 peer均为原signed pseudo-Huber，固定Car1→Car2一条；无门控/质量/回滚，反向只诊断。

M2/M3每帧[x1,y1,yaw1,bias1,x2,y2,yaw2,bias2]。每车单独复用single_car_imu_fgo.graph.Objective，只保留原Odom body平移、墙距和F3 gyro/bias角因子；车间距离复用原3D旋转天线模型。白化联合误差e=[wrap(Δyaw−∫gyro+b_left·dt),b_right−b_left]，Q=[[qg·dt+qb·dt³/3,−qb·dt²/2], [−qb·dt²/2,qb·dt]]；不丢相关项。gyro支持缺口无角边，保留bias RW，传播初猜保持yaw，绝无Odom角回退。初帧yaw仅配置外部先验；后续新增帧/启动/失败预测均选gyro−bias，完整warmstart逐元素记录。Odom yaw仍用于body平移表达，MCU相关性未验收。

M2按两套独立F3分别执行原ftol/xtol/gtol=1e−7、每车max_nfev50，目标的H/g/c仍与完整8维无peer目标一致；保留一个8列完整先验对象和8维QR消元。独立prior应为分块对角，若出现>1e−10交叉块拒绝，不能把M3 prior拆开。M3使用全8维联合TRF、原50次预算。M0/M1保留原共同停止准则；因此成本比较须披露M2独立停止的两次子求解，不把nfev相加当单个优化器迭代数。

开发v1共同ftol曾使第14帧独立F3对照差3.52e−4rad，固定线性化目标一致、尚未消元；没有放宽1e−4容差。v2改独立停止，代码审查发现为子求解临时设置的先验需恢复，否则报告full objective会双计prior；v3恢复零行子prior，新增独立cost测试。失败/各版源码日志Git外保留；此时未运行40单元矩阵。

8维消元只消费prior、最老两车墙/最老peer、首平移和首gyro/bias。列主元QR处理真实秩不足，SVD读取器独立核验完整H/g/常数；保留帧墙和peer不进消元子图。保存8列matrix（可矩形/秩不足）、point/offset/constant，完整跨车位置/yaw/bias相关不丢。数值rank与ftol不是可观测性或位置正确证明。失败边缘化事务回滚，失败解不接受candidate；预测/失败/缺角独立标识。

20s窗口、1s关键帧/接收等待、±.4s原浮点中心窗、最少5样本不变。21帧168标量，消元前瞬时22帧176标量，逐run记录实际峰值；Odom/墙/peer/gyro各流512容量，溢出显式失败。gyro沿用已到达左保持、100ms最大保持，不以未来端点回插；所有原整数header/receive ns、record/source/raw-message SHA和分段依赖保留。共同缺Odom使两车该时刻均不更新；无peer不造量测。

富字段事件接口保留原两车JSONL的kind/vehicle/case/record/source/topic/value。imu.value必须为三轴angular_velocity_rad_s、units=rad/s、frame_id；不读取四元数/加速度。真实bag保留rich_messages与raw bytes hash，input_decisions逐消息记录，source_header与用于关联的mapped_header同时保存。真值与标签仅独立评价器读取。

CLI：`python tools/two_car_imu_fgo/replay.py --events EVENTS --config CONFIG --method M0|M1|M2|M3 --output NEW_EXTERNAL_DIR`。输出run/config、逐车published.csv、完整updates.jsonl.gz/input_decisions.jsonl.gz、final_active_graph/summary；状态时刻与虚拟可获得时刻分开。有限坐标、数值accepted、每车estimate_valid和joint_estimate_valid各有语义；缺角时即便数值accepted也非该车有效。M0/M1 bias为空，M2/M3有效0保留数值0。

预登记量化：合成完整40单元；四组相同events/config bytes，仅method参数变化，固定seed101/211与5场景。实际输入/执行完整SHA和全索引生成后才跑。评价全部有限/每车有效/四组两车共同有效，原pre[3,24)/fault[24,38)/recovery[38,48)/late[48,63]；另全量含2启动。每车base/天线XY、wrapped yaw和bias误差、相对天线XY/斜距、故障传播/正常代价/缺角/失败/恢复/计算同时报告，不对齐轨迹。
