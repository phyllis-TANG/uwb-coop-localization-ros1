# 版本与兼容性

DUAL-A-V1早期接口发布于 e45ca6d5940ff9f28233f03fb3502d5ed7004817，普通PR #131。CONTRACT_READY.json列出的23个文件保持逐字节不变。

后续提交仅新增协同信息分析、两时刻规格、可选GMP代码/记录、固定输入代数复核、验证/决策/写作说明及最终哈希清单。没有替换model_id、预算、阈值、输入、检查器或schema；B可继续锁定早期SHA，无兼容性迁移要求。最终PR HEAD通过Git/PR单列。

归档身份注意：RESULTS_READY的source_commit是B代码完整SHA；单份证书的source_commit按冻结接口仍是共同起点。CONTRACT_READY自身不写当前HEAD，不进行自引用哈希；SHA256SUMS不列自身。
