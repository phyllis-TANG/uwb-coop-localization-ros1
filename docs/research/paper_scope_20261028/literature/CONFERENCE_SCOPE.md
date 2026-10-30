# IV2027官方日程、主题与月球类比

核实日期：2026-10-28（Asia/Shanghai）。检索服务曾返回400，但普通公开HTTPS成功下载官网全文；以下依据官方页面正文，非第三方会议日历或往届日期推算。网页SHA见provenance.json；网页内容仍可能以后更新。

## 官方来源

- [Announcements](https://ieee-iv.org/2027/announcements/)，Important Dates。
- [Call for Papers](https://ieee-iv.org/2027/contributions/call-for-papers/)，Important Dates与Topics of Interest。
- [Information For Authors](https://ieee-iv.org/2027/contributions/information-for-authors/)，Paper Submission Instructions及Manuscript Preparation。

| 事项 | 官网当前明示 | 解释 |
|---|---|---|
| 正式论文提交 | 2026-11-15，23:59 AWST | 作者页给出时区；AWST=UTC+8，与香港/北京同一时钟。现已核实，不能再只标导师目标 |
| 通知 | 2027-01-15 | 官方日程，后续变更以公告为准 |
| Camera-ready | 2027-02-01 | 不当作首次提交截止 |
| 会议 | 2027-06-15–18，Perth, Australia | 官网页眉 |
| 篇幅/评审 | 常规6页含图及参考；作者页另允许最多8页、额外页收费；匿名首稿 | 本交付是导师选题材料，不是正式投稿稿件 |

官网未在所读页声明AoE；不得把23:59 AWST自动改成AoE。作者页还说明LLM生成稿件被禁止、轻量语法/拼写编辑允许；后续论文内容需由作者自行完成并遵守届时要求，不能把本讨论材料直接当成投稿成稿。

## 官方主题与两题的联系（本次判断）

官网Topics of Interest明确列出Connected and Cooperative Vehicles下的Cooperative Perception and Localization，以及Sensing and Perception下的Localization and Mapping、Multi-sensor Fusion；还有Off-road Autonomous Driving和Simulations and Real-World Testing Methodologies。

- **A联系直接**：双车测距采用决策与错误传播可对应协同车辆定位。需用车辆运动、相关状态、有限链路/到达延迟和实际可用性解释意义，不能只讲抽象异常分数。
- **B联系可论证但更窄**：单车质量监测对应定位/多传感器融合；要说明对智能车辆的定位失效与恢复有何具体价值，而非仅室内标签定位。
- 上述是主题匹配判断，**不表示录用保证**。当前贡献未成立、独立参考未验收，不宜因官方截止临近而降级对照或把动作指标写成精度。

## 月球背景单列

既有[LUNAR_COOPERATIVE_LOCALIZATION_OUTLOOK](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/blob/74fa210e7cf6aa322eaebce19530510edb605d22/docs/research/LUNAR_COOPERATIVE_LOCALIZATION_OUTLOOK.md)把有限固定信标与移动伙伴用于绝对定位受限任务。这能解释资源约束和研究动机，但不提供新算法差异。

室内墙锚/两车只验证某些有限参照、测距故障和运动约束下的方法行为；人体/家具遮挡不等于月面传播，商业UWB、平面地面模型不代表低重力、地形高差、真空、热循环或航天级射频。未做专门环境、传播模型与地外类比实验前，不能称“月面验证”。

面向IV可优先以协同移动车辆方法为正文对象，把月面仅列未来应用/动机；若导师要求月球为核心，应补充对应任务需求与环境证据，再考虑更匹配的投稿场景。背景选择不能替代本文与P1–P9的方法区分。
