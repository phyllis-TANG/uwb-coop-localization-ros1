# 协同定位逐车完整性：首轮强基线

已完成seed101三个冻结生成器受控复现案例、B0/B1/B2和独立核验，未改G1主轨迹。**机制层面选择A：成熟历史SS已能发现另一车损害，收缩新方法主张。** 不意味着所有AL/所有时刻满足完整性需求；不是概率认证或实测定位精度验证。

先读[REPORT](REPORT.md)，完整模型/近似在[FROZEN_SPEC](FROZEN_SPEC.md)，原先冻结方案[PLAN](PLAN.md)，[文献实际范围](LITERATURE.md)。[全时段/全敏感性CSV](results/ALL_SENSITIVITY_METRICS.csv)、[逐车轨迹/误差](results/trajectory.csv)、[逐时刻四锚统计](results/B1_STATISTICS.csv)、[逐源SS](results/ss.csv)、[声明CSV.gz](results/declarations.csv.gz)、[越限/延迟事件](results/episodes.csv)、[确切运行及SHA](results/RUN_INDEX.json)。报警/声明是工程定义，不把graph accepted当安全。

[实际命令/只读续接](COMMANDS.md)、[归档可取得性](ARTIFACTS.json)、[中文HANDOFF](HANDOFF.md)。本轮只新增指定tools/docs目录；不扩seed/实包，不自动合并。
