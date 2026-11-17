# 检索范围、版本与排除记录

检索日期：**2026-11-17（UTC）**。本轮是针对可实现区域构造及故障方法边界的定向核查，**不是系统综述或穷尽检索**。未按引用数、期刊声望或新旧年份排序。精读对象为4篇：SIVIA基础1993、Drevelle–Bonnifait2013、Rohou等2017、Hafez等2020；基础和SS文献在PR118已有核查，本轮补核其与指定问题有关的条件及代码，不把重读计作新增不同文献。

## 1. 固定项目证据

|证据|固定身份|用途|
|---|---|---|
|包含已合并PR118的main|`b492c17d719013c31a93168994afe40beed5001f`|先读文献矩阵、理论审计和方法建议；沿原有缺环定向检索|
|PR119只读来源|`e35f94fb89a71236bd04c7f25fc318b016ba592d`|先读PROTOCOL、REPORT、DECISION_MEMO；核实几何改善仍未解决全部分支和联合概率问题；没有自行合并|

两条检索线分别围绕“如何保住全部允许解”和“故障假设怎样约束协同安全结论”。检索不是为已有有利结果寻找背书；PR119轻扰动未改善覆盖、区间方法高维可能不可用、协同对某故障收益有限，均属于需要保留的边界。

## 2. 检索词及追踪方式

|检索组|使用的题名、DOI或关键词|发现后核查渠道|
|---|---|---|
|短轨迹起点|完整题名 `Localization Confidence Domains via Set Inversion on Short-Term Trajectory`；`10.1109/TRO.2013.2262776`；作者名加PDF/HAL|UTC作者官网全文、HAL封面标识、正式出版元数据|
|基础方法|`Set inversion via interval analysis for nonlinear bounded-error estimation`；`SIVIA`、`interval contractor`、`bounded-error estimation`|Jaulin作者原文、出版社条目；从2013引用回溯1993基础|
|后继可信传播|`Guaranteed computation of robot trajectories`；`tube contractor`、`guaranteed integration`；`Reliable non-linear state estimation involving time uncertainties`|Rohou作者官网、White Rose机构仓库、出版社；2017参考文献[25]直接引用2013，2018为时间不确定性后继线索|
|协同指定工作|完整题名 `Fault-Mode Aware Integrity Monitoring for Collaborative CAV Localization`；`10.33012/2026.20494`；Kuwada/Joerger/Spenko加PDF、collaborative localization、fault mode|ION正式页、VT作者发表页/Archive、IIT CARNATIONS项目列表、NSF/ROSA P机构域名检索|
|SS与作者实现|`Quantifying Robot Localization Safety`、`fixed-lag smoothing`、`solution separation`、论文结论中的代码链接|NSF公开期刊PDF、原文明示GitHub作者仓；固定提交静态核查|
|书目身份|题名/DOI精确检索及Crossref注册元数据|以出版社、机构仓库与原文首页互核；注册API失败时不把空返回当不存在|

搜索结果摘要只用于发现来源；公式号、保证与实现判断取自实际读到的全文/固定代码。未使用非作者盗版全文站，未绕过付费墙；未向作者发信，未购买论文。

## 3. 正式发表与实际阅读版本分开

|条目|发表身份|实际读取/访问限制|本轮角色|
|---|---|---|---|
|Jaulin–Walter1993|Automatica29(4):1053–1064；[出版记录](https://www.sciencedirect.com/science/article/abs/pii/0005109893901064)|[作者托管期刊PDF](https://webperso.ensta.fr/jaulin/paper_automatica93.pdf)；公式按期刊页|核心：外包基础|
|Drevelle–Bonnifait2013|IEEE TRO29(5):1244–1256；DOI核实|[UTC作者稿](https://www.hds.utc.fr/~bonnif/pdf/2013_TRO_short_term_trajectory.pdf)有HAL封面和SUBMISSION页眉；正文1–14页，不冒充出版页码|核心：短轨迹、q-relaxed及概率合同|
|Rohou等2017|Robotics and Autonomous Systems93:76–84；[机构发表记录](https://eprints.whiterose.ac.uk/id/eprint/114446/)|[作者稿](https://simon-rohou.fr/research/tubint/)9页；机构确认accepted version，公式按稿件页|核心：连续轨迹保解传播|
|Hafez等2020|IEEE RA-L5(2):3182–3189；DOI核实|[NSF期刊PDF](https://par.nsf.gov/servlets/purl/10203881)8页；补核代码链接及特定尾项|核心：SS事件与迁移条件|
|Kuwada等2026|[ION同行评审正式会议论文](https://www.ion.org/publications/abstract.cfm?articleID=20494)，pp288–301|**未取得全文**；ION需订阅/额度/购买，作者和项目列表仅确认书目|最近工作线索，不作公式核心|
|Nicola–Jaulin2020|Springer SCI835书章pp341–357；[正式页](https://link.springer.com/chapter/10.1007/978-3-030-31041-7_19)|沿用固定PR118作者17页稿核查记录；该稿仍有2018模板页眉，最终书章PDF未取得|背景：Gaussian事件反演入口|
|Rohou等2018|Automatica93:379–388；[出版社](https://www.sciencedirect.com/science/article/abs/pii/S0005109818301699)|作者全文取得，未完成本轮逐式核心精读；不能据获得PDF即声称精读|背景：时间不确定性扩展，当前时间戳模型不需要|

若干DOI经浏览工具打开失败，Crossref部分请求返回非JSON；这是渠道访问限制，不是发表状态的反证。已由成功取得的原文、出版社条目或机构仓库核对相应书目。Kuwada2026的ION会议日期为2026年1月26–29日，Crossref登记的发表日期为2026年2月24日；二者分别记录，BibTeX采用已核实年份并注明会议时间。

## 4. 附近资料与排除理由

- 同作者CARNATIONS报告附录A提供协同故障假设背景，但它是机构技术报告，**不是Kuwada2026全文**，也未确认与2025 ICRA最终稿同版。只用于限定已见报告的假设，不替代指定论文的公式和实验核查。详见[协同笔记](notes/COLLABORATIVE_REVIEW.md)。
- Kuwada2025相关会议题名与作者列表存在版本/题名对应待确认；本轮未取得最终全文，不自行合并这些书目为同一版本。
- PR118的粒子/多峰文献继续提供背景，不增列为第三条候选方法，也不把有限粒子、网格或多初值作为全解包含证据。
- 没有为满足“3–5篇”而将只有摘要的论文计入核心。四篇分别对应外包基础、短窗构造、传播改进和故障接口。

## 5. 代码与许可是另一条证据链

[轨迹访问清单](notes/TRAJECTORY_ACCESS.json)记录Codac源码固定提交 `19c0b2d87b552286bd375dcec3f42124a7a8c8f6` 及LGPL许可文件。作者历史链接演变为当前库，不等于已经找到2017实验二进制或能直接复现。示例中的硬编码对照盒、人工有限域及计时边界都单列限制，不据此否定论文理论。

[协同访问清单](notes/COLLABORATIVE_ACCESS.json)记录作者完好性代码固定提交 `9737f3497c00eff81a32df0d6dbbf3720cfc485e`。原文p3189给出仓库，补充PR118上轮“未核实实现”的访问边界；根目录和GitHub许可接口未确认许可证，递归树被截断，不能推断所有嵌套许可均不存在，也不能默认可复制。代码没有运行。该提交一处尾项使用正确补集，是反对“印刷疑式必然导致作者实现同错”的明确证据。

本轮不提交版权PDF、文章截图或作者代码。保留链接、版本、哈希和关键页码/行号，使读者能够合法回查。

## 6. 评价规则与停止条件

**证据质量**评价来源身份、全文可得性、公式是否能核对、假设是否明示、结果是否支持声明、实现和版本能否追溯；**迁移适用性**评价它是否覆盖我们的固定先验、相关噪声、共享常偏差、低信息方向、多解、域和输出合同。两者分开记录。

可靠的负面结果不能降格为“证据薄弱”：例如循环网络收缩效果差、增加故障容忍导致区域扩大、某类协同故障监控改善有限，可能恰好揭示适用边界。反之，只有摘要的正面或负面结论都只能保留为线索，不添写数值、公式或证明。先验/噪声/域前提与本项目不同也不等于原论文错误。

本轮在上述核心问题、全文版本及公开实现边界得到可定位记录后停止扩充文献数量。没有宣称已覆盖所有近期工作、完成系统创新性判断或复现任何论文性能。后续取得指定2026全文时，应补齐缺项并重新审查差异表。
