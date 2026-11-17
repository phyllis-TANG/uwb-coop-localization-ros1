# 集合反演、Gaussian噪声与固定有界偏移：全文核查笔记

检索日期：2026-11-17。任务只读文献及固定仓库来源；没有定位运行、观测生成、随机抽样或新估计器实现。以下“原文”摘要与“本项目独立推导/迁移判断”分开，不把拟议扩展归给作者。

## 1. 全文与发表身份

|键|已核实发表|实际精读版本与访问限制|
|---|---|---|
|JW93|Luc Jaulin, Eric Walter. *Set inversion via interval analysis for nonlinear bounded-error estimation*. Automatica 29(4), 1053–1064, 1993. DOI [10.1016/0005-1098(93)90106-4](https://doi.org/10.1016/0005-1098(93)90106-4)|[作者托管的期刊版完整12页PDF](https://webperso.ensta.fr/jaulin/paper_automatica93.pdf)。核对首页期刊、作者、页码及出版信息；[出版社条目](https://www.sciencedirect.com/science/article/abs/pii/0005109893901064)核对DOI。不是预印本。|
|NJ20|J. Nicola, L. Jaulin. *Guaranteed Nonlinear Parameter Estimation with Additive Gaussian Noise*. 正式Springer书章，2020，pp.341–357，Studies in Computational Intelligence 835. DOI [10.1007/978-3-030-31041-7_19](https://doi.org/10.1007/978-3-030-31041-7_19)|[作者公开17页稿](https://webperso.ensta.fr/jaulin/paper_region.pdf)全文可读；[出版社页面](https://link.springer.com/chapter/10.1007/978-3-030-31041-7_19)核实2020-02-29正式在线、作者、书章和页码。公开稿仍带“Reliable Computing, 2018 / Template”页眉，故下述公式号和页码明确指**公开稿自身1–17页**，不假定与最终书章逐式完全相同；出版社最终PDF未取得。|

临时核验文件未加入仓库：`/tmp/integrity-sets-c/sivia.pdf` SHA256 `b10574cec919688e8c02c1dfeec9d48492e37e1688cab7645b3bc6c5793cbefe`；`region.pdf` SHA256 `945e7da43c33ce4f08c1de43d9584c7f71a18bb2b5e9c17e9484c7bc6f32fd41`。全文读取包括方法、定理条件、实例、讨论和参考文献，不以搜索摘要代替公式核对。原站TLS偶有超时，作者站HTTP别名成功下载；没有绕过付费墙。

## 2. JW93核心核对

原问题是给定误差可行集合与参数先验可行域，求所有与测量一致的参数。p.1053式(1)–(3)、p.1054式(4)给出

$$S=\{p\in P:y-y_m(p)\in E\}=y_m^{-1}(y-E)\cap P.$$

p.1056 Definition 6要求区间包含函数包住真实函数像；p.1060–1061 §5给出盒分类及二分。p.1061式(36)保留内集合与包括未决盒的外集合：$K_{in}\subseteq S\subseteq K_{out}$。Theorem 1另有逆映射连续性、内部逼近所需full-set等条件；p.1061 §5.2.2明确维数是计算代价的主要限制。[原文PDF](https://webperso.ensta.fr/jaulin/paper_automatica93.pdf)

**本项目迁移判断。** 这是确定性包含结论，不是Gaussian置信水平或故障概率定理。若故障未知却未放入模型或误差域，外包计算不会自动补上它。初始搜索域须覆盖拟保护的全部状态/分支；多解允许保留为分离盒集，不能仅在选中的局部终点附近搜索。区间法本身不要求先求逆H，但不能因此声称低冗余时有小区域或可用保护级。退化集合的内部盒可能为空；外部包含与逼近收敛速度是不同要求。

可借鉴模块仅为“包含函数＋全部未排除分支的外包证书”。最小后续验证应先在有解析双分支的二维距离模型检查：真分支是否均包含、无根盒是否排除、未知盒是否保留、收紧网格是否只改善外包精度。若真实可行点在规定域内却被排除，否定包含实现；若域内始终出现超大/不收缩的外包，只能否定当前精度/算力下的可用性，不能声称概率保证因而成立。

## 3. NJ20核心核对

公开稿p.2式(1)–(2)使用$y=\psi(p)+e$、白化后$e\sim N(0,I_n)$，将**测量噪声集合**$E_\eta$反演成$\widehat P_{E_\eta}=\{p:y-\psi(p)\in E_\eta\}$。p.3式(3),(6)的球满足$\|e\|^2\le\chi_n^2(\eta)$；p.4式(13)给出独立单位Gaussian同时落入立方体的半宽。p.10式(21)是近共线三信标、已知信标位置及机器人高度的静态测距例；p.8、p.10讨论分离区域与区间保守性。[公开稿](https://webperso.ensta.fr/jaulin/paper_region.pdf)

**本项目迁移判断。** $n$是原始白化随机观测维数，不能替换为最小二乘拟合后残差自由度。噪声球在噪声空间最小体积也不推出其非线性逆像在参数空间最小体积。Gaussian噪声不要求估计误差Gaussian；该路线依靠真参数处噪声事件，而不是H逆。没有未知NLOS定位或概率模型；B2的单候选常$b$可作为参数，但原文没有替本项目证明未知候选、多链路或任意NLOS鲁棒性。当前24/25维短轨迹比文中低维例复杂，不能据原示例承诺部署代价。

**公开稿需谨慎的段落。** p.7 §3式(16)–(17)将单位Gaussian的负对数似然写成$\sum r_i^2$（指数内没有$1/2$），随后将其Hessian称为观测Fisher信息及估计协方差逆；同段又说明所得局部椭圆不可靠。截图已目视核对：`/tmp/integrity-sets-c/region-p7.png`。单位Gaussian规范负对数似然应为$\tfrac12\sum r_i^2+const$，因此直接复制该段会混淆尺度；即使归一化修正，有限样本非线性估计器的随机协方差也不因此精确等于H逆。这是公开稿局部比较段的审计，**不否定式(2)噪声事件反演**，也不断言最终付费版保留同样写法。

## 4. 对当前模型的独立代数推导（不是上两篇原文定理）

固定证据为PR116 `34f364d77c0964f22563bad6e5869567fe5f163c`，`docs/research/midterm_bias_region_b/MATH.md`。设真实数据为$y=h(\theta_*)+\epsilon$，$\epsilon\sim N(0,R)$，$R$已知正定。固定survey中心满足$c-E\theta_*\in D$，$D$由独立证据预先确定，且$\theta_*\in X$。此处$D$与$X$不是随机Gaussian先验。定义

$$\mathcal C_\eta(y,c)=\left\{\theta\in X:
\|R^{-1/2}[y-h(\theta)]\|^2\le\chi_m^2(\eta),\quad c-E\theta\in D\right\}.$$

对每个满足上述固定条件的$\theta_*$，事件$\epsilon^\top R^{-1}\epsilon\le\chi_m^2(\eta)$蕴含$\theta_*\in\mathcal C_\eta$；在本式没有额外未知随机量且精确计算时二者等价。概率来自重复测量，不是给定这一次数据后的Bayesian后验质量。若另有未知有界干扰$\delta\in D$，用联合$(\theta,\delta)$可行集并向$\theta$投影，则真参数覆盖至少为$\eta$；投影可能增大集合，不能仍声称恰好$\eta$。有限外包$\mathcal C_{out}\supseteq\mathcal C_\eta$保留该下界。

三项实现前提是这个推论的一部分：

1. 固定先验行不进入Gaussian维数$m$。先验可信范围作为硬集合约束；若以后先验真有独立随机观测，需重新构造联合噪声模型。
2. 应使用完整非线性$h$或经严格包含的表达，不能把终点Taylor展开冒充全局逆像。若用Taylor加余项，需在每个保留域上给出统一有效的余项集合，覆盖跨分支及接近零距离时的适用问题；有限差分吻合只检查局部导数。
3. 搜索盒/边界不能由真值挑选，也不能删除到盒外的可行分支。若无法证明全体可能状态已被覆盖，结论只能条件于搜索域。区域过大、未完成外包、空集或投影不有界时，应拒绝给有限保护级，并纳入可用率分母。

这一路线避免“精确H逆=随机协方差”陷阱，也避免仅靠残差通过选一个可靠位置。但它仍需要独立噪声尺度、完整故障假设、外部固定偏移集合以及可信计算域。缺少上述依据时，严格算法只能严格回答错误的条件问题。

## 5. 最小后续对照建议（本轮不执行）

|问题|只改变一个模块的最小验证|应保留的反证/不利结果|
|---|---|---|
|线性参照概率语义|解析仿射模型对比噪声事件反演与PR116既有局部Minkowski候选；检查完整噪声维数、固定先验不随机化|若同一正确噪声事件下真状态被反演排除，优先查白化、约束或包含实现，不归因非线性|
|弱几何多分支|从二维/降维单时刻镜像测距问题开始，原样保留两个分支；只比较局部区域与全域外包|只保留真值附近一支的“覆盖改善”无效；分支未穷尽则不能给全局证书|
|固定偏移包含前提|在冻结$D$内检查轴向、非轴向及边界偏移，另列域外反例；区分测试设计与全集合证明|域外失效不能反调D；有限轴向通过不证明整个四维球|
|余项与域依赖|若选择局部扩展，只引入经证明的一个余项界，检查其在指定域上的包含|界在域内失败否定该余项构造；界始终过大则显示可用性代价|
|有限资源与拒绝|预先给定外包计算预算，未决盒计入外包或输出不可用，不能丢弃|拒绝输出但从分母删除会制造虚假的条件覆盖；有限保护级必须附可用性|

如果对整个六时刻状态一次建立同一个噪声事件和全状态集合，其投影可共享该联合事件；这与对每个时刻单独使用95%椭圆不同。未来保护级仍需把外包映射到预先指定的误差指标、告警限和任务事件，再处理故障未覆盖风险；本笔记不设最终风险预算。

## 6. 公开软件与未核实材料

[Codac官方v1集合反演说明](https://codac.io/v1/manual/11-separators/index.html)公开SIVIA接口及IN/OUT/UNKNOWN分类；[官方FAQ](https://www.codac.io/v1/faq.html)说明Gaussian转有限区间本身引入尾部风险。它们是可考虑的未来实现基础，不是已复现这两篇论文的代码，亦未在本轮安装或运行。没有查到NJ20所用三例的可固定版本代码链接，故不编造仓库地址。其他搜索线索（LSCR/SPS非渐近区域、区间机器人跟踪）仅作背景，不据摘要代写公式或性能。

## 7. 可纳入REFERENCES.bib的核实条目

```bibtex
@article{JaulinWalter1993,
  author = {Jaulin, Luc and Walter, Eric},
  title = {Set inversion via interval analysis for nonlinear bounded-error estimation},
  journal = {Automatica},
  year = {1993},
  volume = {29},
  number = {4},
  pages = {1053--1064},
  doi = {10.1016/0005-1098(93)90106-4},
  url = {https://webperso.ensta.fr/jaulin/paper_automatica93.pdf},
  note = {Published article; author-hosted publisher-layout full text checked 2026-11-17}
}

@incollection{NicolaJaulin2020,
  author = {Nicola, J. and Jaulin, L.},
  title = {Guaranteed Nonlinear Parameter Estimation with Additive Gaussian Noise},
  booktitle = {Beyond Traditional Probabilistic Data Processing Techniques: Interval, Fuzzy etc. Methods and Their Applications},
  series = {Studies in Computational Intelligence},
  volume = {835},
  pages = {341--357},
  publisher = {Springer},
  year = {2020},
  doi = {10.1007/978-3-030-31041-7_19},
  url = {https://link.springer.com/chapter/10.1007/978-3-030-31041-7_19},
  note = {Publication metadata verified; formulas checked against author manuscript https://webperso.ensta.fr/jaulin/paper_region.pdf, whose pagination is 1--17 and whose header is a 2018 template; final publisher PDF not accessed; checked 2026-11-17}
}
```
