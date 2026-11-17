# A端交接

完成：旧48终点弱方向诊断、缓存读回一致性、新seed审计、预提交冻结协议、开发冒烟、全部2400配置、无优化读回、seed配对统计、图表和报告。未合并任何PR，不等待B端，不修改报告正文、A/B/C或月面任务目录。

固定来源cc3861bf054f96f88c381eb07f6f89b81ebf2618；PR112已合并到main，merge为5e6e365b3c4e150a5146e18d3078daa19b823f14。新checkout仍从固定来源建立。普通PR以main为base，仅含本任务两个新增目录，无需携带未合并PR112祖先改动。

冻结SHA：c88571f51d7165f568847c9338005ddf4880addb；正式执行SHA：e97f94e7824f6bc5450319b59d14d501b8482418。全部正式2400配置/4800调用，2232接受、168未驻点；开发60配置/120调用，56接受、4未驻点。没有额外继续迭代、换seed或追加配置。formal_RUN已结束，无待恢复单元。

证据位置：docs/research/midterm_noise_scale_a/results。完整阶段r/J及attempt日志、独立venv保存在/home/ubuntu22/uwb-midterm-noise-scale-a-artifacts，精简交付不依赖该绝对路径。原始大体积结果约数十MB，交付中的输入/状态足以无优化复核。

验收使用README命令：legacy_diagnostic、readback、summarize、contrasts、final_checks、figures均不调用优化器。NPZ成员一次解压到字典；没有在循环里重新读压缩数组。旧交付46个文件哈希、执行时全部冻结依赖哈希已重新核验。所有正式阶段独立r/J/代价/梯度一致，噪声跨尺度精确配对、白化receipt、初始化依赖和全部分母通过。

分析入口修正记录：第一次readback缺少distance函数别名，输出空目录，随后只读回重算；首次汇总沿用旧30seed的180点/150配置常数，在分母验收时修正为240/200。旧中间表和图在Git外保留。新交付包含额外3072行分母检查与192主计数检查；所有输入、估计、覆盖计数和预定主要配对结果不受影响，未重跑任何优化器。执行源码哈希检查仍全部一致，修正局限于分析入口。

结论边界：weak组率没有稳定下降，覆盖未共同改善；整体范数改善不代表最弱方向改善。每条件n=40，同seed跨尺度/车/方法相关；原48点不增加n。相对先验信息、初始化微变、接受候选集合变化仍无法单独排除。见REPORT与DECISION_MEMO，不应改写成因果机制已证明或方法验证成功。

本地路径/home/ubuntu22/uwb-midterm-noise-scale-a，分支research/midterm-noise-scale-a。若推送失败：保留本地提交，确认git status后运行git push -u origin research/midterm-noise-scale-a，再创建base=main普通PR；不merge或rebase到移动main改变固定研究来源。
