# 本批恢复交接

本目录是PR130短窗之后的批次完成入口，历史结果仍在field_moon1_integration。数据合同和完整全段比较在此，不必重新做原bag解码或反复找数据。

真实运行目录：/home/ubuntu22/uwb-field-moon1-integration-artifacts/completion/batch 与 completion/recovery，均只读。38调用原批和16调用恢复分开计数；没有真实开发冒烟调用，formal_runs=0。已有attempt不自动重跑。

冻结提交分别记在两个RUN.json；源文件/输入/保存端点SHA对应FREEZE与RECOVERY_FREEZE。便携JSON归档保留完整输入、阶段端点、尝试记录和完成回执。具体完成计数以REPORT和READBACK为准。

下轮讨论应基于全数据合同及已完成比较，不把仍缺的安装原点、采样时钟标定、连续真值解释成待运行代码。未接受端点完整保留，不能作为已接受最优解使用。不要仅为过门槛继续增加预算，不要把拟合bias当已发现真实故障，不把静态校正训练包当独立验证。

没有自动合并PR，没有启动Isaac，没有改动A/B/C或Moon_1历史数据。
