# 实测与Moon_1接口契约

|项目|现有证据|可用范围/缺口|
|---|---|---|
|UWB身份|Car1=node_1，Car2=node_0；peer互指，墙节点2/3/8/10；本轮逐消息核实|距离m，保留两个方向及各自时刻；不能复制成独立同刻约束|
|运动|各车局部odom位姿与twist，IMU gyro/accel|不是Moon_1的合成全局XY增量；不能直接差分后假称已对齐房间坐标。odom位姿/twist可能相关，IMU与odom内部融合关系需核查|
|高度/天线|18日人工安装：Car1 .17m，Car2 .20m；水平杆臂(.08,-.06)/(.12,-.08)m，相对近似底盘中心|不是Moon_1世界竖直1.16m；近似中心与odom原点对应待核实，旧notes .20m并列保留|
|信标|17日重装人工测量配置，历史18日分析沿用|不是Moon_1人工四角布局；不可跨安装日期套用；原始配置另含旧校正，不自动应用|
|时间|bag接收时间、各topic header同时保存|接收关联仅工程假设；时钟状态文本先后执行，不是同步标定；不由header差直接修正采样时间|
|噪声/偏差|raw样本、历史静态校正与工程权重|本轮不重新拟合；Moon_1 .04/.02/.5不迁移；旧实测.2/.03等也不称全面标定|
|参考|历史人工起终点和部分卷尺值；无连续真值|只能有限端点/静态几何参照；不当强约束，不计算全程RMSE/覆盖|
|质量与标签|quality非有限字段保存null；实验备注在reference|不作为估计权重/故障真值，挑战包不自动标NLOS|

历史来源：datasets/field_raw/20261018/README.md、notes/live_field/antenna_mount_survey_20261018.txt、clock_status_end_20261018_055752.txt；docs/field_tests/20261017/session_config.json；two_car_updated_comparison_20261022/protocol.json；20261024_25/two_car_imu_fgo_20261028/REPORT.md。

reference与measurements在文件层分开；当前是原始观测审计导出，尚无本轮estimates。后续适配应先选用已有实测SE(2)与杆臂实现；若要与Moon_1六时刻XY模型比较，需显式定义局部到全局变换、运动因子及相关性，不能直接强行改字段名。历史M0—M3名称在不同实验含义不同，不能横向混同。
