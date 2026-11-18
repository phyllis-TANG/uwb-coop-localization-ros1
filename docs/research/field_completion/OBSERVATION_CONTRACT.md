# 逐项证据合同

|项|已核实证据|本批用法|仍不能声称|
|---|---|---|---|
|原始身份|PR128五包SHA、逐消息归档，本次五包raw/portable接口再次相等|原bag只读，包与方向身份显式检查|重新采集或独立盲测|
|odom原点|消息frame为car*/odom_combined，child为base_footprint；原始antenna_mount_survey明确pending verification|沿用人工近似底盘中心杆臂作为条件假设|已证实base_footprint就是测量的几何中心|
|杆臂/高度|20261018人工记录(.08,-.06,.17)、(.12,-.08,.20)，水平x前y左|SE(2)旋转杆臂+固定高度，所有方法一致|完整姿态外参/高度不确定性融合|
|世界设施|历史Oct17墙锚人工配置，Oct18沿用|复用冻结坐标及静态校正|无误差锚点或跨位置准确校准|
|初始参考|三个历史动态包有起点/朝向假设；045116索引只说明旧聊天曾有起终点，当前便携reference无数值|本批四包统一墙观测+全段odom初始化，删除全部起点先验；不借用另一包坐标|初始化是独立观测、精确先验或真值|
|时间|各topic receipt/header完整保存，时钟状态文件三机先后执行|统一bag接收时间；每方向分别聚合；保留差值与缺测|接收差就是延迟；header差就是可直接施加的时钟修正|
|测距误差|各链路原测距、历史墙校正、工程sigma=.2m|修正只应用一次，peer无预校正；F2/F3为明确受限模型|实测噪声已知高斯、月面噪声已标定或真实故障已定位|
|运动|局部odom及IMU原消息，静/动态由实测odom支持|原SE(2)相对运动sigma=.03m/sqrt(s)、yaw=2deg/sqrt(s)，不新增IMU因子|轮速独立真值；odom/IMU相互独立|
|参考|013206人工静态天线坐标；三包旧人工末点；045116无可追溯数值参考入口|reference只在最终评价读取，013206明确校正训练重用|连续轨迹RMSE、覆盖率或罕见风险验证|
|相关性|双向方向差、异步取样；时间点共享硬件与校正|只聚合一条peer，整包报告，不把时刻当独立实验|聚合后独立白噪声或跨包完全独立|

结论：能完成软件接入、观测审计和条件数值对照；无法从现有文件恢复精确安装原点、采样同步、完整轨迹真值。没有修改时间戳、原始坐标或观测来强行消除不一致。

证据路径：datasets/field_raw/20261018/notes/live_field/antenna_mount_survey_20261018.txt；clock_status_end_20261018_055752.txt；datasets/field_raw/provenance/user_confirmations_20261020.md；docs/field_tests/two_car_updated_comparison_20261022/protocol.json；PR128便携reference与measurements。
