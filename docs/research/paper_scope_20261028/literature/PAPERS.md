# 逐论文核查与阅读范围

截至2026-10-28。FULL表示正文已读，不表示推导已经独立证明或代码已运行；部分/摘要的未知字段保留未知。9篇=5篇指定近邻＋4篇直接补充。P6正式版与预印本版本分开，P8仍是预印本。检索到不等于已读全文；没有搜到代码不等于不存在。

| ID | 论文 | 阅读范围 |
|---|---|---|
| P1 | [Quantifying Robot Localization Safety: A New Integrity Monitoring Method for Fixed-Lag Smoothing](https://par.nsf.gov/servlets/purl/10203881) | 全文：8页正文、关键公式与算法；视觉核对p.3184；参考文献不作为已读论文 |
| P2 | [Integrity Monitoring for GNSS Positioning Via Factor Graph Optimization in Urban Canyons](https://ira.lib.polyu.edu.hk/bitstream/10397/93579/1/Wen_Integrity_Monitoring_Gnss.pdf) | 全文：机构库8页，出版社元数据交叉核实 |
| P3 | [Exploiting redundancy for UWB anomaly detection in infrastructure-free multi-robot relative localization](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2023.1190296/full) | 全文：出版社HTML和10页PDF，视觉核对PDF p.6 Algorithms 1/2 |
| P4 | [Solution separation integrity monitoring method for factor graph optimization-based loosely coupled GNSS/INS navigation under GNSS position-solution faults](https://www.sciencedirect.com/science/article/abs/pii/S0273117726013074) | 仅出版社公开预览的摘要和贡献列表（检索服务索引）；Crossref完整元数据。全文未获取；普通直连返回195字节机器人拦截页，不算文章 |
| P5 | [Geometric Clustering for Distributed Fault Detection and Identification in Range–Based Cooperative Localization Without Fixed Reference Nodes](https://www.mdpi.com/2076-3417/16/10/5137) | 全文：官方HTML §§1–8、公式/Algorithm 1、表1及图注；公开代码选读，不运行 |
| P6 | [Decentralized Cooperative Localization With LoS and NLoS UWB Inter-Agent Ranging](https://arxiv.org/abs/2009.03538v3) | 作者预印本选读§§I/III–VI及实验；正式期刊元数据由Crossref核实，正式版全文未逐页核对 |
| P7 | [Integrity Monitoring for Extreme Indoor Environment Positioning Based on Ultrawideband](https://www.ion.org/publications/abstract.cfm?articleID=18610) | 仅出版社完整摘要与出版字段；全文需下载额度，未获取/未绕过 |
| P8 | [Incremental-Smoothing-Based ARAIM Protection Levels for Tightly Coupled GNSS/IMU Integration in Urban Canyons](https://arxiv.org/abs/2610.32259v1) | 全文：作者预印本15页正文/图表，重点§III–IV、§V-D5与VI；PDF署名Qian Meng而arXiv元数据显示Meng Qian，依题名页登记 |
| P9 | [Fault-tolerant multi-robot localization: diagnostic decision-making with information theory and learning models](https://link.springer.com/article/10.1007/s10514-025-10196-6) | 仅出版社摘要、出版/Code availability字段；正文订阅受限，未以图缩略图代全文 |

## P1：Quantifying Robot Localization Safety: A New Integrity Monitoring Method for Fixed-Lag Smoothing

**书目核实**：Osama Abdul Hafez; Guillermo Duenas Arana; Mathieu Joerger; Matthew Spenko。IEEE Robotics and Automation Letters 5(2):3182–3189; online 2020-02-21, issue 2020-04。 DOI：[10.1109/LRA.2020.2975769](https://doi.org/10.1109/LRA.2020.2975769)。

**阅读范围**：全文：8页正文、关键公式与算法；视觉核对p.3184；参考文献不作为已读论文。

**可定位证据**：§II-B Eq.(5); §III Eq.(11)–(13); §IV-A Eq.(17)–(19); §V-A Eq.(33); Algorithm 1; §VII。阅读链接：https://par.nsf.gov/servlets/purl/10203881。

**问题与方法**：窗口观测的未知确定性故障；明确包含窗口之前进入prior的故障；已知地标range/bearing、轮式/惯性相对测量；实车LiDAR/IMU/DGPS；单机器人集中式fixed-lag；非多机器人协议。

**不可省略的条件**：每个故障排除假设仍可估计；噪声协方差和故障先验概率已给定；实验动态调窗维持观测冗余。同时故障：一般假设集合可含同时故障；截断阶数须计未监测概率；实验仅绝对观测可故障。

**参照与历史**：全量解与各故障假设的排除解；假设匹配时排除解才无故障，未把任意影子当真值。固定滞后历史＋prior故障假设；不是仅当前历元。

**可用性与验证**：HMI风险、报警及风险要求下可用性；不是完整在线重建/再准入策略。真值/实验：仿真真值；实车完整性示例未核实额外独立全轨迹真值，不把输入DGPS当独立GT。

**代码/许可**：论文末尾链接mspenko/RoboticsLab-Integrity-Evaluation；MATLAB SS目录存在。GitHub license=null；已查根/相关SS目录未见许可；全递归索引截断，不能断言全库无许可。

**对选题的判断（本次推断）**：已覆盖固定窗口SS、先验故障及可用性；仅加入prior/故障假设不新颖。

## P2：Integrity Monitoring for GNSS Positioning Via Factor Graph Optimization in Urban Canyons

**书目核实**：Weisong Wen; Qian Meng; Li-Ta Hsu。Proceedings of ION GNSS+ 2021, pp.1508–1515, 2021-09-20–24。 DOI：[10.33012/2021.18157](https://doi.org/10.33012/2021.18157)。

**阅读范围**：全文：机构库8页，出版社元数据交叉核实。

**可定位证据**：§4 Eq.(4)–(8); §5.1; p.1513最大残差归责局限; §6。阅读链接：https://ira.lib.polyu.edu.hk/bitstream/10397/93579/1/Wen_Integrity_Monitoring_Gnss.pdf。

**问题与方法**：城市多路径/NLOS引起的伪距故障；Doppler作为较不敏感辅助；低成本GNSS伪距/Doppler；单接收机集中式滑窗FGO。

**不可省略的条件**：利用跨历元冗余；残差噪声模型与可解几何；不保证最大残差对应真故障。同时故障：目标为多故障城市条件；迭代最大残差排除，未证明任意同时故障可归责。

**参照与历史**：由全部剩余观测得到的FGO解及归一化后验残差。窗内重复审查；已排除历史观测不带入下一窗重新考虑，§6留为后续。

**可用性与验证**：统计测试/迭代排除；未给低冗余unknown完整协议或PL；PL列为后续。真值/实验：独立NovAtel SPAN-CPT RTK/INS参考，§5.1；不是低成本GNSS输出本身。

**代码/许可**：引用GraphGNSSLib基础定位，不等于本篇FDE完整实现；专用FDE代码未核实。本篇专用实现许可未核实，不从基础库推定。

**对选题的判断（本次推断）**：滑窗FDE和错误排除问题已明确；仅换UWB/窗口/阈值不足以构成B贡献。

## P3：Exploiting redundancy for UWB anomaly detection in infrastructure-free multi-robot relative localization

**书目核实**：Sahar Salimpour; Paola Torrico Morón; Xianjia Yu; Tomi Westerlund; Jorge Peña-Queralta。Frontiers in Robotics and AI 10:1190296, published 2023-12-22。 DOI：[10.3389/frobt.2023.1190296](https://doi.org/10.3389/frobt.2023.1190296)。

**阅读范围**：全文：出版社HTML和10页PDF，视觉核对PDF p.6 Algorithms 1/2。

**可定位证据**：§3.1–3.3, Algorithms 1/2, Eq.(2)–(4); Figs.2/3/6/8; §4.3; §5。阅读链接：https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2023.1190296/full。

**问题与方法**：UWB收发节点时序/硬件异常造成多条对外距离异常；不是只检测单链NLOS；节点间UWB ToF；未将Odom融入本文定位；集中式笔记本ROS2；相对构型对齐。

**不可省略的条件**：多对基节点生成多配置；需足够成对距离、第三点解镜像与配置对齐。同时故障：仿真每8节点1异常，可多异常；无任意共模/低冗余保证。

**参照与历史**：多基节点配置的LSE与去可疑配置后的离散度；明确讨论异常基节点。逐时间戳配置检测；低速约0.3m/s、14Hz/距离，近同步近似；无边缘化历史。

**可用性与验证**：检测后删除异常相关配置；未建立本项目式拒判占用/历史恢复指标。真值/实验：实物OptiTrack MOCAP；仿真真值；节点5实际NLOS与注入节点异常分别讨论。

**代码/许可**：文称ROS2实现；未从正文核实一一对应的公开方法仓库。文章CC BY；未核实对应代码许可，文章许可不替代代码许可。

**对选题的判断（本次推断）**：A的异常传播/多参照归责有直接先例；仅多影子比较或先排错再优化不新颖。

## P4：Solution separation integrity monitoring method for factor graph optimization-based loosely coupled GNSS/INS navigation under GNSS position-solution faults

**书目核实**：Ershen Wang; Shuqi Chang; Tengli Yu; Deyan Wang; Huishuo Feng; Yongkang Wang; Song Xu; Pingping Qu。Advances in Space Research; online 2026-09-15, Corrected Proof; Crossref已编排78(11):10528–10548, 2026-12未来期次。 DOI：[10.1016/j.asr.2026.09.026](https://doi.org/10.1016/j.asr.2026.09.026)。

**阅读范围**：仅出版社公开预览的摘要和贡献列表（检索服务索引）；Crossref完整元数据。全文未获取；普通直连返回195字节机器人拦截页，不算文章。

**可定位证据**：公开Abstract及贡献1–3；不能引用未知正文节/公式。阅读链接：https://www.sciencedirect.com/science/article/abs/pii/S0273117726013074。

**问题与方法**：GNSS位置解故障；不是原始UWB链故障；GNSS/INS松耦合；滑窗FGO、逐历元监测；其他架构细节需全文。

**不可省略的条件**：摘要称保守分离不确定度、独立nominal标定、配置一致先验；具体条件未知。同时故障：GNSS位置解注入；惯性和GNSS/INS组合故障未评估（摘要自述）。

**参照与历史**：解分离＋二次一致性检验；可信检查点来源/触发/重建细节未知。摘要明确递归候选隔离集、configuration-consistent working priors、trusted checkpoints。

**可用性与验证**：摘要明确检测、缓解、重估验收、PL、可用性统一流程；拒判/恢复细则未知。真值/实验：公开车载数据＋人工注入（摘要）；参考来源/误差界未从全文核实。

**代码/许可**：全文未得，未核实完整方法仓库。未核实代码许可；出版社全文受限。

**对选题的判断（本次推断）**：A/B历史先验与恢复候选的实质重合警报；全文未读不能断言覆盖全部，也不能宣布绕过该文。

## P5：Geometric Clustering for Distributed Fault Detection and Identification in Range–Based Cooperative Localization Without Fixed Reference Nodes

**书目核实**：Uthman Olawoye; Jason N. Gross。Applied Sciences 16(10):5137, published 2026-05-21。 DOI：[10.3390/app16105137](https://doi.org/10.3390/app16105137)。

**阅读范围**：全文：官方HTML §§1–8、公式/Algorithm 1、表1及图注；公开代码选读，不运行。

**可定位证据**：§2.1/Table1; §2.4 Eq.(4); §3 Eq.(6); §4.2.2–4.2.4; Eq.(14); §5; §6.3/6.5; §7。阅读链接：https://www.mdpi.com/2076-3417/16/10/5137。

**问题与方法**：移动peer广播位置持续偏差而协方差不变；测距名义高斯；模拟UWB＋VIO位置/协方差广播；分布式snapshot FDI＋网络投票；融合后端未评估。

**不可省略的条件**：5邻居形成5个LOO＋10个LTO；4邻居仅LOO、3邻居仅检测/拒绝归责、少于3不可解；单坏peer。同时故障：当前方法仅单坏peer；双坏peer只剩一个无污染子集，不能形成健康簇。

**参照与历史**：子集WLS解的几何聚簇，识别健康组；坏参照/最大残差错归责是正面对象。仅当前快照；不评FGO边缘化prior、故障撤除后的恢复。

**可用性与验证**：§2.1已有低连接拒绝归责；§4.2.4模糊集有probable fallback；同步投票/无丢包假设；§6.2识别正确率以Stage1已触发为条件，不能当完整管线的无条件成功率。真值/实验：仅仿真，1000次MC；窄廊为单示例；不把仿真结果写成硬件验证。

**代码/许可**：wvu-navLab/FDE；固定检查commit 880203341da70e97065bc608c1ce5689ecc90499；论文/代码多处差异见BASELINES.md。GitHub license=null；完整目录树无LICENSE/COPYING；未获得代码复用许可。文章CC BY不等于代码许可。

**对选题的判断（本次推断）**：最强直接反例：坏参照、多子集和低冗余拒判已做；两车/有限墙锚/固定窗只是条件差别，贡献待证。

## P6：Decentralized Cooperative Localization With LoS and NLoS UWB Inter-Agent Ranging

**书目核实**：Jianan Zhu; Solmaz S. Kia。IEEE Sensors Journal 22(6):5447–5456, issue 2022-03-15；对应2020 arXiv作者预印本题名以An IMM-based开头。 DOI：[10.1109/JSEN.2021.3083724](https://doi.org/10.1109/JSEN.2021.3083724)。

**阅读范围**：作者预印本选读§§I/III–VI及实验；正式期刊元数据由Crossref核实，正式版全文未逐页核对。

**可定位证据**：预印本§III Eqs.(8)–(20), §IV Eqs.(21)–(31), Fig.3/4; §V Fig.6/7。阅读链接：https://arxiv.org/abs/2009.03538v3。

**问题与方法**：LoS/NLoS测距模型不确定与正偏置；不等同坏peer位置广播；UWB、脚载INS；功率型LoS/NLoS概率识别；分散式松耦合IMM/保守相关性处理、SKF偏置处理。

**不可省略的条件**：已初始化共同坐标/本地belief协方差及测距模式概率；保守处理未知车间相关性。同时故障：混合LoS/NLoS；未从所读预印本确认任意同时peer-state故障保证。

**参照与历史**：本地与peer belief＋模式概率；明确不把互相关置零。递归局部滤波历史；非fixed-lag边缘化。

**可用性与验证**：模式概率/偏置补偿保留有益测距；未核实独立unknown/撤故恢复协议。真值/实验：预定路线与回环闭合误差；不能升级为全轨迹独立MOCAP真值。

**代码/许可**：所读预印本给演示视频；未核实同方法公开代码。方法代码许可未核实；arXiv可读不代表代码许可。

**对选题的判断（本次推断）**：A的保留正常协同/概率处理坏测距已有先例；不能只用二值阈值切换声称新贡献。

## P7：Integrity Monitoring for Extreme Indoor Environment Positioning Based on Ultrawideband

**书目核实**：Jianing Li; Yuan Sun; Zhongliang Deng。Proceedings of the 2023 International Technical Meeting of the Institute of Navigation, pp.535–547, 2023-01-24–26。 DOI：[10.33012/2023.18610](https://doi.org/10.33012/2023.18610)。

**阅读范围**：仅出版社完整摘要与出版字段；全文需下载额度，未获取/未绕过。

**可定位证据**：ION Abstract及出版字段；无全文节/公式编号。阅读链接：https://www.ion.org/publications/abstract.cfm?articleID=18610。

**问题与方法**：UWB NLOS粗差和基站物理损坏（摘要）；固定UWB基站与标签；trilateration/LS＋MHSS；具体集中流程需全文。

**不可省略的条件**：采用MHSS和室内误差模型；最少节点/低冗余条件未知。同时故障：故障阶数未知，不能据multiple hypothesis推定支持多同时故障。

**参照与历史**：MHSS子解；具体参照选择/误差模型未知。摘要未说明固定窗或历史；不推定snapshot。

**可用性与验证**：摘要报告报警；拒判、恢复和可用性定义未知。真值/实验：摘要称仿真＋实测；独立真值来源未知。

**代码/许可**：摘要未给方法代码，未核实。未核实；全文受限。

**对选题的判断（本次推断）**：UWB＋MHSS本身已有；B需在低冗余归责/代价问题上另证差异。

## P8：Incremental-Smoothing-Based ARAIM Protection Levels for Tightly Coupled GNSS/IMU Integration in Urban Canyons

**书目核实**：Jiahao Hu; Xiangru Wang; Weisong Wen; Qian Meng。arXiv:2610.32259v1, 2026-10-23；未核实正式接收/期刊出版，PDF期刊模板不作出版证明。 尚无核实的正式期刊DOI，不编造。

**阅读范围**：全文：作者预印本15页正文/图表，重点§III–IV、§V-D5与VI；PDF署名Qian Meng而arXiv元数据显示Meng Qian，依题名页登记。

**可定位证据**：§IV-B4 Eq.(17)–(19); §IV-C Eq.(25); §V-D1/TableIII; §V-D5; §VI。阅读链接：https://arxiv.org/abs/2610.32259v1。

**问题与方法**：当前历元单卫星、星座及二阶伪距故障；持续历史故障明确列为局限；紧耦合GNSS/IMU、Doppler、clock；单车增量fixed-lag FGO＋6层监测，15s。

**不可省略的条件**：完整当前状态marginal、跨状态/历史相关性、假设可移除性/正定性及风险可分配。同时故障：单星/星座/二阶组合；未监测概率显式计入；不是任意历史多故障保证。

**参照与历史**：同一相关posterior的故障排除与全解；SPP辅助参照共享GNSS，不独立。保留历史posterior；当前因子移除的等价性不扩展到历史prior污染，§V-D5明确。

**可用性与验证**：PL-valid、operational availability、navigation output区分；报警时定位可继续。真值/实验：NovAtel SPAN-CPT＋IE参考；参考不确定度和时序相关限制明示；非稀有风险实验证明。

**代码/许可**：文中数据链接可见，方法代码与许可证未核实。未核实方法代码许可；只读作者公开预印本。

**对选题的判断（本次推断）**：不能忽略相关后验/历史、PL与可用性分离已有最新工作；其局限不自动成为我们的已成立贡献。

## P9：Fault-tolerant multi-robot localization: diagnostic decision-making with information theory and learning models

**书目核实**：Zaynab El Mawas; Cindy Cappelle; Maan El Badaoui El Najjar。Autonomous Robots 49(2), article11, published 2025-04-17。 DOI：[10.1007/s10514-025-10196-6](https://doi.org/10.1007/s10514-025-10196-6)。

**阅读范围**：仅出版社摘要、出版/Code availability字段；正文订阅受限，未以图缩略图代全文。

**可定位证据**：Publisher Abstract, Code availability, About this article；无未知正文章/公式。阅读链接：https://link.springer.com/article/10.1007/s10514-025-10196-6。

**问题与方法**：同时传感器故障（摘要）；多传感器；精确类型/是否UWB未知；分散式模型＋数据驱动，两层检测/隔离。

**不可省略的条件**：预测/校正分布Jensen–Shannon指标；训练/冗余要求需全文。同时故障：摘要明确目标同时故障；适用组合/数量需全文。

**参照与历史**：预测与各传感器校正分布；被污染参照的确切处理未知。递归模型细节、窗口长度未知。

**可用性与验证**：分类器检测＋隔离；拒判/再准入/代价未知。真值/实验：Turtlebot3真实数据；真值来源未知。

**代码/许可**：出版社Code availability: Not applicable；未核实其他方法仓库。未核实可复用方法代码许可；全文订阅限制。

**对选题的判断（本次推断）**：不得把同时故障/两层诊断本身称新颖；对参照污染是否已覆盖需合法全文再核实。

## 关键区分

- P1的prior故障建模不是在线prior修复；P4摘要已声称配置一致先验和可信检查点，具体修复/验收必须补读。不能用P1没做修复来无视P4。
- P5的故障是peer广播位置而不是其距离本身；P3针对收发节点相关的多链测距异常；P6针对LoS/NLoS测距模式。三者不能混作同一个故障注入。
- P5已有连接不足拒绝归责，其模糊聚簇又可回退到probable选择；我们的unknown若改变决策/可用性含义，须以完整代价曲线说明，不能只更名。
- P8当前因子移除的线性代数等价依赖因子只作用当前状态；不能把已进入旧窗/边缘化prior的故障当作同样被移除。它不等于已处理所有历史污染。
- P5完整方法需要6机器人和投票；两车＋墙锚的局部适配必须标适配，不能删除投票/低冗余门槛后称原论文完整方法。
- 本轮额外发现但未纳入9篇主表：Hafez等PLANS2020误关联论文（DOI 10.1109/PLANS46316.2020.9110126）属于已知ID之外的故障对象；作者站下载404，只有机构摘要及正文索引片段。未把这些算全文或追加一条凑数量。

## 跨论文指标不能直接混算

P1的可用性是完整性风险低于要求的时间比例；P5的部分识别率以检测触发为条件；P8分别统计PL有效、业务可用和仍有导航输出。我们若报告unknown链秒/车秒或故障恢复延迟，必须另外统一分母，含未检测、拒判、失败和删失，不能拿条件识别率对比全程可用率。
