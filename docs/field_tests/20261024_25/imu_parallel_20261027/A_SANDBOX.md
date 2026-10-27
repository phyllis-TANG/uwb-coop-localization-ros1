# A窗口：沙盒Codex，IMU模型与合成验证

请用中文作为“IMU因果模型实现端”自主完成本任务。仓库https://github.com/phyllis-TANG/uwb-coop-localization-ros1。先读同目录README.md和CONTRACT.json，再读imu_odom_audit_20261027下REPORT、OFFLINE_EVIDENCE、VM_SOURCE_EVIDENCE、INTEGRATION_PLAN。不要重新做资料大搜索。

1. 核对pwd、Git状态/分支/HEAD/remote、AGENTS.md和Python执行能力。从用户指定分工包提交建立独立checkout、analysis/20261027-imu-core分支、venv与Git外结果目录，不动其他窗口。网络或文件限制如实说明，不绕过权限。授权范围内可自主写代码、安装隔离依赖、测试并发布草稿PR；不自动合并。
2. 只写tools/field_20261024_25/imu_prototype/和docs/field_tests/20261024_25/imu_prototype_20261027/。旧causal_baselines、causal_reliability、t10_exploratory、t10_reliability_bridge、公共manifest/geometry和B目录不改。可只读复用旧函数或采用新适配器；新功能放自己目录。
3. 实现默认关闭的每车[x,y,yaw,b_gz]运动/融合模型。车体vx/vy来自Odom.twist；IMU分量经显式轴映射得到body gyro_z，再减每车残余bias传播。使用真实有效dt，bias随机游走和过程噪声单位必须一致。推导/检查运动、测距杆臂投影、状态及bias交叉项的Jacobian；联合8维，独立模式不得被peer或另一车墙距悄悄更新。
4. 实现合同中的四种运动模式。冻结旧模式直接调用原实现；新的body_odom_rate是同传播表示对照。IMU两模式中不持续使用odom.pose/yaw/角增量或IMU四元数做额外航向观测，不做accel双积分。初始化只用已声明的一次源记录/工程配置。原六维策略不能直接复用硬编码索引到八维；本轮先独立/固定peer联合，可靠性策略适配留作下一阶段。
5. 实现事件接口和真实因果传播。只用接收已到达且源时刻合格的控制数据；源header/receive整数ns、每次传播的IMU和速度记录身份完整可回读。针对同刻、不同到达顺序、过期/未来、重复、乱序、缺口、单车IMU掉线给出显式状态。禁止离线最近邻和未来端点反向积分。先设计并记录缺口等待/失效/恢复策略，不能无提示切回Odom航向、填0或无限外推。
6. 在正式合成矩阵前提交并冻结代码、参数协议、噪声/初值/bias随机游走、时间门槛、种子和生成真值方式。工程选择可自行决定，但不能把厂家固定协方差或5秒候选统计当已标定，也不能通过T10终点/视频挑值。说明系统在哪些运动/几何条件下bias不可观测或弱可观测。
7. 意义明确的测试至少覆盖：恒定/时变bias、±yaw wrap、有限差分Jacobian、非零初始朝向/倒车/侧向速度、异步顺序、同刻重复、超时缺口与恢复、单位/轴反号负例、关闭回归、独立/联合交叉更新。合成比较正常/弱墙距/有偏gyro/有偏测距/速度滑移或生成器失配；每类固定若干种子，先小矩阵验证，再有预算地扩展。保留不改善和恶化结果，不为制造收益只选同模型理想数据。
8. 新CLI按合同实现--events-jsonl、--config、--output；输出run/config/estimate/decisions/summary，记录来源/假设、拒绝、bias和pose协方差含义。需要更改合同才能实现时，先在自己目录写接口差异提案，不让B猜接口。
9. A不需要下载现场bag或视频，也不运行留出包。完成合成与源/数值回读后发布独立草稿PR。HANDOFF必须给确切源码提交、协议SHA、测试与合成矩阵计数、失败模式、CLI示例、供B生成配置的精确schema、实际耗时与可取得结果归档/SHA。不要仅留下沙盒本地路径让另一窗口无法取文件。

有效工作预算约3–5小时；给每个量化批次设运行上限并持续保存阶段日志。完成后即归档，不为凑满时间重复测试。若平台中断，用HANDOFF恢复。最终清楚区分“模型实现/合成验证完成”和“现场精度仍未验收”。
