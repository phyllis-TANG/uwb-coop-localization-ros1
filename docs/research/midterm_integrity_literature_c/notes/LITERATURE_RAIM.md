# 解分离、故障假设与选择后分布：原文核查

检索日期：2026-11-17。范围包括IEEE原发表页面、NSF公开存档、作者机构主页与Curtin作者公开稿；用题名、DOI、solution separation、nonlinear integrity、fault exclusion和robot localization组合检索，而非仅UWB。本文为文献与适用性核查，不运行定位、抽样或数值实验。以下“项目推论/拟验证”均不是所引论文的实验结果。

## L-SS：Abdul Hafez 等，2020，固定滞后机器人定位的解分离

**核实书目。** Osama Abdul Hafez, Guillermo Duenas Arana, Mathieu Joerger, Matthew Spenko. *Quantifying Robot Localization Safety: A New Integrity Monitoring Method for Fixed-Lag Smoothing*. IEEE Robotics and Automation Letters, 5(2), 3182–3189, 2020。DOI [10.1109/LRA.2020.2975769](https://doi.org/10.1109/LRA.2020.2975769)。正式期刊论文，不是仅有预印本；PDF首面注明2020-01-27接受，IEEE页注明2020-02-21发表。原始来源：[NSF全文](https://par.nsf.gov/servlets/purl/10203881)、[IEEE发表页](https://xplorestaging.ieee.org/document/9006956)、[作者Virginia Tech发表列表](https://www.aoe.vt.edu/people/faculty/joerger/personal-page/publications.html)。已阅读8页全文并目视核对关键公式页；未取得可核验的作者配套代码仓，不以第三方论文清单代替代码。

**原文内容定位（精简概括）。** p3183式(2)/(5)分别给Gaussian白噪声加确定性故障和随机先验；式(7)–(10)在收敛点线性化。p3184式(11)–(13)定义超告警限且未告警事件及故障假设求和；式(16)–(19)给全解与假设剔除子解的分离及阈值。p3185式(29)–(33)用无故障子解误差和分离阈值包住全解误差，核心为

$$P(\mathrm{HMI}\mid H_i)\le 2\Phi\!\left(\frac{T_{\Delta_i}-l}{\sigma_i}\right),\quad \sigma_i^2=\alpha^T\Lambda_i^{-1}\alpha.$$

假设身份定义故障位置；幅度未知。p3184要求假设互斥完备，并说明截断故障数时需计未覆盖风险。p3187–3188的“较少测量”仍是有绝对地标/先验且动态调窗的例子，不是无冗余网络定理。以上页码为期刊页，分别对应PDF第2–7页。

### 针对本项目的适用性推论

1. **可借模块是事件、假设与子解接口。** 当前B2由实验指定单一peer常偏差候选；B3减真实注入，二者都不是未知故障假设管理器。若今后构造SS，需预先列有限故障族和对应剔除行，不能事后知道哪条链故障再只运行那一子解。对未监控模式，必须明确其风险项或确定性范围；无P(H_i)依据时，不可给带任意先验权重的总体HMI承诺。
2. **低冗余先做秩审查。** 把当前白化线性矩阵记为A，状态维数d。原文用Λ_i^{-1}实际上要求每个保留行矩阵B_i A满列秩。N>d只是总数量必要性的一部分，不保证故障剔除后还可定位；共线横向零空间和偏差列混淆不会由“观测条数很多”消失。残差检验还需正剩余自由度N−d；失秩应输出不可用，不能加ridge后声称该故障假设已监控。
3. **先验机制必须重建。** 该文把历史先验估计看作随机测量，并可把先前故障归入先验故障假设。PR116的δc是固定未知量，白化先验行不是重复Gaussian噪声。即使H满秩，也不能直接搬用逆信息作为随机协方差，或把固定survey行作为独立随机冗余。需要另以本项目的G与噪声块传播，固定中心偏移另计；本轮不把这些模块拼成新定位器。
4. **线性与非线性保证不同。** 原文Gaussian误差与协方差差公式依赖线性化模型。对于本项目，终点Jacobians、分支和告警决策均随数据变化；全解和各子解可能停于不同分支。共同固定A下的线性协方差恒等式不能不经证明用于不同终点的非线性子解。原文没有提供覆盖所有分支的非线性余项上界，可作为完好性结构参考，不能直接消除PR115/116已经观察到的非线性问题。
5. **范围与概率语义。** 该文主要是滑窗估计下当下兴趣方向的HMI概率；并非整段任务联合风险证明。本项目逐车二维径向误差和六时刻联合事件要分别定义。接受条件事件的概率不同于P(失效且未告警)，也不同于可用率；今后全部计划输入均须记录输出/拒绝/数值失败。

### 原发表公开PDF中的公式一致性问题

这是本次逐式核查发现，**不是对作者代码或全部结论的推断**。NSF公开正式排版PDF p3185式(35)写成“误差超过l”的概率乘未检测概率；但式(36)显示的Gaussian因子为

$$\Phi((l-\mu)/\sigma)-\Phi((-l-\mu)/\sigma),$$

它是区间内概率。p3186式(39)继续使用相同CDF差。已目视PDF确认，并非仅由文本提取引起。按p3185对Φ为标准正态CDF的定义，且令μ=0、l趋于无穷，该CDF差趋于1，而超限概率应趋于0；因此公开版本(35)与(36)不一致。超限因子的直接概率恒等式应为

$$1-\Phi((l-\mu)/\sigma)+\Phi((-l-\mu)/\sigma).$$

没有在当前可得原始来源中核实勘误，不能假定作者实现同错，也不能借此否定SS式(33)。迁移时必须从事件定义重推，并向后核对原始参考/作者更正；不可照抄式(36)/(39)实现CS风险计算。SS式(33)在l≤T时还只能给平凡上界，应与1截断；它不提供有用的小风险界。

### 最小后续验证与可否定结果（本轮未执行）

先只建立一个满秩、固定矩阵的仿射对照，固定一种已声明故障族，逐一检查全解及剔除子解秩、Cov(Δ_i)=Cov(e_i)−Cov(e_0)的适用性、告警/未告警/HMI/不可用四种计数及CDF尾部极限。不同时加鲁棒核、多分支包络和故障估计。若仿射对照已不满足解析关系，优先否定实现或先验/噪声合同，不归因非线性；若仿射通过而非线性失败，才检验共同线性化与分支假设。若删除任一允许故障后兴趣方向不可辨识，该SS路线在该故障族上不具可用性，需改变信息结构或如实拒绝输出，不能靠调阈值补救。

## L-SEL：Teunissen、Imparato与Tiberius，2017，正确排除后的估计偏差

**核实书目。** Peter J. G. Teunissen, Davide Imparato, Christian C. J. M. Tiberius. *Does RAIM with Correct Exclusion Produce Unbiased Positions?* Sensors, 17(7), article 1508, 2017。DOI [10.3390/s17071508](https://doi.org/10.3390/s17071508)。正式发表，2017-06-26；[出版页](https://www.mdpi.com/1424-8220/17/7/1508)、[作者机构16页全文](https://gnss.curtin.edu.au/wp-content/uploads/sites/21/2017/06/Teunissen2017DoesRaim.pdf)。已阅读全文，数学重点为§2–4（pp2–10）；本文自身不是完整非线性PL构造器。

**原文公式定位（精简概括）。** pp2–3式(1)/(3)用已知正定Q及固定满秩A建立Gaussian线性模型，并要求[A,C]满列秩；Cb为未知偏差。p4式(10)把检验后估计定义为依据同一数据切换的分段估计器。p5式(14)给其残余偏差；p7式(20)–(21)说明即使在正确拒绝事件内，估计也可能仍有偏。核心写为

$$\bar x=\begin{cases}\hat x_0,&\hat b\in\mathcal A,\\\hat x_a,&\hat b\notin\mathcal A,\end{cases}\qquad E[\bar x\mid H_a]-x=A^+C\int_{\mathcal A}\beta p_{\hat b}(\beta\mid H_a)\,d\beta.$$

p9式(23)起推广到多个备择假设。已知的是各候选C_i，而不是实际故障身份。其解析结论是对规定检验规则的线性模型，不能扩大为所有剔除方法的统一数值性能。

### 项目迁移推论与具体模块

- 最值得借鉴的是把“检测/候选选择/剔除”作为估计器的一部分分析。Gaussian测量经过数据依赖的候选选择或分支选择，不再自动有单Gaussian估计误差；正确候选子模型的无偏性质不能直接移交给选择后的输出分布。
- 本项目现有B2候选是预先指定，尚未实施RAIM选择，因此不能用这篇文献断言当前B2欠覆盖已被“选择偏差”解释。若下一轮只做固定候选机制诊断，本问题是未来接口审查项；若按数据挑最佳分支/最小区域/最佳候选，则立刻成为必须纳入的效应。
- [A,C]满秩要求与当前单常偏差可辨识性直接相连。增广一列不等于获得冗余；共线或删除墙链后若秩下降，BLUE方差及原检验公式可能不存在。本文的线性结论不控制非线性距离余项，也未为固定中心集合Dρ提供现实依据。
- 最小后续验证应先明确“始终使用正确已知模型”“按同批数据检验后切换”“拒绝输出”三种不同映射，验证其条件均值与全计划事件分母。若只评正确选择子集却宣称总体覆盖，设计本身不足；若预先固定候选且不作数据选择，该论文的选择机制不能充当当前失败因果。

## 仅作为背景、未完成公式全文核查的条目

1. **O'Brien & Rife (2009), Propagating Integrity Bounds in Nonlinear State Estimation.** [ION官方发表记录](https://m-private.ion.org/publications/abstract.cfm?articleID=8588)、[作者实验室列表](https://sites.google.com/a/tufts.edu/asar/)确认会议发表；官方页列pp1807–1818，全文需下载额度，未取得2009论文全文。只知道其摘要描述prediction step与unsigned bias，不写原公式/推导/性能，不以2010同题学位论文替代2009正式文。
2. **Joerger, Chan & Pervan (2014), Solution Separation Versus Residual-Based RAIM.** [出版页](https://onlinelibrary.wiley.com/doi/10.1002/navi.71)确认NAVIGATION 61(4),273–291及DOI10.1002/navi.71。当前已核对书目与摘要，未取得完整正文；Hafez文对其的引用不算逐式核查，不将其添加为“已精读核心”。

## 全文访问留痕

原论文PDF仅下载至临时目录，未复制进仓库；正式书目和公开链接已在上文给出。

|文献|读取版本|本次下载SHA256|
|---|---|---|
|Hafez2020|NSF存档的IEEE正式排版8页，页3182–3189|`3f7fbdcc64cd90c6ad277226c5d01a67eb0134b5be1db86c772383b5229c9651`|
|Teunissen2017|Curtin作者机构公开的Sensors正式排版16页|`5247da2f508b74101ec4e352895e078b5dfc5a670b836b975d15d4c3ac9fd2cf`|

检索Hafez题名+github/code没有得到可确认的作者实现；检索DOI+correction/erratum未核实到更正。此处仅报告本次检索结果，不宣称代码或勘误在其他渠道不存在。正文数学页以PDF像素核验为准，网页索引的“Published: months ago”不作为首次发表日期。

## 可供主文件采用的BibTeX（已核对元数据）

```bibtex
@article{AbdulHafez2020FixedLagIntegrity,
  author = {Abdul Hafez, Osama and Duenas Arana, Guillermo and Joerger, Mathieu and Spenko, Matthew},
  title = {Quantifying Robot Localization Safety: A New Integrity Monitoring Method for Fixed-Lag Smoothing},
  journal = {IEEE Robotics and Automation Letters},
  year = {2020}, volume = {5}, number = {2}, pages = {3182--3189},
  doi = {10.1109/LRA.2020.2975769},
  url = {https://par.nsf.gov/servlets/purl/10203881}
}
@article{Teunissen2017CorrectExclusion,
  author = {Teunissen, Peter J. G. and Imparato, Davide and Tiberius, Christian C. J. M.},
  title = {Does {RAIM} with Correct Exclusion Produce Unbiased Positions?},
  journal = {Sensors}, year = {2017}, volume = {17}, number = {7}, pages = {1508},
  doi = {10.3390/s17071508},
  url = {https://gnss.curtin.edu.au/wp-content/uploads/sites/21/2017/06/Teunissen2017DoesRaim.pdf}
}
@article{Joerger2014SolutionSeparation,
  author = {Joerger, Mathieu and Chan, Fang-Cheng and Pervan, Boris},
  title = {Solution Separation Versus Residual-Based {RAIM}},
  journal = {NAVIGATION}, year = {2014}, volume = {61}, number = {4}, pages = {273--291},
  doi = {10.1002/navi.71}, url = {https://doi.org/10.1002/navi.71},
  note = {Metadata verified; full text not accessed in this audit}
}
```
