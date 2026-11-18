# 逐车水平保护级与发布时刻判定

在合同模型、噪声联合事件与认证外包成立时，真实天线位置落在至少一个保留矩形。给定实际发布点 e=(ex,ey)，对每个矩形 [l₁,u₁]×[l₂,u₂]，到 e 的最大平方距离为 Σⱼ max((lⱼ−eⱼ)²,(uⱼ−eⱼ)²)，由某个角点取得。对全部投影矩形取最大并将平方根向上取整至 10⁻³⁰ m，即模型条件下的候选水平 PL。只要输出仍针对相同状态时刻和坐标系，水平误差就受该值约束。旧 radius 的圆心取两轴总包络中点，程序始终按发布点重算。共线镜像和预算停止的 PENDING 叶均包括在内。

从仓库根目录复现样例（Python 3.10+）：

```sh
d=docs/research/midterm_dual_robot_contract_a
t=tools/midterm_dual_robot_contract_a/integrity_v1
python3 "$t/decision.py" "$d/integrity_v1/publication.json" "$d/precontract_v1/examples/normal.input.json" "$d/precontract_v1/examples/normal.composite.json"
```

输出见 expected.json。支持 B 平面原域与复合树、月球固定高度 P4/N4。检查器从 Git 固定对象加载；浅克隆需先 git fetch origin refs/pull/139/head。请求必须由发布系统绑定 case、seed、输入哈希、方法、车辆、坐标系、状态时刻和实际已发布天线 XY，位置单位 m。平面合同只有相对 t0，外部发布系统负责其绝对时间和 seed 绑定。月球 state_time 采用对应车辆的源时标，所有时间字段须换算到同一秒时标。decision_ready_time 指发布策略获得完整且完成核验的结果时刻，由执行端记录，不用离线复查耗时代替。deadline 为最迟就绪时刻，valid_until 为该状态记录的最后允许使用时刻，as_of 为查询时刻。这项证书约束 state_time 的误差；将其用于移动后另一个状态需重新认证。各时限均含等号。

PL≤AL 时 available=true；PL>AL 时 alarm=true。启动、未发布、未就绪、缺证、坏证、空域、迟到和过期均 available=false，alarm=false 表示未产生超限告警，原因另列。有效预算外包按同一半径规则。查询早于结果到达时不显示未来 PL 或超限告警。真值、故障类型和起止时刻不属于发布接口；事后评价可用首次实际告警时间计算延迟。

两车共享同一历元联合事件，可同时推出各自误差界。要推整段任务风险，需另计各历元联合事件失败、模型失效、故障未覆盖和超时策略；时序相关时不能将逐历元概率相乘。该段尚无任务风险预算。
