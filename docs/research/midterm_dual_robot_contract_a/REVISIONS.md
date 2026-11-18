# 版本与兼容性

DUAL-A-V1早期接口发布于 e45ca6d5940ff9f28233f03fb3502d5ed7004817，普通PR #131。CONTRACT_READY.json列出的23个文件保持逐字节不变。

后续提交仅新增协同信息分析、两时刻规格、可选GMP代码/记录、固定输入代数复核、验证/决策/写作说明及最终哈希清单。没有替换model_id、预算、阈值、输入、检查器或schema；B可继续锁定早期SHA，无兼容性迁移要求。最终PR HEAD通过Git/PR单列。

归档身份注意：RESULTS_READY的source_commit是B代码完整SHA；单份证书的source_commit按冻结接口仍是共同起点。CONTRACT_READY自身不写当前HEAD，不进行自引用哈希；SHA256SUMS不列自身。

## 2026-11-18：检查器V2与正式只读验收

新增checker_v2.py及可复现证据锁/计时/原始数据核对工具；旧core.py、check.py和CONTRACT_READY列出的23文件保持不变。V2返回值/算术/量词兼容V1，增加输入内精确缓存与显式兄弟模块加载。

当前用户将正式确定性分母明确为44（16 J5/16 P4/12 N4），条件随机明确为240（P4/N4配对）。该口径覆盖原冻结HANDOFF的48/360计划；旧4个特殊N4占位按计划外保留，不补跑。新INTEGRATION和EVIDENCE_LOCK明确此修订；不静默修改冻结输入或旧archive函数。

CROSS_READBACK由PENDING更新PASS，原观测嵌入历史字段。VALIDATION_REPORT、DECISION_MEMO和写作说明更新当前事实；新旧44条一致性及计时按CHECKER_V2_READY发布，不等待B随机结果。最终SHA仍通过Git/PR报告，避免文件自引用。
