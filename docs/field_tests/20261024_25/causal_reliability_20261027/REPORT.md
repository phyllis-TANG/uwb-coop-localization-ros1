# A端同六维EKF结果审阅

本轮已经执行：同PR46/48六维SE(2)因果EKF的9组比较，60个共享输入组合（80计划行去重20）、每输入48s，计算365.36s；89项相关测试通过。执行源码提交 `7896c82d2454b67ea388341484a93c2265a209fb`，协议与源码指纹见RESULT_INDEX.json。全部是开发证据，重复使用5个配对种子；角色、场景和帧都不增加独立seed数。没有使用PR47四维估计器或旧480组作为本轮结果。

## 最有用的结果与反例

以下为5种子故障阶段[12,30)逐车XY RMSE的算术均值，单位m；按每行自身的state_epoch_ns对生成真值评价，无轨迹配准。正常阶段[0,12)、故障阶段、恢复阶段[30,48)及所有方法均保留于分车表。

| 条件与评价车 | independent | joint | Huber | gate+cap | shadow-only | gate+cap+shadow |
|---|---:|---:|---:|---:|---:|---:|
| 持续peer偏差，Car1 | .030888 | .173516 | .138907 | .164626 | .046701 | .033803 |
| 持续peer偏差，Car2 | .036095 | .181739 | .142736 | .165672 | .052706 | .040377 |
| Car2弱墙+正确peer，评价Car2 | .276911 | .168093 | .168093 | .168093 | .224020 | .224020 |
| Car1弱墙+peer偏差，评价Car1 | .172437 | .673959 | .668254 | .666656 | .310032 | .306537 |
| Car2弱墙+peer偏差，评价Car2 | .276911 | .474394 | .455576 | .459236 | .168810 | .277997 |
| Car1自洽故障，评价Car1 | .801582 | .805555 | .805199 | .805555 | .802778 | .802778 |

1. **有偏peer确实可同时损害两车。** 本设置下反馈式joint累积较大误差；Huber优于反馈gate+cap。非反馈版本降低这类积累，但不能把组合的全部收益归因于gate或cap：shadow-only控制已降低很多损害。
2. **保护会损失正确协同。** Car2弱墙时正确peer使joint从.276911降至.168093；非反馈组合仅到.224020。健康Car1在该条件joint从.030888升至.033900，组合为.032030，仍保留对另一车的小损害。
3. **组合会比消融更差。** Car2弱墙+peer偏差时shadow-only为.168810，组合为.277997；这组偶然有利的故障/漂移几何不支持“错误peer可靠”或“gate必然改善”，却是必须保留的反例。
4. **自洽错误仍失败。** 两角色受影响车各方法约.80–.82m，局部墙几何强且P为PSD也不能证明可信。热图相对independent接近零的灰色在这里意味着基线和候选都错。该条件Odom-only可暂时更小，但它仍只是带噪估计，评价真值来自生成器。
5. **正常代价不为零。** 名义故障同长子窗中joint与组合平均变化约毫米以内，存在逐种子变差：seed233 Car1的joint相对independent增加.002351m RMSE；不把小均值改善写成显著收益。正常场景没有gate拒绝或限幅，亦不能由5种子证明长期误报概率。
6. **限幅单独作用覆盖不足。** cap-only两车共26次clip；gate+cap仅1次；组合25次。大量gate-only/gate+cap结果相同，不声称已充分验证cap改善。没有为追求触发而更改0.06/.35m参数或扩大网格。

## 反馈、恢复与时间语义

原三基线默认无插件完全不变；gate/cap/Huber在同一个六维滤波器内改变已准入peer增益/反馈。gate+cap提交缩放后的均值和Joseph协方差；非反馈组只发布保持修正，内部状态和shadow逐事件等于independent；非零保持修正的输出协方差为null。工程协方差、PSD或cap都不是真实误差上界/PL。

固定Car1→Car2，200ms链路间隔、60ms已到达twist支持、原时间/去重政策保持。car2 gate转换为0是固定排除反向输入的结果，不能解释为反向传播验证。normal/peer_bias/pulse/ramp的role=car1只是去重规范索引；其余role表示墙支持/故障或丢odom的车辆。

gate-only、gate+cap各8次闭合/8次重开；组合29/29。精确事件保存在events.jsonl.gz，首次发布可见变化在gate_publication_transitions.csv，状态时刻与发布可获得时刻分列。离线批处理时钟不是车载实测报警延迟。

预登记恢复指标是**相对independent的误差增量回到0.03m内并持续2s的窗口开始时刻**，不是绝对位置恢复，也不是该开始时刻已经可确认。非反馈组最早恢复窗口均始于故障后.05s；反馈组部分延至7.15s；两者都需再观察2s确认。independent/shadow在自洽故障下可同时错，不能用此相对指标掩盖绝对误差。96个被删失项均属Odom-only的方法-车辆条件，不是96个独立失败运行。

## 独立回读与可用性

在复制的源码/结果目录执行，未依赖原工作树路径。独立工具不导入估计器、生成器或评价器，核对全部417,300输入事件及3,755,700方法决策、29,040发布记录/522,720逐车状态、3,240指标行，重算三维peer几何、六维H、准入、gate、增益/限幅/Joseph/保持和误差。数值失败0。20个去重角色另行重生成输入并核对相同SHA，没有新增估计器运行。

522,720状态行包括1,080未初始化、3,690陈旧保持、27,520几何退化但数值有效、490,430正常滤波保持；均保留。不可用/退化行不是独立试验。对协方差有限/对称/PSD的检查不等于统计校准。

计算成本分列core和私有shadow。例如48s输入的平均core耗时joint约182ms、gate+cap+shadow约195ms、shadow-only约223ms；所有比较实例都维护辅助shadow，其成本另列。串行Python诊断框架及日志I/O不能直接换算实车实时性能。

## T10与证据边界

严格模板实际编译返回BLOCKED：14组来源字段待补，归结为8个基线阻塞项（两车initial_room_pose、antenna_body_xy_m、odom_clock、range_clock）。已有近似高度保留C1=.17/C2=.20m，未知误差不填0。初始候选记录保留原index/header/receive整数ns，未把候选升级为已批准初值。仅确认冻结起点没有B端新交接，不推断B当前工作的完成状态。

没有读bag、没有T10定位或现场ATE/RMSE；视觉参考仍not_accepted。T09/T11/T13/T15没有定位回放或调参。合成事件的source_file_sha256是沿用基线的fixture身份token，真实输入文件SHA在run.json输出清单，规范事件内容SHA在input_sha256；不将其伪称实测bag SHA。

## 复核入口

- [规格与反馈/协方差定义](SPEC.md)、[冻结协议](frozen_protocol.json)、[结果索引](RESULT_INDEX.json)、[全部计划/失败/去重索引](results_summary/experiment_index.json)。
- [逐车配对摘要](results_summary/paired_seed_summary.csv)、[重点数值表](results_summary/key_findings.csv)、[独立回读JSON](results_summary/independent_readback.json)、[T10精确缺项](results_summary/T10_BLOCKED.json)。
- 三类图：[轨迹](results_summary/peer_bias_trajectory.png)、[误差/监测/故障](results_summary/peer_bias_error_monitor.png)、[配对代价](results_summary/paired_fault_delta_reviewed.png)；[计算成本](results_summary/compute_cost.png)。旧自动图表保留在归档report/；reviewed版只修正色条布局和标签解释，不覆盖旧证据。
- 全量逐时刻数据、smoke与旧源码、日志/配置/哈希见artifact_manifest.json登记的NAS归档。所有科学数值与阈值在正式运行中未修改。
