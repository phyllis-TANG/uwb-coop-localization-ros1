# 中文交接：B端历史单车IMU因子图

**已完成两历史开发包的F0–F3条件性运行与独立核验，未作现场精度结论。** 从`112586ceb9ce674a083fb43f7d8afb7768a15aaf`建独立分支`analysis/20261027-single-car-imu-fgo-eval`；工作树`/workspace/work/uwb-b-imu-fgo-eval-20261027`。只新增B的工具/文档目录，A内核、旧入口、原bag、公共参数和其他窗口均未修改。

旧EKF草稿`6b96801`已推送独立分支并保存HANDOFF、代码、venv和日志；它只完成语法检查，未正式导出T08/T10，不误报成可用新包。转向后0个新EKF实验，原PR45/51等T08/T10资料保留。第一阶段检查点`eca7e8b`，完成20,994条原消息独立核对、真实IMU/整数时间身份包、旧三组564行复现，最大分量差0。

A为PR58冻结执行`e3a20fe04a6d53973696ec055dbc71eb135e0f77`；B八运行协议/适配器预先冻结`db36166`；**实际干净组合提交`f00c8743ac9c47d967817af448d3cd3fc80e8b79`**，另保留执行分支`execution/20261027-fgo-e3a20fe-b-stage1`。A后续报告提交5dd0a54核心不变；未重复A的96次合成。

完成：004023/005135各四臂，共8名义运行、752发布；全部有限，736图接受、16启动预测，0求解失败/缺角/Odom角回退。四臂共同有效分别94/96、90/92，全部与共同口径均保留。新F0的188条输出与旧图完全一致。F3最多21帧84变量、瞬时22帧88变量。B独立重算558角区间/11,718片段、554个cost、全部438次边缘化的交叉信息/affine/常数与唯一消元；八个真实41秒receive-prefix控制的304条非耗时记录逐字段一致。六个重封SHA的坏结果副本全部拒绝，另有八组原包负例。B33、A新43、旧25项测试通过。

响应：F2/F3相对F0最大base变化约1.0–1.5cm、航向约6–9deg；这是输出变化，不能读作精度收益。完整bias/覆盖/失败/初次跳变/耗时和共同有效结果在[REPORT](REPORT.md)、[逐阶段来源和命令](results/STAGE2_SOURCE_VERSIONS.json)。F3零偏轨迹不等于真实标定，云端耗时不等于车载实时。启动/预测/优化新初值/失败回退航向已检查；全活动warmstart向量仅有固定源码审查、没有独立逐元素日志，限制已列。[源码审计](FGO_SOURCE_AUDIT.json)

仍缺最小信息：①历史gyro→body轴/符号证据；②历史采样/header/receive打戳版本绑定与物理时钟误差界；③物理odom积分原点与历史几何中心偏移对应。严格物理分支继续BLOCKED；此次只跑显式工程假设配置，不用填零解除未知。原平移表达仍依赖上游Odom yaw，未宣称统计独立。连续精度结论另需独立合格参考。T08/T10本轮不扩跑，T09/T11/T13/T15未打开；没有视频、ROS、串口或车辆操作。[参数证据](PARAMETER_EVIDENCE.md)

Git外根`/workspace/work/uwb-b-imu-fgo-eval-20261027-run/`：`results/inputs_002`、`A_inputs_001`、`F0_F3_001`、`F0_F3_readback_002`、`prefix_controls_001`、`FGO_negative_001`、`FGO_report_001`；日志在`logs/`。旧版本和开发回读001保留。可迁移归档/完整SHA/远端实取核验见[ARTIFACTS](ARTIFACTS.json)，不是要求其他窗口使用云端绝对路径。

续跑只新建目录，不加resume：从本分支取得B工具，按[README](../../../../tools/single_car_imu_fgo_eval/README.md)取得确切A或组合提交、校验归档和输入SHA后运行。当前名义和核验已经结束，无需凑时长重跑。若补证或改模型，另冻结新协议，不覆盖本结果或恢复旧EKF。草稿[PR59](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/59)目标main、依赖PR58，未合并。GitHub固定提交实际重新下载40,991,617字节归档并核对364个成员全部通过。会话自09:37 UTC至约10:50 UTC约73分钟；最终时间/来源见[CHECKPOINT](CHECKPOINT.json)，低于预算。
