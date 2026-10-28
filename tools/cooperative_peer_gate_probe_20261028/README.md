# 普通peer目标排除门控开发核查

算法读取版本固定74fa210e7cf6aa322eaebce19530510edb605d22，19个依赖SHA见frozen_manifest.json。G1已含pseudo-Huber；G2只是新peer准入，不是新鲁棒损失、新可信性算法或正式验证。

`PEER_GATE_FROZEN_ROOT`必须指向按manifest取得的独立源码树；import时校验所有19文件。实际源码、输入与结果在Git外任务根，不修改基础核。`prepare.py`核验原24单元后生成唯一新输入适配器；`probe.py`包装原JointReplay/WindowGraph；`records.py`只记录外部来源。`runner.py`冻结精确45条索引，先checkpoint后complete，拒绝覆盖/自动重试，带本轮6小时UTC截止。

`test_probe.py`检查数值等价、单位/全拒绝、helper隔离、前缀、真实目标与joint prior；test_index.py拒绝缺项等伪全集；test_export.py证明旧24单元转换不构造估计器。历史source snapshot没有.git，原CLI元数据测试需在19文件完全相同的Git检出运行，失败环境日志保留。

`evaluate.py`是分离公式只读评价/核验，不导入在线估计器；`make_report.py`只生成预定全部seed的紧凑图表。主要结果和复核入口见同名docs目录REPORT/METHODS/COMMANDS/HANDOFF。不要重跑已完成矩阵；优先对归档做readback到新的Git外目录。代码中的allow_all/reject_all仅是合同测试，不是可选矩阵方法或阈值搜索接口。
