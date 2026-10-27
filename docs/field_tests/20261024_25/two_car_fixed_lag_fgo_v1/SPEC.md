# 双车固定窗口最小对照 v1（首轮预登记）

共同基准 868349b543a03a6a713d1675e1d4ada7d905410c。只新增本目录和
tools/two_car_fixed_lag_fgo_v1/。先提交本协议，开发 seed=7；代码测试冻结提交后
才生成正式 seed=101、211、307，四场景×D0/D1=24组，不换seed、不按结果调权。

| 项目 | D0 | D1 |
|---|---|---|
| 状态 | 每关键帧 [x1,y1,yaw1,x2,y2,yaw2]，同一联合求解器 | 相同 |
| 单车因子/初值/输入/截止 | F0 原位置朝向先验、Odom SE(2)、墙距 | 相同 |
| peer | 不进入目标函数，仍记录可用性/诊断 | 每帧最多一个 Car1→Car2 中位数斜距因子 |
| 外参 | 每车各自固定 body XY 杆臂和天线高度，非待估变量 | 相同 |
| IMU/质量策略 | 无；忽略但保留事件身份 | 无；后续独立消融接口保留 |

状态中天线位置由各车自己的 SE(2)、杆臂、高度确定；没有把另一车已融合位置当独立观测。
peer 的预测是两天线中心三维欧氏距离，含高度差、各自yaw的杆臂导数。
peer尺度0.2m，同墙距 signed pseudo-Huber；无新gate/PR61质量/方向择优。
反向仅诊断。只收 bridge canonical 测距；raw 副本只记拒绝计数，不参与墙/peer，
canonical 每车同header重复消息明确拒绝。缺peer不生成因子，绝不填0或用反向补齐。

沿用20s、1s关键帧、±0.4s中位数、每链至少5样本、t+1s接收截止（等号可用）、
原始Odom插值/unwrap/有效正距及一次修正、首两帧预测、TRF解析Jacobian及50次预算。
6维QR仅消费旧边界先验、旧帧两车墙距和peer、旧到新两车Odom；保留帧墙距/peer
仍显式保留一次。保存完整6×6矩阵、非零仿射offset及丢弃常数，禁止对角化交叉项。
历史非线性在消元点冻结，不声称全历史重新线性化等价。解算21帧126标量，瞬时22帧132。
边缘化失败事务回滚并输出失败；不接受失败候选，下一次可用输入重试。求解失败用Odom预测。
两车首网格必须相同，否则严格BLOCKED；任车缺Odom包围端点时该联合关键帧无效、两车不更新，
恢复后连接到各自上次有效Odom。此共同可用性限制同时适用于两臂，缺Odom行不隐藏。

合成设计：64s、20Hz消息、两车同时非共线运动，已知独立房间坐标初值和固定外参；
共享精确合成clock mapping（不是现场同步证据）。正常；peer在[24,38)s加1.2m；
Car1 node_2墙链在[24,38)s加1.2m；peer在[24,38)s完全缺测后恢复。
正常噪声：墙/peer原始独立0.04m，Odom每步body平移0.002m及yaw0.0008rad随机游走，
初始位置/yaw误差分别由seed生成，sigma=0.08m/2deg，先验沿用0.2m/5deg。
安装合成取历史数值C1=[.08,-.06],z=.17；C2=[.12,-.08],z=.20，明确synthetic_design，
不据此解决历史符号争议。墙距修正为0（合成生成模型），不迁移Car2 P1。
每seed四场景共享噪声，故障只改指定量测；D0/D1逐字节同一事件文件。
接收延迟确定性随消息变化10–40ms；故障边界独立标签，不进入估计器。
真值在truth.jsonl、标签在labels.json，事件输入无truth/fault字段。EOF只到末条实际接收。

必要验收：D0与两独立原F0在非缺Odom输入上同解（位置/yaw1e-5）；残差/Jacobian有限差分；
6维消元与Schur的Hessian/梯度/常数；非零交叉项及保留因子不双算；receive-prefix含真实多次
边缘化、截止等号/晚到、不可回写、缺peer恢复、缺Odom、solver和marginal失败、有界缓存/溢出。
基础测试未过不运行正式矩阵。开发输出不覆盖，失败在矩阵清单保留，不静默重跑。

评价：每车天线XY RMSE及yaw RMSE、相对天线XY向量RMSE、三维间距RMSE；
全部有限输出（含暖启动/回退）与D0/D1两车共同accepted有效时段并列。
按pre=[3,24)、fault=[24,38)、recovery=[38,48)、late=[48,63]报告；
正常D1-D0代价和故障对未直接污染Car2的同期传播差、恢复残留均保留负结果。
缺测覆盖/因子覆盖、失败、回退、总耗时/p95及峰值变量/缓存单列；
拟合peer残差不能独立证明定位更准。所有回放标virtual，不宣称车载端到端实时。

输入：JSONL按原接收顺序，每条kind=odom/uwb/imu/clock，vehicle_id=car1/car2（clock可空），
case_id、record_index、整数receive_epoch_ns/header_epoch_ns、source_file_sha256、topic、value。
odom.value.pose=[x,y,yaw]；uwb.value={node_2:raw_m,...,node_0/1:peer_m}，representation=bridge。
source_observation_id为同源身份，raw副本可用representation=raw。identity和原ns保留，不按header排序。
严格field入口当前BLOCKED，不支持把synthetic配置改scope绕过；留出包不读、视频不作真值。
CLI replay.py --events-jsonl --config --arm D0/D1 --output（新Git外目录）；输出
run.json/config.json/published.csv/updates.jsonl.gz/final_active_graph.json/summary.json。
published每时刻两车各一行，保留原state_time_s、availability_cutoff_s、pose/antenna/yaw、valid/status/耗时；
updates逐次保存冻结bins、依赖最大接收时刻、完整先验/边缘化输入、状态及optimizer状态。
IMU事件目前只有diagnostic_ignored，不增因子；后续扩展必须新臂/新协议。

大型产物Git外；此Linux环境无已确认I盘映射，不写未知盘符、不复制原视频/大bag。
合成小文件及运行产物放 /home/ubuntu22/uwb-two-car-fixed-lag-fgo-v1-artifacts，归档SHA登记。
历史015334/033248只交就绪/缺项；origin/mount/heading/clock未明确前不跑条件性4组。
