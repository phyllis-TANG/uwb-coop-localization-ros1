# C端交接

本轮完成四篇核心公开全文、两篇补充对照的公式和迁移审计。先实现**可核验平方差凸预收缩**；第二候选是**平稳GMP联合协方差外包**的独立低维核查。两项都只是未来方案，未运行新定位器、Monte Carlo、完整IMM/CORA或修改正式实验。

## 1. 固定身份及保护范围

新工作树 /home/ubuntu22/uwb-open-literature-followup-c，分支 research/open-literature-followup-c，创建基准main为0c3dbbb59a5c65087e073ad1c49eaed397f2958b。原工作树分支experiment/two-car-independent-integrity-bridge-20261023、HEAD 115b17deb2f848e596d1638a0b45cf360deae947，检查时clean；未修改原树。origin为 https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git 。祖先路径和仓内未发现适用AGENTS.md。

PR122仍OPEN，head 9832da3b7cb44e43c89bd10dad550d96419b72c0；只读detached checkout，不合并。交付复核main已到30f9379249a4e695acf75910c40862a770e6f4ce，外部合并PR123/124；其head仍分别为f354cf5e370d4ffc54077b7280ca97638a8bd585、aab57504262fff739d0754145c61a61efa79791a，与本轮证据一致。本分支未merge/rebase。

仅新增本目录。环境原始/复核记录见 [ENVIRONMENT.json](notes/ENVIRONMENT.json)、[DELIVERY_ENVIRONMENT.json](notes/DELIVERY_ENVIRONMENT.json)。最终交付commit及普通PR链接随提交后报告返回；不自动合并。

## 2. 交付索引

- [README.md](README.md)：入口、结论和范围。
- [CURRENT_EVIDENCE.md](CURRENT_EVIDENCE.md)：A/B/moon1固定SHA、实际状态/噪声/先验及缺口。
- [LITERATURE_MATRIX.md](LITERATURE_MATRIX.md)：证据质量、迁移适用性分别评价，最近工作差异。
- [ASSUMPTION_AND_GUARANTEE_AUDIT.md](ASSUMPTION_AND_GUARANTEE_AUDIT.md)：四个问题的数学审计和保证边界。
- [METHOD_TRANSFER_DECISION.md](METHOD_TRANSFER_DECISION.md)、[NEXT_EXPERIMENT_SPEC.md](NEXT_EXPERIMENT_SPEC.md)：最多两候选、延期项、否证条件及预算。
- [SEARCH_LOG.md](SEARCH_LOG.md)、[REFERENCES.bib](REFERENCES.bib)：实际版本/书目/访问限制，作者代码SHA及许可。
- notes中的四组全文笔记、访问JSON、[INDEPENDENT_REVIEW.md](notes/INDEPENDENT_REVIEW.md)：公式页码、代码位置、原文疑点和独立审阅。
- [CHECK_PROTOCOL.md](CHECK_PROTOCOL.md)、[analytic_checks.py](checks/analytic_checks.py)、[RESULTS.json](checks/RESULTS.json)：三个预先登记的精确代数核验。
- [DELIVERY_CHECKS.json](checks/DELIVERY_CHECKS.json)：文档、引用、链接、源码身份与修改范围验证记录。

没有提交版权PDF、截图、作者代码或新实验结果矩阵。主要交付为可编辑中文Markdown和BibTeX；本任务不要求PDF排版，未把先前窗口的排版/Overleaf请求继续套入本轮。

## 3. 关键发现及对A/B的影响

1. PR124已具限定低维外包，Calafiore的平方差凸域和方向外盒可作保守预收缩；普通数值原始可行值不是外界，必须独立认证。不能把内接椭球/截线当外包，不能因正半径内球需膨胀就说原集空。
2. PR123的非线性直接套仿射区域已有失败证据。Safe/CORA的最优性证书不修复区域事件；换平方目标不能回答旧原始测距目标的多解。两个库的数值移位PSD与实数定理需分开。
3. 2020 GMP v1的非平稳初始方差式(32)/(33)有完整三时刻反例；不要在B端未来相关R中直接采用它。平稳谱外包仍可保留。此项只影响该公式的**未来移植**，本轮没有发现当前A/B已使用它，不据此宣布历史实验无效。
4. Zhu/Kia bias是考虑参数，非在线幅值追踪器；现有step/ramp不能自动转为平稳GMP。当前集中估计保留模型内状态耦合，真实原始时间/共模噪声仍需独立依据。

公式疑点均绑定实际作者稿版本，列出独立推导；未指认作者程序错误、未评价未读正式/后继正文。

## 4. 检查及运行口径

先提交核验协议，完整SHA为10871a2392483884db5119825f6f4695d0f6fb1e，之后才创建/运行核验脚本。E1几何单点集、E2两种目标、E3三时刻协方差，共三个独立例；精确有理数、随机抽样0、定位优化调用0。E3的负二次型经独立纸面复核；平稳控制是同一例的对照，不是额外Monte Carlo。

交付检查解析全部Markdown/BibTeX/JSON及脚本语法；核对本地引用、固定Git路径/行号、可访问网页和文件哈希，并检查仅新增允许目录。网页访问受限与失效分列，不能以抓取受限宣称来源不存在。实际检查：14份Markdown、6条BibTeX、78个本地引用和32个固定Git文件/行链接通过；29个外部入口未发现404/410，Crossref两处429、SIAM一处403、IEEE五处202脚本页已记录，不能据此称全部出版社全文可访问。机器结果见 [DELIVERY_CHECKS.json](checks/DELIVERY_CHECKS.json)。Safe的25个作者Python文件仅做AST语法检查，CORA未构建；这些都不是作者实现复现。

## 5. 未完成项及下一窗口

**第一实施项为V1。** 冻结PR124全八例输入，先证明新外盒界可靠，再同域/同预算比较总成本；若只省搜索却认证更贵，应保留负面结论。不得丢镜像支、超时队列或调小域；失败回退原算法。V2保持独立，只用平稳初始化，先有全参数谱证明，再做短矩阵实现检查。

仍缺真实域/锚点/bias边界和相关噪声参数依据，模式功率数据、共模结构、故障候选及删测可辨识性、任务风险/告警合同。作者缺失代码许可与运行性未补齐；2023 GMP全文未取得，原文疑点是否在后继版解决不确定。Kuwada2026保留摘要线索。

可以向中期正文提供已核书目、条件式包含推导、模型区别和限定反例；性能改善、平台适用性、保护级/HMI和月面验证均不可写成已完成。后续实施、数据校准和正文编辑需由对应任务另行开展。
