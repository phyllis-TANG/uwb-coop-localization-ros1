# C端：公开全文精读与方法迁移评估

日期：2026-11-17。结论是**先实现可核验的平方测距差凸预收缩，接到PR124已有SIVIA之前**；第二候选仅做**平稳Gauss–Markov联合协方差外包的低维核查**。两项均未在本轮实现或启动定位验证；不组合成一套新定位器，不承诺覆盖改善或研究创新性。

本轮新增价值是四篇指定公开全文的逐式迁移审计，以及CORA、Limited Connectivity两篇补充对照。PR122已完成的集合反演与solution separation综述不重写；当前B端已有低维外包原型，本轮回应其收缩成本，而非重新建议“从零做SIVIA”。Kuwada2026仍为摘要线索。

最需保留的不利发现：

- Calafiore的内接椭球不是保护区域；为容纳预设正半径内球而需要膨胀量测界，并不证明原可行集为空。外盒需要可靠方向界，普通数值可行点不够。
- Safe and Smooth认证平方测距目标，通常不等于本项目原始测距目标。CORA更接近原始range残差，但偏差增广、先验和松弛后投影仍须重推。二者都不直接认证真值覆盖或HMI风险。
- Zhu/Kia的NLoS偏差是SKF考虑参数，其均值和二阶矩不被测量在线更新；不能当作现成step/ramp跟踪器。当前集中式联合估计并未因使用独立原始噪声而丢掉全部状态相关性。
- **2020 GMP作者稿式(32)/(33)初始方差折减存在三时刻反例**：首两时刻块通过，完整联合矩阵却不是保守上界。独立复核支持这一限定结论；平稳谱界仍可保留，未评价2023正文或作者实现。

## 阅读入口

|文件|用途|
|---|---|
|[CURRENT_EVIDENCE.md](CURRENT_EVIDENCE.md)|固定A/B/moon1证据、状态模型和现有缺口|
|[LITERATURE_MATRIX.md](LITERATURE_MATRIX.md)|证据质量与迁移适用性分开评价；最接近工作差异|
|[ASSUMPTION_AND_GUARANTEE_AUDIT.md](ASSUMPTION_AND_GUARANTEE_AUDIT.md)|集合、最优性、偏差和相关误差的公式及保证审计|
|[METHOD_TRANSFER_DECISION.md](METHOD_TRANSFER_DECISION.md)|最多两项候选、暂缓方法、可写入中期的边界|
|[NEXT_EXPERIMENT_SPEC.md](NEXT_EXPERIMENT_SPEC.md)|两项未来最小验证的条件、对照、失败判据和硬预算|
|[SEARCH_LOG.md](SEARCH_LOG.md)、[REFERENCES.bib](REFERENCES.bib)|实际全文版本、正式身份、访问限制、代码SHA及许可|
|[CHECK_PROTOCOL.md](CHECK_PROTOCOL.md)、[保存结果](checks/RESULTS.json)|先登记后执行的三个精确代数例；不是定位或覆盖试验|
|[HANDOFF.md](HANDOFF.md)|环境、交付范围、检查与未完成项|

详细全文笔记在 [Calafiore](notes/CALAFIORE.md)、[Safe/CORA](notes/CERTIFICATION.md)、[IMM/Connectivity](notes/IMM_CONNECTIVITY.md)、[GMP](notes/GAUSS_MARKOV.md)，版本访问记录在同目录JSON。结论标签统一为“原文定义/证明”“我们推导”“既有或本轮数值观察”“待验证”，不互相替代。

## 固定基准与工作范围

- 原工作树：/home/ubuntu22/双车协同/uwb-coop-localization-ros1；分支 experiment/two-car-independent-integrity-bridge-20261023；完整HEAD 115b17deb2f848e596d1638a0b45cf360deae947；检查时clean，未改动。
- 新工作树：/home/ubuntu22/uwb-open-literature-followup-c；分支 research/open-literature-followup-c；创建时远端main完整SHA 0c3dbbb59a5c65087e073ad1c49eaed397f2958b。
- PR122检查时OPEN，最新head仍为 9832da3b7cb44e43c89bd10dad550d96419b72c0；在独立detached checkout只读。PR123/124亦仅按固定SHA读，不自行合并。
- origin： https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git 。祖先路径及仓内未发现适用AGENTS.md。原始记录见 [ENVIRONMENT.json](notes/ENVIRONMENT.json)。[交付复核](notes/DELIVERY_ENVIRONMENT.json)：远端main已到30f9379249a4e695acf75910c40862a770e6f4ce，PR123/124已由外部合并且head与所读版本一致；PR122仍OPEN。本分支没有合并或rebase。
- 只新增 docs/research/midterm_open_literature_c/；未修改历史正文、代码、配置、实验结果或门槛。没有启动定位优化、Monte Carlo、作者完整系统或Overleaf上传。

本轮恰好3个预定低维核验，使用标准库精确有理数运算，无随机抽样。协议先提交于 10871a2392483884db5119825f6f4695d0f6fb1e，再执行脚本；脚本及协议哈希保存在结果中。独立纸面审阅没有另增数值例。版权PDF和作者代码只在临时目录读取，不提交仓库。
