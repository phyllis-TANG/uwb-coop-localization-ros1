# 中文交接：质量FGO既有失效归因

独立工作树`/home/ubuntu22/uwb-quality-fgo-diagnosis-20261027`，分支`analysis/20261027-quality-fgo-diagnosis`；共同基准`868349b543a03a6a713d1675e1d4ada7d905410c`。冻结执行源码仍为`12a1d94379b58c5a759b1698425fb90d48587609`。预登记先提交`88a0e73`，然后仅执行D1/D2。原双车目录HEAD `115b17deb2f848e596d1638a0b45cf360deae947`、分支和干净工作区保持；其余注册检出未切换/修改，最终只读清单在新归档worktree_readback.json。无适用AGENTS。

已完成用户要求：七文档完整阅读；原归档2138文件、复用1298正式文件和96运行源码/配置SHA核验；8个健康链误降权逐事件原始依赖/同期影子/主图/状态机/入图倍率/历史链；common全部3seed；0–20s及>20s位置/yaw/bias和倍率/冻结窗口/prior分别分析；两项预登记最小诊断；一页中文结论、逐事件表与8张全时段同期图、全部3seed和D1对照图、反例/未知、最多两项后续建议。

主要结论：健康scalar完全未变，但健康目标的影子仍以g1消费故障node10，导致8次误归因；ramp443更在故障结束8s后误降。common的Q3全部3seed yaw/bias恶化，419位置也恶化；只取消419晚发node2抑制可改善恢复位置但不能消除全部恶化。59.01s固定快照替换prior证实旧历史仍改解，但419/Q1的yaw反而变差，不能称删除prior必有益。完整证据/边界见CONCLUSION、REPORT、EVENTS。

必要检查全部通过：135936条raw依赖、8496次入图倍率、4104个已知分数、4248个影子排除/恒1、6372图链和3762prior链；独立4248次FSM与4248次sqrt(g)残差/J、90指标对原值、6主图重建与28快照控制/有限差分。D1控制严格吻合原Q3；401/443改动为空的反例相同。原始证据末次完整复核与首次verification JSON完全相等。读器开发三次schema失败日志保留，没有改v1。正式96组重启0；阈值改动0；ROS/实车/串口启动0；未修改原数据。

新证据本地根`/home/ubuntu22/uwb-quality-fgo-diagnosis-20261027-artifacts`；归档13,286,380字节，SHA256 `d71635a4883cf0ad1ac2227dcd1f855da1164e9eeea2ae1528aa317418eb1def`，47份新证据/source/log加manifest逐项核验。已写入NAS独立`quality_fgo_diagnosis_20261027_12a1d943`目录并完整读回SHA匹配。还需原v1归档（293,750,470字节，SHA `7a5ff137…dc3ab8`）取得全部原输入/图；新归档不重复这些大数据。精确路径、SHA、取得命令见ARTIFACTS.json。

分支仅新增用户指定`tools/single_car_quality_diagnosis/`和本目录。线上内核、B端、双车工具和公共几何/清单没有变化。结果约7MB入Git；47文件大证据在Git外。结果提交`2006474b31f312e5a85295845ef2d648ba0bd406`已推送并创建[草稿PR #63](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/63)。交付收据与SHA索引为随后纯元数据提交，最终HEAD以PR分支为准；未自动合并。

继续工作时先读INTERVENTION_REGISTER和REPORT的未知项。不要再跑正式96组或用本轮暴露数据调阈值；已有归因试验不是独立验证。两项下一版建议都需要另建版本、预冻结和未暴露seed验证。当前没有待补的授权范围内分析项；真实数据/B外部验收、在线参照可靠性规则和可因果重建prior尚未验证，不能把它们当本轮完成的功能。

合并前导出口径修订：Q0/Q2的缺失bias/误差不再用0占位；时序、快照和两张Q2图已同步重新导出，两个针对性测试通过。有效零bias仍计算误差。原两份证据归档保持原SHA；本次正式矩阵、主图重建、快照求解新增次数均为0。现行导出及补充归档以EXPORT_SEMANTICS_REVISION.md、review/bias-null-provenance.json及ARTIFACTS.json为准；旧review/provenance.json中的源码SHA描述修订前实际计算，不能混称现行导出源码。PR #63继续保持草稿、未合并。

本次独立补充归档：13,166,330字节，70文件加manifest，SHA256 `014373c58d9a3a0fdfd997ec4cbe7e5e0eae0878319003951c65a64f51db0d0a`，NAS完整读回匹配。路径见ARTIFACTS.json。旧归档只保留历史导出口径；现行时序、快照与Q2图应读取本分支/补充归档。
