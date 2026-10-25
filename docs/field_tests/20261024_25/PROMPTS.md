# 可复制给三个工作窗口的任务指令

本页用于本交接PR**合并后**分派任务。先由协调端公布本轮完整`HANDOFF_COMMIT`，再将相应提示词复制给对应端。提示词中的尖括号必须替换成真实值，不能将历史基线当新工具版本。

三个窗口不会自动共享工作树或上下文：每端都须读仓库文件、固定相同提交及配置摘要，使用独立分支/输出目录。合并权限由协调端/用户统一处理，不让各端自行合并。

夜间有限批处理另见[NIGHTLY_SANDBOX.md](NIGHTLY_SANDBOX.md)，首次运行与中断恢复的命令不同。

## A端：沙盒bag与离线准备

```text
请使用中文处理仓库 https://github.com/phyllis-TANG/uwb-coop-localization-ros1 。
本轮共同提交 HANDOFF_COMMIT=<合并后完整40位提交号>。

先只读报告pwd、git status --short --branch、当前分支、git log -5 --oneline和remote；
有未提交/未跟踪或分叉内容时不reset/clean/自动stash，不覆盖别端工作，可创建新检出。
确认包含本轮提交后创建你自己的analysis/field-bag-*分支。

按顺序阅读 docs/field_tests/20261024_25/README.md、manifest.json、geometry.json、
EXPERIMENTS.md、QC_REPORT.md、RUNBOOK_SANDBOX.md和RESULT_CONTRACT.md。
SESSION_LOG_ARCHIVE.md只作历史证据，较晚修正覆盖较早记录；不要执行其中车端启动指令。

当前先完成RUNBOOK_SANDBOX的A1验收复现，再实现A2标准化观测/时钟诊断与测试。
下载/数据均放Git树外，用prepare.py核对SHA并安全解压，原始文件只读；输出新运行目录。
八个正式bag已过文件检查，共311144条消息，成功T10选184755 retry。
参考视频文件完整，但Car2标记提取、板形状、逐片空间关系/时间同步尚未通过，
不要提前把视频当连续真值，不用Odom或脚本目标当真值。

开发包T08/T10/T12/T14；T09/T11/T13/T15整包留出。可做健康检查，不能按留出定位误差调参。
先准备Odom-only、独立UWB/Odom、固定peer联合解接口与合成测试；正式评价等待协调端批准参考和冻结规则。
不要加真实终点因子、逐包终点拟合或用测试结果反调外参。

只改本端bag/标准化/估计代码、对应测试和紧凑结果，不改公共manifest/geometry、他端视觉代码、旧结果。
ROS/真实小车/串口/固件/UWB配置不在任务范围；不要升级厂商Melodic环境。
保留代码/配置/输入哈希、命令、环境和全部失败/阻塞项，按RESULT_CONTRACT交付。
提交本端PR供协调端审阅，不自行合并。

若已授权夜间有限批处理，再读NIGHTLY_SANDBOX.md，先--plan-only核对已实现任务，
首次用run_nightly.py --data-root <DATA_ROOT> --output <OUTPUT_ROOT/nightly> --max-hours 6，不能加--resume。
只有同一路径已有run.json、源码/配置指纹一致的中断恢复才加--resume，保持原始截止时间。
预算/检查点和授权范围遵循该页，不承诺关闭窗口后平台一定后台运行。
```

## B端：本地原视频与参考

```text
请使用中文处理仓库 https://github.com/phyllis-TANG/uwb-coop-localization-ros1 。
本轮共同提交 HANDOFF_COMMIT=<合并后完整40位提交号>。

先只读报告pwd、git状态/分支、最新提交和remote、操作系统、Python、ffprobe/ffmpeg版本。
有未提交/未跟踪或分叉内容时不reset/clean/自动stash；用新检出或独立工作目录。
固定同一提交后创建analysis/field-video-*分支。

阅读 docs/field_tests/20261024_25/README.md、manifest.json、geometry.json、EXPERIMENTS.md、
QC_REPORT.md、RUNBOOK_LOCAL_VIDEO.md及RESULT_CONTRACT.md。
按本机Linux/WSL或Windows PowerShell示例准备独立现代Python环境，数据和输出放Git树外。

先用prepare.py和audit_videos.py复现已收到camera_reference、T08_video、T09_video、T10_video的SHA/CRC/全片解码。
T11_video/T12_video/T13_video现已在Release，随后按任务书完成它们的下载/CRC/解码验收，未核验前不标通过；
T14/T15视频仍待上传。棋盘IMG_7336/7337若本机无原片，先报告缺项给协调端。
之后完成B2–B5：视频身份与真实PTS、标记提取/诊断、各片相机关系与板到天线转换、
独立Q点验证、与bag时间映射和运动覆盖，最后交带质量/不确定性的天线参考。
后续视觉/轨迹工具需要实际实现并测试，不假设仓库已经有未列出的跟踪程序。

重点：Car1视觉ID0对应UWB node_1；Car2视觉ID1对应node_0；实际黑框144mm。
Car2板面弯曲/默认识别失败需先处理既有4K素材，不能直接把平面PnP结果当真值，也不立即强制全套重录。
每片内部固定但片间角度会变，不能共用未验证的单个房间外参；地面单应不能直接用于高处标记。
相机K/D尚未定版，IMG_7337显示旋转需正确处理。保留所有时钟域，不用frame/30、NTP或文件名假定精确同步。
Q点若用来拟合，不能又声称在同点独立验证。不能根据UWB/Odom估计结果反调参考轨迹。

只改本端视觉工具/测试和紧凑报告；公共manifest/geometry修正提交证据给协调端，勿直接与别端竞争修改。
按RESULT_CONTRACT回报原片/配置/源码哈希、真实命令、可见率、独立误差、失败/未知项和适用范围。
若只够支持停点就交checkpoints，不强行交连续真值。提交PR审阅，不自行合并，不启动现场设备。
```

## C端：协调与评价冻结

```text
你是本轮离线分析协调端，仓库为 https://github.com/phyllis-TANG/uwb-coop-localization-ros1 。
先检查实际Git状态、分支、remote和最新提交；不要假设本地main已更新，不覆盖脏工作树。
阅读 docs/field_tests/20261024_25/README.md、manifest.json、geometry.json、EXPERIMENTS.md、
QC_REPORT.md、RUNBOOK_COORDINATOR.md、RESULT_CONTRACT.md及各端新提交结果。

确认交接PR合并后，发布实际完整HANDOFF_COMMIT及manifest/geometry SHA给A/B端，
各端独立分支/输出目录，公共清单与几何由你单一维护，各端不自动共享上下文。

当前八个动态bag和已收到参考/T08–T10视频均通过文件检查；视觉精度、Car2标记/板形状和时空同步仍待验收。
维护待补：Car2运动日志、T14/T15实际遮挡材料/位置/时段、P/Q实际点与原片对应、T12实际起始几何、其余视频。
沿用已纠正人工读数，T12起距2.00m、T13起距2.12m、T11终距1.52m、T10起距1.75m为沿用值。
未知量标未知，不事后反造精确事件或测量。缺项只限制其相关结论，不阻塞所有诊断。

验收A端来源/标准化/时间报告，验收B端独立空间/时间参考；通过后冻结开发/留出与基线/评价规则。
T09/T11/T13/T15整包留出，不能随机拆帧或按留出误差调参；Odom与脚本目标不能当真值。
先比较Odom-only、独立UWB/Odom、固定peer联合解，候选机制、消融和文章题目待数据反馈再定。
不按强弱挑选实验，不把室内结果当月面性能，不强求所有方法必须改进。

审阅各端PR时核对真实输入/配置/代码/参考哈希、命令、环境、失败和质量范围，再按用户批准合并。
大bag/视频放Release或外部存储，Git只存清单、代码和紧凑证据；不将平台权限或真实硬件操作纳入离线授权。
需要夜间任务时按NIGHTLY_SANDBOX.md明确有限范围、预算、检查点和停止条件，避免无人值守无限扩大任务。
```

## 合并后的最小交接消息

协调端向三个窗口发布以下事实即可开始，不需要再次转述整段聊天：

```text
本轮HANDOFF_COMMIT：<完整SHA>
数据与任务入口：docs/field_tests/20261024_25/README.md
manifest SHA256：<实算值>
geometry SHA256：<实算值>
你的角色：A沙盒 / B本地视频 / C协调
允许修改范围：<对应任务书>
当前第一阶段：<A1或B1等>
已批准参考版本：尚未批准 / <实际版本与SHA>
回报：真实运行命令、代码/配置/输入哈希、检查结果、失败/阻塞、PR链接。
```

任何端发现提交/配置哈希不一致，先停止依赖该差异的计算并回报；不要自行把main拉到最新后继续与旧结果混合。
