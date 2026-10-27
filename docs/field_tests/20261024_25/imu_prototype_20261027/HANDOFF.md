# EKF工作已保存，主线已转FGO

2026-10-27 09:50 UTC收到用户路线更正后停止，不再启动EKF试次。此目录属于保留的历史实现，不能当当前主任务完成交付。下一主线按112586ceb9ce674a083fb43f7d8afb7768a15aaf的FGO_REDIRECT.md执行。

- 分支analysis/20261027-imu-core；工作树/home/ubuntu22/uwb-imu-core-20261027，独立venv与Git外输出/home/ubuntu22/uwb-imu-core-20261027-artifacts。
- 已冻结执行源码b7a56b22d55e033f267ffb87055af64da313ef81；协议SHA256 `2a897ff6e84c2e952d7595b85ef770a8c4b8d1dcb4ecdb3a50ad753b51f9f0f0`。冻结后44项测试通过，日志tests-frozen-b7a56b2.log。
- 已实现默认关闭四种运动输入、每车4维/联合8维因果EKF、残余bias与工程Q、缺口/恢复、配置schema及CLI。旧六维模式调用原实现，未修改原算法或公共文件。
- 两轮开发smoke均保留；v2的4次CLI与逐段独立数值回读PASS。首轮39测试有2项测试假设失败，修正记录与原日志仍保留；后续44测试全通过。开发期间修正固定bias导数及回读采样步长，正式源码冻结在上述提交。
- 正式矩阵原计划120CLI/240方法/480分车指标，转向时仅37CLI完成，1个部分输出。未完成全矩阵、未生成正式整体性能结论。部分cell为gyro_timevarying_bias_seed31__body_odom_rate，run.json保持原IN_PROGRESS状态，不伪造DONE；外部03_fgo_redirect.json明确标记中断。
- 原checkpoint.json、全部输入/输出/配置/日志均保留，无重跑、未调阈值。停止时保留37个已索引DONE的SHA清单及部分目录各文件SHA，见checkpoints/03_fgo_redirect.json。没有访问现场bag/留出/视频，无ROS/串口/车辆操作。

可复用的是整数ns身份、轴/单位/时钟显式来源、真实dt及Jacobian/Q数值验证方法、无未来端点测试和可移植归档规范。FGO需另写角增量因子和含bias边缘化；不能把EKF结果或协方差当FGO验证。

本分支暂停，禁止自动执行原batch.py --resume。新FGO分支/checkout从用户指定更正提交建立，保留此树及现有结果。新任务预算沿原开始09:04:29 UTC累计记录，不借转向重置已用时间。归档/远端保存位置见后续FGO交接中的历史检查点索引。
