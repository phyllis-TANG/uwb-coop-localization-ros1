# IMU接入前审查交接

先读REPORT.md、READINESS.json、INTEGRATION_PLAN.md。已核验T08/T10两开发包、12,063条IMU与12,046条odom、12,046唯一配对；T10 4,619条与PR51逐值一致。16项测试通过，当前来源采集器只在Python3 fixture测试，未访问实车。

Car2归档上位机：odom heading积分另一个串口角速度字段，IMU gyro/quaternion另算；上游MCU依赖未知，归档源码与历史运行二进制未绑定。Car1底盘源码缺失，不能套Car2结论。两车原始gyro有偏移，固定协方差未标定，厂商四元数不作绝对房间yaw。

本轮没有加入IMU融合。下一阶段可先编写默认关闭的body速度+gyro_z−bias原型，以替换旧角运动输入，避免重复约束；来源补采命令已在VM_COMMANDS.md，用户执行即可，不需要重录路线或启动ROS。

冻结审查提交d3439ebefc36eeee184131038b2f209838431cc4。保留原件/公共manifest/geometry/PR54冻结结果；T09/T11/T13/T15不解码或定位评价；不刷固件、重启设备、发串口或运动命令，不自动合并。

更新：先读OFFLINE_EVIDENCE.md。已新增两历史包的关系核对，4包8组共19,953对（含前轮重叠），8项本目录测试通过。用户不在实验室；可以直接推进默认关闭的gyro/bias离线原型，车端源码补采暂缓并行，不作为编码阻塞。不把消息一致性升级为固件识别或精度验收。
