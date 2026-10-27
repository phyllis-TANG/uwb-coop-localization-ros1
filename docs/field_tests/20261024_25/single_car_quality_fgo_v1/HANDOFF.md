# 阶段交接：开发完成，准备冻结验证

工作树/home/ubuntu22/uwb-single-car-quality-fgo-v1，分支analysis/20261027-single-car-quality-fgo-v1；基准2b43ec9fef0ea22f0d35318b2f11e35c646cce6c，origin phyllis-TANG/uwb-coop-localization-ros1。2026-10-27 11:19 UTC开始，先行接口提交6116aa6574341b296d3538333fd23fe8ca7010b1已推送。断网后12:49核对无运行遗留、没有启动正式验证，因此从冻结前继续；旧结果均保留，无隐式resume或重复开发回放。

独立venv及Git外根/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts。已实现Q0/F0、Q1/F3原图与Q2/Q3逐链控制、每链独立排除影子、只作用UWB的冻结信息倍率、未知/恢复滞回、因果账本、实际paced可用时刻及原始角冲突诊断（不控制任何因素）。未改旧IMU/固定窗口模块、B目录、geometry/manifest或旧协议。没有实包/视频/留出/ROS/车辆操作。

当前测试：新30、冻结IMU43、原固定/顺序37，合计110项通过。32开发CLI全部DONE，开发读取器v2为32/32 PASS；6个重封SHA坏日志全部拒绝。首轮1个测试期望ID别名错误、schema异常类型测试错误、旧Q1缺weights字段的读取兼容错误及修正前后日志全部保留。Q1旧固定原图仅在控制关闭时解释倍率1，不篡改旧日志。旧PR58的96矩阵未重跑。

开发只用101/151，不参与正式的401/419/443；阈值/状态机与倍率数学从先行接口提交起未变，证明见checkpoints/02_rule_lock.json。开发seed101单链+.60m时Q3比Q1位置RMSE约.405→.065m，同时发生对其他健康链的误降权。正常该seed无降权，不能据此声明验证成功或长期误报概率。正式结果尚未产生。

下一步：提交全部代码/协议后启动唯一validation-v1：8场景×3新seed×Q0–Q3=96CLI，60秒/输入，4独立进程同anchor真实paced，预计约25分钟；每CLI90秒、整批2700秒上限，无自动重试或参数网格。首次启动不加--resume。中断只按case边界/严格源码协议与已完成输入输出SHA恢复；部分运行保留，不自动重跑，不宣称完整滤波器状态恢复。

接口quality_fgo_v1见INTERFACE.md、config.template.json/config.schema.json及examples；日志包含所有原记录/时间/参照依赖、分数/状态/原因、实际倍率和后验诊断，后者不反馈控制。实际可用时刻必须连接availability.jsonl，不能用state或单主图估计时延替代。正常误报按连续事件和每车/每链可监测秒数给分母；故障给全部与可监测事件分母。位置/yaw/bias误差、告警与恢复独立评价；停用当前约束不清除旧prior污染。

正式验证后只加审阅说明和报告；保留全部失败/未知/误判/恶化。创建面向main的独立草稿PR，不合并。最终源码提交/协议SHA/可取得归档和结论待验证后补齐。
