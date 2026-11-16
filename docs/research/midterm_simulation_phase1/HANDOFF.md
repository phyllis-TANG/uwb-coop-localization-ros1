# 中期第一批交接
已完成P-A0现状/缺口、旧PR91一组仿真复现、实测保存结果数值复现；P-R2主五包及全部10正常包逐记录/留一分析，既有窗口与参考敏感性复核；P-S0两布局开发扫描、冻结后G2主场景50seed确认；P-S1单偏差可估计性/先验/初始化诊断。

入口REPORT、GAPS、README。主产物：S0_PER_RUN/SUMMARY、FIELD_PER_RECORD/LEAVE_ONE及ALL10补充、S1_INFORMATION/INITIALIZATION，五张图。SOURCE_LOCK/EVIDENCE_SOURCES/RUN_INDEX/SHA256SUMS绑定来源。所有结果保留逐车负面方向；共有182条件配对运行（开发32+确认150），独立确认单位是50seed。未实现保护级、未改论文结论、未新增实车采集或操作硬件。

身份问题：当前Git保存文本与原Windows登记字节有换行差异，139份源经原字节或CRLF恢复精确匹配；两历史setup说明内容仍不匹配，具体路径见FIELD_RECONSTRUCTION。数值所需轨迹/配置/参考严格匹配，完整统计复现通过；不能称141来源全通过。保留失败日志和两个临时副本，不改原数据。

可访问稿件为v003模型文档与11月3日IV相关大纲文本，完整当前投稿稿未在仓库定位。原始11月数据Windows路径不自动映射到云端；本批不需要raw bag重解码。精确硬件/坐标标记/外参仍按缺口表限定。没有将停点升级成连续真值。

P-S2：可启动限定单偏差诊断原型的预登记对照；暂不直接进入完整生产后端增广性能比较。先确定偏差先验和拒判/失败语义，保留无增广强基线、共线弱信息负例，再冻结新确认seed。若接入8维固定窗，须单独验证新雅可比/边缘化/噪声相关。本批16101/16102与17101–17150均已暴露，后续不再称盲确认。不预设新方法优于基线。

工作树/home/ubuntu22/uwb-midterm-phase1-20261116，分支research/midterm-simulation-phase1；起点main b23188de8f1d70829a34a093028f6d15ddf8dfaa。只新增本任务tools/docs；旧树与论文结果未改。草稿PR不自动合并。临时CRLF副本和matplotlib缓存在tmp并从Git排除。
