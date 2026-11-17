# C端技术初稿交接

## 范围与来源

- 工作目录 `/home/ubuntu22/uwb-midterm-technical-draft-c`，开发分支 `docs/midterm-technical-draft-c`。
- 固定开发起点 `c51411433d30dc379bd69cf5fb20a11e196b7182`（PR109已审查提交）。
- PR108独立只读checkout `/home/ubuntu22/uwb-midterm-technical-c-pr108-readonly`，固定 `41ba0d3a6e69897ef6330cc9ad218253c7fb80ea`，没有修改或提交。
- 原工作区保留原分支和HEAD，状态未改。父目录与固定树均无适用AGENTS.md。
- 仅新增 `docs/research/midterm_technical_draft_c/`。会议论文、原分析、实验脚本、已有结果和Git历史均未更改。
- 本次定位/优化运行0，新增真值线性诊断0，新增随机样本0；复制20份保存表图、核对数值与编译不计定位运行。
- 55条结论和固定来源/行/筛选键见CLAIM_EVIDENCE；方法引注M01–M11与结果来源R系列在notes中展开。

## 正文交付与阅读

完整正文包括研究问题与模型、实测动机、状态增广与不确定性、仿真结果、技术边界和后续路线。正文与证据附件分开。`TECHNICAL_DRAFT_ZH.md`由三份sections源码合并，PDF由同一Markdown生成完整LaTeX后编译。未改动会议论文模板；固定树没有可沿用的中文技术报告LaTeX模板，故新增简洁模板。

原图逐字节复制，没有重绘、裁剪、不利条件删除或重新求解。PR108完整补充表保存在evidence/pr108，避免依赖本机只读checkout。图表完整条件与样本数、索引、哈希在FIGURE_TABLE_INDEX和SOURCE_COPIES中。

## 逐项审查

- [x] D_i/C_i/T_i沿用原始平方误差定义及符号；MSE和平均RMSE区分，单位明确。
- [x] 测距偏差b、简化位置偏差beta、静态C_i和传播矩阵分别定义；Schur公式附可逆条件。
- [x] 运动因子为全局位移，不将本批写成IMU融合；实际动态后端单独说明。
- [x] B2仅单候选常偏差；B3及正确中心/真实噪声/真值线性参照标记理想信息边界。
- [x] 43200既有结果复用、14400非线性及14400配对线性诊断分开；独立n与点数、方法数、阶段数分开。
- [x] 各批未驻点/预算耗尽有限结果保留；6400奇异传播二维块不可用，没有伪逆包装。
- [x] 点覆盖与轨迹全覆盖分开；不宣称罕见风险、PL/HCPL/HMI或月面验证。
- [x] PR106–109固定Git来源关系、55条来源路径和20份原样复制通过只读检查。
- [x] 代表数值从原表复核，独立审阅记录见notes/INDEPENDENT_REVIEW.md。
- [x] A-NL/B-PRIOR插入位明确标记计划；没有等待或引用A/B新窗口工作树。

编译和最终目录检查的实际结果另见 `notes/BUILD_AND_REVIEW.md` 与 `notes/DELIVERY_CHECKS.json`。如重编辑sections，需重新assemble与编译，不直接修改合并正文后遗忘同步。

## 尚缺材料

师兄原始方案及风险分配/HCPL公式未找到可核对版本；E1–E4原编号映射未证实（已有历史S1/S2与当前P-S1/P-S2明确区分）。真实survey与噪声标定、动态高精度真值、未知故障与长期/月面验证尚缺。详细搜索范围、缺口及接入规则见OPEN_QUESTIONS和notes/methods_sources。缺失原文不阻塞已完成技术正文。

## PR提交方式

普通PR提交到main；不自动合并，不改写已有提交。最终交付完整HEAD和PR链接以Git/PR回执为准，避免在提交内容中自引用其尚未生成的SHA。该分支从指定固定PR109提交创建，即使main随后新增A/B内容也不改变本稿来源。
