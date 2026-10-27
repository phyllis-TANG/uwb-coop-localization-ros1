# T10 视频参考 v2 HANDOFF

仓库基准 `868349b543a03a6a713d1675e1d4ada7d905410c`，分支 `analysis/20261027-video-reference-v2`，实际检出 `I:\UWB\project\worktrees\video-reference-v2`。

处理链已完成；位置参考批准范围仍`not_accepted`。保留有效的原件身份、PTS、观测、13个原4K小样本、条件几何/敏感性、原bag事件、测试和独立逐行回读。没有continuous或checkpoints_only真值，未运行定位估计器。旧18片QC不重跑，T09/T11/T13/T15不作定位调参，T14/T15候选族未变。

原始输入只读复用 `I:\UWB\project\outputs\video_reference_20261026`，本轮原件SHA见input_evidence.json。新输出 `I:\UWB\project\outputs\video_reference_20261027`；选定新解码帧 `I:\UWB\temp\video_reference_20261027\raw_samples_001`；每个任务进程TEMP/TMP设`I:\UWB\temp`。不得在I盘不可用时回退C盘。没有新增大型下载或解压。

Car1标题边/红支架车头采用本轮明确人工来源，旧相反推断保留；完整角度未知。Car2板倾斜/曲率与marker→body旋转未验证，天线坐标留空。候选房间XYZ不是精度参考。

接续先读README、五契约、MISSING_EVIDENCE和visual_review。真正阻塞及最小补证已列一次性表；不要重问已确认事项、重跑输入QC、按Q/融合误差选模型，或插值制造真值。如今重摆车或对钟不能补造历史实测。若取得新证据，建立新run目录/版本，不覆盖本轮结果，再独立审查空间、停车窗或时间是否足以支持指定范围。

工具、复现命令见`tools/field_video_20261027/README.md`；commands.jsonl保留实跑argv/源码SHA/退出码。tests_001及verification.json记录通过的检查。所有参考不确定度/精度指标仍为null，未放宽容差。
