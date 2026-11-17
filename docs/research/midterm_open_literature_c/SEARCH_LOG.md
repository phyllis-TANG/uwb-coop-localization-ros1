# 公开全文、正式身份与代码访问记录

检索与访问日期：**2026-11-17（UTC）**。本轮采用用户指定的四篇核心全文与两篇补充比较；没有为增加数量沿参考文献另增精读论文。正式书目信息见 [REFERENCES.bib](REFERENCES.bib)，公式页码均指下表指定作者稿的内部页码，不能与期刊页码混用。

## 1. 范围、入口与证据规则

检索围绕四个已有缺口：非线性多解与可行集外包；最优性证书的实际目标；LOS/NLOS 偏差与模式；不确定时间相关误差及车间互协方差。入口依次为用户给定 arXiv、作者主页/机构发表目录、正式 DOI 和 Crossref 注册元数据、作者链接的 GitHub 仓库。题名、DOI、作者名与 `code` / `GitHub` 的定向查找只用于定位公开来源。第三方摘要聚合页、请求代码按钮与搜索摘要不作为公式证据。

全文阅读与元数据核对是两种状态：拿到公开作者稿，足以核该版本的公式；正式发表的 DOI、卷期可另行核实，但不能据此宣称已经比较期刊最终正文。本轮没有绕过访问控制，没有提交版权全文、页面截图或作者源码。下载稿及只读代码副本仅留临时工作目录。原文表达疑点固定到具体版本，独立代数核验与原文结论分列，不由排版或记号问题推断作者实现错误。

## 2. 六篇实际访问版本

|条目及本轮用途|实际取得与阅读的公开全文|正式身份核对及限制|精读记录|
|---|---|---|---|
|Calafiore；核心，测距可行集/凸外近似|[arXiv:2603.04867v1 PDF](https://arxiv.org/pdf/2603.04867v1)，2026-03-05，26页|[SIAM 正式页](https://epubs.siam.org/doi/10.1137/25M1750652)：SIAM Journal on Optimization 36(2):1100–1124，2026，DOI `10.1137/25M1750652`。没有取得并逐页比较出版社最终全文|[CALAFIORE.md](notes/CALAFIORE.md)；[访问清单](notes/CALAFIORE_ACCESS.json)|
|Dümbgen、Holmes、Barfoot；核心，给定目标的最优性认证|[arXiv:2209.04266v5 PDF](https://arxiv.org/pdf/2209.04266v5)，2024-09-02，10页含附录|[Crossref DOI 记录](https://api.crossref.org/works/10.1109/LRA.2022.3233232)及作者仓库：IEEE Robotics and Automation Letters 8(2):1117–1124，2023，DOI `10.1109/LRA.2022.3233232`。v5 页眉2022不替代期刊年2023；本轮公式以v5为准|[CERTIFICATION.md](notes/CERTIFICATION.md)；[访问清单](notes/CERTIFICATION_ACCESS.json)|
|Zhu、Kia；核心，模式与 Schmidt/consider 偏差处理|[arXiv:2009.03538v3 PDF](https://arxiv.org/pdf/2009.03538v3)，2020-12-30，11页；作者稿题名含“An IMM-based”|[作者正式发表页](https://solmaz.eng.uci.edu/Papers/UWB.html)、[Crossref](https://api.crossref.org/works/10.1109/JSEN.2021.3083724)：IEEE Sensors Journal 22(6):5447–5456，2022，DOI `10.1109/JSEN.2021.3083724`；2021为early access，正式题名去掉“An IMM-based”。部分IEEE访问返回脚本/机器人验证，未宣称最终全文一致|[IMM_CONNECTIVITY.md](notes/IMM_CONNECTIVITY.md)；[访问清单](notes/IMM_CONNECTIVITY_ACCESS.json)|
|García Crespillo、Joerger、Langel；核心，GMP 时间相关误差界|[arXiv:2009.09495v1 PDF](https://arxiv.org/pdf/2009.09495v1)，2020-09-20，8页；实际读的是2020作者稿|[arXiv版本页](https://arxiv.org/abs/2009.09495v1)列作者顺序为 Garcia Crespillo、Joerger、Langel。仅引用该2020版本，不把2023后继论文的作者顺序、推导或发表身份套到该稿|[GAUSS_MARKOV.md](notes/GAUSS_MARKOV.md)；[访问清单](notes/GAUSS_MARKOV_ACCESS.json)；[核验条件](CHECK_PROTOCOL.md)|
|Papalia 等；补充，CORA 原始测距目标与证书|[arXiv:2302.11614v3 PDF](https://arxiv.org/pdf/2302.11614v3)，2024-09-28，20页含附录|[MIT 作者组发表目录](https://marinerobotics.mit.edu/publications)、[Crossref](https://api.crossref.org/works/10.1109/TRO.2024.3454430)：IEEE Transactions on Robotics 40:4265–4283，2024，DOI `10.1109/TRO.2024.3454430`。作者为 Alan Papalia、Andrew Fishberg、Brendan W. O'Neill、Jonathan P. How、David M. Rosen、John J. Leonard|[CERTIFICATION.md](notes/CERTIFICATION.md)；[访问清单](notes/CERTIFICATION_ACCESS.json)|
|Zhu、Kia；补充，有限通信下未知状态互协方差|[arXiv:1904.13074v2 PDF](https://arxiv.org/pdf/1904.13074v2)，2019-07-21，9页|[作者发表目录](https://solmaz.eng.uci.edu/papers.html)、[Crossref](https://api.crossref.org/works/10.1109/TRO.2019.2930404)：IEEE Transactions on Robotics 35(6):1523–1530，2019，DOI `10.1109/TRO.2019.2930404`。未比较最终排版全文|[IMM_CONNECTIVITY.md](notes/IMM_CONNECTIVITY.md)；[访问清单](notes/IMM_CONNECTIVITY_ACCESS.json)|

上述六篇稿件的 SHA256、像素核对位置及已取得的作者代码文件清单保存在对应访问 JSON 中。Safe and Smooth 和 CORA 已核上述最新作者稿版本，而不是默认使用初次投稿版。Zhu/Kia 的公开 IMM v3 与正式刊文题名不同，这不是两篇独立成果。

## 3. 后继论文、已有线索与没有扩展的范围

- GMP 的2023后继论文正式题名为 *Tight Bounds for Uncertain Time-Correlated Errors with Gauss-Markov Structure in Kalman Filtering*，IEEE Transactions on Aerospace and Electronic Systems **59(4):4347–4362**，DOI [10.1109/TAES.2023.3242943](https://doi.org/10.1109/TAES.2023.3242943)。[DLR机构记录](https://elib.dlr.de/193615/)列作者为 Garcia Crespillo、Langel、Joerger，并明确 accepted manuscript 仅 DLR 内部可访问，Open Access 为 No。本轮只核该元数据与访问限制，**没有精读2023正文**。2020稿中发现的表达或保证边界，不能直接归到2023版本；REFERENCES.bib 的 GMP 条目保留2020作者顺序与题名。
- Kuwada、Joerger、Spenko 2026 的协同定位 fault-mode aware integrity 继续保留为 PR122 已记录的摘要级最近工作线索。本轮未重复索取付费全文，未据摘要填补公式、冗余度条件或保护级保证；未将其计入六篇全文或追加 BibTeX 条目。
- 本轮没有额外精读参考文献中的其他论文，也没有把 Calafiore 的内接椭球、全局优化器的证书或滤波 covariance consistency 统一改称保护级。负面和不匹配证据保留于矩阵及迁移判断。

## 4. 作者代码、许可与实际检查深度

|方法|取得的固定源码身份|许可与静态检查|明确未做的工作|
|---|---|---|---|
|Safe and Smooth|[作者仓](https://github.com/utiasASRL/safe_and_smooth)，`42def2d19403e08ec92d81377426d6e92d6355d7`|根 LICENSE 为 BSD-2-Clause；检查 README、依赖、子模块指针与认证/目标代码；25个 Python 文件 AST 解析通过|未初始化子模块、安装依赖、导入作者求解器、运行测试或定位；依赖许可未完整审计。语法可解析不是可运行性或论文复现证明|
|CORA|[作者仓](https://github.com/MarineRoboticsGroup/cora)，`015dc43340ca3aed07226bee1727ea929536fd01`|检查 CMake、依赖和认证代码；在已取得主仓完整 tracked 文件列表未发现 LICENSE/COPYING，复用许可未确认；子模块指针已记录|未配置/编译/运行，未初始化子模块，未完整审计依赖许可；公开可读不能解释为可整套复制|
|Calafiore|在全文、arXiv、SIAM页、作者发表页及题名/代码定向查找范围内，未定位论文绑定作者仓库|论文声明 MATLAB/CVX/MOSEK；没有可固定源码 SHA 或已核许可|没有安装/执行；不能据此说作者未公开任何代码，也不能宣称可复现|
|Zhu/Kia IMM、Limited Connectivity|在全文、作者项目/发表页及题名/作者与GitHub定向查找范围内，未定位论文绑定代码仓库|没有已核 SHA 或许可；Limited Connectivity 给出求解器名称不是给出完整复现源码|没有安装/运行；没有执行 IMM 或分布式滤波系统迁移|
|2020 GMP|本轮核查公开作者稿的公式及适用范围，未取得可固定的论文配套作者代码|源码 SHA、许可与运行兼容性未确认|没有运行作者实现；独立公式核验不能冒充其代码测试|

作者仓库 SHA 是本轮读取的固定状态，不保证等于论文实验时版本。更细的源码链接、子模块 SHA、文件哈希和静态检查限制见 [CERTIFICATION_ACCESS.json](notes/CERTIFICATION_ACCESS.json)。所有作者系统均未执行；本轮允许的少量独立核验由统一 [CHECK_PROTOCOL.md](CHECK_PROTOCOL.md) 先登记条件与判据，不与作者程序复现或定位实验混计。

## 5. 本项目固定上下文

环境原始记录见 [ENVIRONMENT.json](notes/ENVIRONMENT.json)。读取时远端 main 为 `0c3dbbb59a5c65087e073ad1c49eaed397f2958b`；本轮独立工作树 `/home/ubuntu22/uwb-open-literature-followup-c`，分支 `research/open-literature-followup-c`，仅向本轮目录新增文件。

|来源|本轮读取的完整提交|方式与用途|
|---|---|---|
|PR122，尚未合并的文献基线|`9832da3b7cb44e43c89bd10dad550d96419b72c0`|独立只读 checkout；核既有矩阵、理论审计与候选路线，避免重新包装已完成结论|
|当前A：PR123|`f354cf5e370d4ffc54077b7280ca97638a8bd585`|固定SHA只读，不等待、不合并；核非线性/求解诊断的现有缺口|
|当前B：PR124|`aab57504262fff739d0754145c61a61efa79791a`|固定SHA只读，不等待、不合并；核候选区域、外包与接受状态定义|
|moon1_bias_dynamics_eval：已合并PR120|PR head `8765e12377966cb527e1bbb51e47f7699eaada6b`；读取main `0c3dbbb59a5c65087e073ad1c49eaed397f2958b`|读取 REPORT、DECISION_MEMO 及对应联合状态/偏差注入实现；不重跑实验|

检索结论以具体来源的条件为限。集中式联合估计已有的跨车辆、跨时刻耦合，不等于另行建模了有色输入噪声；相关误差文献的迁移不能默认要求改成分布式。constant/step/ramp 结果保留其探索性样本口径，不升级为完好性风险保证。

交付复核：远端main已前进到 `30f9379249a4e695acf75910c40862a770e6f4ce`，PR123/124已合并，head与本轮读取版本一致；PR122仍OPEN且head未变。见 [DELIVERY_ENVIRONMENT.json](notes/DELIVERY_ENVIRONMENT.json)。链接检查对受限、限流和脚本响应分别记录，原文版本访问证据不由一次HEAD结果取代。
