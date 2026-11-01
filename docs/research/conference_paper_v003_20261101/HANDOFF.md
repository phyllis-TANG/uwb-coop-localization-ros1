# 论文 v003 与 PR92 证据交接

2026-11-01。此目录保存本轮**现行**论文工作材料；不是投稿终稿，也不修改既有实验或验证身份。按以下顺序阅读：

1. `PAPER_OUTLINE.md`：从领域背景到问题、章节、图表和证据用途的框架。
2. `MODEL_AND_CALCULATIONS.md`：单次理论、实测配对 $D/C/T$、人工参考敏感性及已读回数值。
3. `EVIDENCE_AND_NOVELTY.md`：PR92 正反结果、现场及 PR91/A2/B2 的用途、可主张贡献和最近邻边界。

本目录复制自本地 `I:\UWB\project\outputs\conference_paper_draft_20261101\v003` 的两份现行稿，并为远端接手新增证据卡。旧 v001 全文与 v002 引言均是修订历史；v002 曾被用户指出缺少领域背景且表述生硬，勿沿用其散文段落作为正文。文内出现的 `outputs/...` 是本地研究总账路径，**不是**本 PR 内可直接打开的文件。可访问的先前公开交接在 [PR89](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/89)、[PR90](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/90)、[PR91](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/91)、[PR92](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/92)；最终 A2/B2 停点输出仍只以本地冻结结果为准。

核心判断：材料足够写完整、可复核的分析型会议论文；目前已有实证／问题刻画层面的创新，不因缺少新算法而归零。PR92 在指定合成模型内证明摆位交互可发生，但 Car1 的交互方向与现场相反。论文必须同时报告这一支持与反证；不能宣称在线安全选择、真实移动全程精度、自然 NLOS 规律或安全概率已经验证。接下来的工作是代码方程核对、图表和近邻文献逐篇对照，然后写正文；没有由本轮结果推出的新实车采集需求。

数据身份：静态五包交互是已暴露数据的事后二次分析；PR91/92 是各自冻结的受控仿真；A2/B2 仅验证原 M2/M3/M3W025 的运动后停点配置，不能回头认证新交互假设。实测人工参考的每轴 ±2 cm 是操作者估计下的敏感性设定，不是认证精度。PR92 的公开归档与指标读回为 PASS；本地接手窗口仅独立重算发布 CSV 的 $T$ 与 t 区间，未重跑估计器。

本交接只包含四个小型文本文件。无原始 bag、视频、密码、完整轨迹、未公开实验日志或新增估计代码。后续窗口若引用本目录，请继续沿用本地研究总账 `I:\UWB\project\outputs\research_data_register_20261029\v001\研究数据总账.json` 记录来源及用途；该总账未作为本 PR 文件上传。

