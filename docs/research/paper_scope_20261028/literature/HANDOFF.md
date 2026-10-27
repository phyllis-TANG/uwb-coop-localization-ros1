# 交接：文献差异核查与会议选题

## 目标与实际完成

仅为导师讨论核查近邻/会议和A/B范围，不开发定位器、不运行定位矩阵。九篇一手论文对照完成：P1/P2/P3/P5/P8阅读全文正文，P6选读作者预印本，P4/P7/P9仅摘要/公开预览。两个基线规划、一页摘要、五分钟口头说明均已写入。所有建议均为待验证，不是已实现成果。

## 实际环境和版本

实际路径`/workspace/scratch/baf181dcbfd0/literature-scope-20261028-baf181`，分支`research/20261028-literature-scope`，remote `https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git`。旧scratch仓库已不在，单独初始化/获取指定基准，没有恢复或改动旧计算工作端。起点完整HEAD：`74fa210e7cf6aa322eaebce19530510edb605d22`。初始HEAD处无tracked修改，有两项范围外未跟踪临时文件，原样保留；初始进程观察只有系统/应用/同步服务，未见定位进程，可用空间约30GiB。无适用AGENTS；Python3.12.14及pdftotext可执行，未安装共享依赖。

PR64固定head `d9eea02092511c6571fe1b06e5164ccb5007e1e7`、PR65固定head `b2efc577e667c339a45741760e8c7623625f03bc`均以git show只读。接口当时均显示已合并，远端main观察为`7b67c66f2470d23f6c876f45b6543f72fab66391`；仍保留用户指定起点，不等待、不自行合并或切换其他工作端。阶段提交e371a71、8b37ca8。最终完整提交/草稿PR由provenance publication字段及同名远端HEAD登记；本交接文件不能自引用自身最终commit SHA。

## 修改文件

只新增`docs/research/paper_scope_20261028/literature/`下的README、PAPERS、BASELINES、CONFERENCE_SCOPE、SUPERVISOR_BRIEF、TALK_5MIN、READING_LOG、HANDOFF、COMPARISON.csv、REFERENCES.bib、catalog.json和provenance.json。无算法、公共manifest/geometry、源数据或既有结果修改。

## 已执行命令与核验

环境：pwd、git status/branch/log/remote、ps与df；独立git init/fetch指定三个SHA；git show读取五份报告。阅读：公开HTTPS获取出版社/机构/arXiv材料，Crossref核实元数据，pdftotext -layout抽取，pdftoppm/view_image核对关键算法和公式；GitHub只读目录和指定代码文件。全部输入报告SHA、外部URL/字节SHA和代码固定版本在provenance。

文档检查已实际运行：9条ID/全部对照字段、9个BibTeX条目及括号、DOI与目录一致、Markdown本地链接、git diff --check及写入范围。**这只是文档核验，不是定位测试或论文复现通过。** 没有运行定位矩阵，也没有以阅读代实验。完整阅读范围与访问失败见READING_LOG/provenance。

## 重要结论与未完成

P5足以否定“坏参照＋多子集＋unknown本身新颖”的宽泛主张；P1已有prior故障。P4公开摘要已声称配置一致工作先验/可信检查点，全文仍未获，不能替其下正文结论。P5论文与当前代码在参数/噪声点/选簇/回退/投票有差异；两代码库未核实复用许可。P8仍为预印本，不能因期刊模板称正式期刊发表。

A有条件保留，B作为较小备选，都尚未证明贡献。PR65实包收益混合，PR64连续和停点位置参考均not_accepted，不能报告实包精度提升。IV2027官方页已确认2026-11-15 23:59 AWST，与香港同时间；月球只是任务类比。

尚未做：合法全文补读P4/P7/P9、原方法实现/完整复现、代码许可澄清、新贡献理论或实验、独立参考验收、定位器开发和矩阵。不要把这些建议写成已完成成果。

## 下一步与导师决定

1. 用SUPERVISOR_BRIEF和TALK_5MIN讨论A/B主线及贡献门槛。
2. 决定是否投入P4等合法全文、两种完整基线的复现/授权核查；先读规范与假设，禁止按验证结果调参补出“原法”。
3. 决定独立参考/故障标签补证的优先级；未验收参考前保持现场精度结论受限。
4. 选择投稿日程；证据不足时调整投稿窗口，不以日期替代贡献。

本任务不会继续开发算法或运行试验；需要新任务明确新范围。四小时预算没有重置，达成文献交付后结束。不要改原数据/Release、刷固件、开ROS/串口或车辆，不停止别的进程；不自动合并PR，不上传未授权PDF，不绕过付费墙。
