# 任务A交接（2026-10-28，供10月29日讨论）

## 已完成与结论

任务A完成：原归档SHA/239成员、16逻辑单元身份/公开表、五方法同期发布/历史/三类局部信号只读分析，八项检查通过。**没有重新运行任何估计器**。优先阅读[A_FACTS](A_FACTS.md)，其至多两项实际缺口与[ANALYSIS](ANALYSIS.md)对应；代码不提供新的定位控制策略。

本例裁剪已显式分离发布位置和内部主图，图内约束没有这种分离；但连续发布无全面改善，yaw会付出更大代价。局部墙冲突可见，信息代理/小修正/覆盖不足以认证健康，恢复尾部仍有历史来源和配对差异。没有证明图内约束的实际用途必要性，停止扩张，不追加种子/实包/矩阵/阈值，不安排实车。

## 身份和保存位置

- 实际基线main `0ef38e8b84dc88cb7b0e26fea595ac05c5162676`，包含PR71；其更新已合并PR72，已记录，与下发快照不同。本轮只新增自己两个目录，没有将旧PR72文件重复加入。
- 研究固定PR72 HEAD `1cc7713a7e48776474788a07a1b41040f9df9330`，原执行SHA `312180ef51c6ea4ba394bc85618674ec36ff786d`。
- 分支`analysis/20261029-cooperative-a-evidence`；worktree `/home/ubuntu22/uwb-cooperative-a-evidence-20261029`。工具保存点`57fce43f1ebc6cc7bb1a34cb5d40567be92506d0`，最终文件身份由DELIVERY_SHA256.json绑定，最终完整Git HEAD随交付回复/远端分支提供。
- 原仓库HEAD `115b17deb2f848e596d1638a0b45cf360deae947`，原工作区保持不变；既有ROS/rosbag未操作。现场记录在checks/FINAL_SITE.txt，收尾main仍为上述值。
- Git外根`/home/ubuntu22/uwb-cooperative-a-evidence-20261029-artifacts`：evidence-v1保留原归档副本/全量解包；analysis-v1失败保留，analysis-v2正式读回；summary-v1保留早期ns表示，summary-v2正式整数ns导出；semantics-v1、tests-v1/v2和package-v1。
- 原归档SHA `50c671e3687c3342b8abe99986ecd6a6488de23e24fe112b16b44d9f8fb3f320`，未改。自有读回包3,835,744字节，SHA `2d1e4e20333341f280c0cc6c3c78f2bc167fd954504b1025a34798164644bffe`，已复制并核验到新NAS专属目录；58成员含manifest。具体路径/内容见[ARTIFACTS](ARTIFACTS.json)。不需要再次下载原bag/视频。

## 复查入口与失败记录

[COMMANDS](COMMANDS.md)为真实核心调用；[METHODS](METHODS.md)说明三类信号依赖、单位/分母、共享标量读器范围及局限。[EVIDENCE_LEVELS](EVIDENCE_LEVELS.json)逐结论绑定输入/产物/读器SHA，区分本轮重算、仅核表、引用原记录、新建议。[RUN_INDEX](RUN_INDEX.json)区分原研究逻辑单元与本次只读阶段；没有未执行的估计器任务伪装完成。

最早extract CLI漏参数只usage退出；正式v1出现离线truth同名列表覆盖字典错误，未得完整表。修复另存v2，保留原日志和源码版本。summary-v1为整数秒ns写作float表示；v2统一保留整数ns，并验证任意1ns不丢失。失败/修订是提取器的开发记录，不是原定位运行失败，未改PR72结果。

## 剩余事项与边界

没有待补算单元或本任务后台运行。仅保留未知：无独立硬件/控制用途限值或实际下游消费记录，未对prior单独做因果干预，原系统无发布协方差、工程噪声未标定，仅单个开发seed，不能推断完整性概率或普遍否定约束方法。以上不会靠增加本轮试验来填补。

交付本分支草稿PR供审阅，不自动合并，不修改PR67/70/72；无需夜间提供凭据或开展额外操作。

草稿PR已创建：[PR75](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/75)，open、draft、未合并。交付及推送于2026-10-28 15:17 UTC完成，约47分钟内结束，无后台续跑。
