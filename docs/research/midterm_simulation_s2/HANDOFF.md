# B端交接

已完成：PR97固定基准独立工作区；6时刻XY+单常值bias四对照；运行前24c7841提交；无噪声数学检查、3开发seed含噪/初值/有偏prior实验；逐车结果、配对成功表、负面/失败、图及独立重算。只新增tools/midterm_simulation_s2和docs/research/midterm_simulation_s2。

关键边界：192条件×4=768方法运行，只有3个独立随机开发seed。403次不满足预登记optimality阈值，不能隐去或事后放宽。256个方法案例参考数据秩亏，解处满秩不抹去此事实；CHECKS保留精确退化解/null协方差及故意不收敛。B2知道链路、B3另知幅值；全局位移强假设。小样本最终迭代误差改善不是正式方法验收。

未完成/等待：正式验证0次，未分配正式seed；未消费A的固定提交及S2_INTERFACE。详见VALIDATION_PROTOCOL_DRAFT对齐表。先解释/修订开发求解协议并保留旧结果，再冻结双方共同设置；不得直接运行正式矩阵。本轮seed26011601–26011603已暴露；现有PR97和本地历史seed记录不可冒称新确认。

路径：/home/ubuntu22/uwb-midterm-s2-bias-prototype；branch research/midterm-s2-bias-prototype。未压缩全审计记录及临时缓存位于Git外/home/ubuntu22/uwb-midterm-s2-bias-prototype-artifacts（约23MB）；交付UNITS.jsonl.gz为无损压缩，不依赖外目录即可读回全部估计/秩/协方差/失败。重跑必须新输出目录，不覆盖本轮。

入口README、REPORT、CONFIG、SOURCE_LOCK、SEED_REGISTRY、PROVENANCE、CHECKS/INDEPENDENT_CHECKS。不迁移8D后端、不合并PR97、不操作硬件、不新增实测数据、不修改论文结论。完成后推送草稿PR，不自动合并。
