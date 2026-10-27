# B端读取接口 quality_fgo_v1（先行交接）

本轮输入沿用PR58/59的单车**消息级**events.jsonl(.gz)，不从包里重提数据、不改B目录。`kind/case_id/record_index/source_file_sha256/topic/header_epoch_ns/receive_epoch_ns/value`保留；Odom pose/角速度、IMU轴/frame/单位和raw UWB与原接口相同。epoch ns严格整数。quality原NaN/null不参与打分，输入日志仍记录缺失来源。真值/故障标签只在评价文件，不能交在线端。

新入口：`tools/single_car_quality_fgo/qrun.py --events-jsonl ... --config ... --output ... --max-seconds 120`。输出必须为不存在的Git外目录。配置`interface_version=quality_fgo_v1`，`group=Q0/Q1/Q2/Q3`、`base`为冻结PR58配置（Q0/Q2 arm=F0，Q1/Q3 arm=F3），`quality_enabled`只在Q2/Q3启用，`controller`所有项有value/units/source_kind/source/frozen_before_field_run，`timing.paced`区分加速开发与实际计时验证。接口源码提交、配置SHA和正式协议状态见HANDOFF/checkpoint；当前先行版本不能误称正式验证已完成。

必需文件：run.json/config.json/published.csv、input_decisions.jsonl.gz、graphs.jsonl.gz、quality_ledger.jsonl.gz、publications.jsonl.gz、availability.jsonl.gz、summary.json。CSV保存所有发布（缺失pose为空）；bool=True/False，JSON为bool/null。不要把缺失填0。

`quality_ledger`在主图更新**之前**不可改地记录每个关键帧×墙锚：factor_id=`group|state_ns|target`、publication_id、原raw中位数/P1/修正后值、全部target_dependencies（原index/header/receive/SHA/topic）、原quality=null、排除影子reference_record_id、XY几何/工程分数/符号残差、state/reason/连续计数、原sigma/名义信息、实际新信息倍率与sqrt倍率、information_admitted/factor_action、host冻结时刻。缺测actual倍率=null，不是停用0；unknown保留策略倍率并明确held模式，不是健康判断。

`graphs`逐发布记录main或每个被排除target的影子：独立prior及上一记录ID、输入prefix计数/摘要、当前Odom插值两端和每链原样本支持、活动window local/observations/states/weights/IDs、完整优化初值、候选/接受状态、首次角积分原依赖及marginalization_details。活动interval通过其end_epoch引用之前graph记录中的angular_interval，避免反复复制；前后prior、消费旧factor IDs、权重与线性化affine可独立重建。shadow其他链路新倍率全部1，excluded_target绝不出现在其因素或消元输入。source/parent和prior链构成完整可回读依赖DAG；排除图从初始化独立运行，不能把它叫独立真值。

`publications`记录主图输出和引用的冻结factor IDs。**actual_available_receive_epoch_ns先为null**，必须以publication_id连接`availability`获取输出数据已flush后的实际时刻，避免在尚未完成写出时伪造可用时间。availability包含data_flushed_host_monotonic_ns/UTC ns、共享host anchor、映射到原receive clock的available_receive_epoch_ns、1秒等待+计算+排队后的actual_release_delay_s、完整处理耗时。原内核CSV中的单图耗时只作原意诊断，不能替代影子/监测/主图/写出的总成本。

正式验证采用同机4独立进程、每输入相同anchor、按记录receive实际paced，主指标用实际host单调经过时间映射，包含调度/排队。本实验是本机离线回放，不等于车载ROS实时保证。开发加速的timing_mode另标virtual，不混用为实际延迟。

状态：normal(1)、downweighted(.10)、disabled(0)、unknown(保留上次策略倍率，初始1)、recovering(.25)。分数是绝对排除影子误差/.20m，阈值/确认/恢复见SPEC和配置，不是NIS或保护级。指标false-positive只针对合成已知正常/健康UWB，实包只能称降权/停用占比；故障检出与真正降低位置/yaw/bias误差分别汇总。旧Huber不记新增贡献，旧prior污染不因后续停用消失。
