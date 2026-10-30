2026-10-30 研究收敛检查点

基准 main: 396eded0d9eca4b38e6400138949a5e4c950da88。
只新增 tools/research_convergence_20261030 和本目录。未修改估计器、冻结核、输入登记、阈值、公共几何或旧结果；未执行定位器或重跑70单元。

阅读顺序：REPRODUCTION.txt -> CASE_STUDY.txt -> TARGET_CARD.txt。
机器证据：IDENTITY_AUDIT.json、ADAPTER_CHECKS.json、CASE_DATA.json、RECOVERY_DIAGNOSIS.json、SOURCE_RECEIPTS.json。

本轮进展：
1. truth SHA 失败已定位到本机三角函数舍入。独立120/160位计算都得到原登记的完整truth文件SHA；仅两个Car1 yaw字段不同。诊断环境下原两项adapter测试通过，原生Windows一项失败保留。
2. 共同墙偏差完整案例把逐车HMI、可用性、强基线假设与实测承接放在一起，不将监测收益描述为轨迹精度改善。
3. 从已有序列定位了恢复代价：28秒偏差结束后12秒，Car2持续报警；假设AL=.10m时其中平均11秒误差未超限。下一小题优先检验恢复可用性，不直接解警。

仍未完成：原事件归档字节读回/完整跨平台事件身份；新恢复判据的必要性与新颖性；实车B2及独立位置真值。前两项中truth定位已完成，不再重复泛问“数据在哪”。
本目录为证据整理与研究决策，不是新算法效果或安全认证。
