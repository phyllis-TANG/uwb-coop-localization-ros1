# 中文交接：首轮强基线已完成

**结论A（机制范围）：原q不足不代表成熟监测无效；含独立历史、显式交叉相关的工程SS已能报警另一车的传播损害，本轮收缩新方法主张。** 假设AL=.10m时，共同墙偏差Car2全时段HMI由B0的5秒降为主SS的0秒，可用由61/63降为49/63；AL=.05m仍有3秒HMI。不能称所有完整性需求达标、最优阈值已选定或认证风险。全部三AL、两车、启动/恢复/late、正常误警/有害代价见REPORT和6660行敏感性表。没有新候选或扩大矩阵。

实际仓库`/workspace/work/uwb-cooperative-integrity-baselines-20261029`，分支`analysis/20261029-cooperative-integrity-baselines`。main计算基准81fb509ba2d2a1b2e1f1151d53a7e73807820bd4；远端核对到519113f38d636844285e01b56a193ca26ef2bfb4（新增PR79，仅分析文件），未静默纳入。19文件原核锁74fa210e…全部匹配；在线执行完整提交在results/RUN_INDEX。原工作树和旧成果保留，无其他实验进程被操作。

无授权数据盘挂载/NAS副本。按用户随后澄清，在已授权工作区只做轻量RAM受控复现，研究结果<100MB，不下载归档/视频/bag、不生成大缓存。Git外根`/workspace/work/uwb-cooperative-integrity-baselines-20261029-run`，TEMP/TMP/TMPDIR为其tmp；独立venv，Python3.12.14，NumPy2.2.6/SciPy1.15.3。配置/truth SHA精确一致，gzip事件SHA不同，保留新canonical/hash与旧数值等价核验，**不是原归档读回**。

完成seed101 nominal、共同墙、peer_bias三案例，共189次联合发布、183 accepted、6启动；3次同机同输入原生G1控制精确等价，1次receive<=46秒前缀44发布精确一致。B0 never-peer；B1四锚本地及网络OR；B2三源自启动排除、完整QR历史、共享噪声交叉项；不反馈G1。15项最终测试、8组语义损坏负例、504全部Schur H/g/常数、96窗口独立FD/K、全部1098 SS/1134四锚分数与13986声明通过。原核、公共几何/manifest、原始资料、双车旧工具未修改。

在线原执行与最终工具分开：之后只修读表/独立核验/打包，并补未发生于本三案例的缺Odom审计保护、跨关键帧primitive不支持时B2明确unknown。原源码与完整日志保留，不重报成最终源码执行，也不重跑矩阵。预检gzip不一致、CLI同名导入、CSV键排序字节比对失败和旧读表版本均保存；最终逐值/重复计数一致。预先报警onset/延迟已修正，只重读结果。

只读续接见COMMANDS：输入/输出目录已完成，不再调用run.py重复估计；需要审查则independent.py或readback.py输出到全新目录。RUN_INDEX、SOURCE_AUDIT、SHA256SUMS绑定输入/配置/源码/结果；ARTIFACTS给完整证据本地路径、SHA及实际可取得性。完整本地包不冒称NAS/公共HTTP可取得；紧凑审查包随独立草稿PR交付，未自动合并。

真正剩余：Hafez本次指定全文入口502、CIM仅官方摘要；尚无应用批准AL、名义相关噪声标定、故障先验/未监测风险及独立验证，所以不交PL或稀有HMI概率保证。小AL/晚段代价本轮已算，不能通过再扫故障阈值“解决”。实测先引用PR77 G3：已有10静态包适合输入与测距变化诊断，不能唯一归责或验收连续定位精度。本轮没有实测精度结论，不扩T08/T10，留出T09/T11/T13/T15不消费，不启动ROS/串口/车辆。
