# C端：完好性文献与方法路线核查

研究目标仍为 **Safety Quantification for Multi-Agent Cooperative Localization in Lunar Exploration**。本轮为完成原定安全量化目标核查可用理论与方法，不降低目标，也不把尚未完成的保护级环节写成成果。检索日期：**2026-11-17**。

**范围：仅文献、公式与适用性审计。新增定位运行0、仿真0、随机抽样0、新定位器0；未修改中期正文、已有实验/协议或其他窗口代码。** 只新增本目录。

## 最重要的发现

1. **下一轮“线性正常/异常”的参照不能混用。** PR116的`oracle_truth_GN`仅改变G/T的计算点，仍评价非线性估计误差；它不是直接求解的真值仿射模型。详见 [THEORY_AUDIT §1](THEORY_AUDIT.md)及[固定源码定位](notes/MODEL_AUDIT.md)。
2. **现有survey组不能验证非零集合内偏移。** 实际四维中心偏移约0.41677–0.45826 m，均在最大0.05 m球外；正确中心只有δ=0。有限集合内新面板与整个D的证明必须分开。
3. **降噪不是单因素的非线性干预。** 数据/固定先验相对权重、含噪积分初值和接受集合均随之改变；多终点组不是已穷尽物理分支，也没有概率权重。
4. **当前实现没有把精确H逆误用为随机协方差。** PR116用GGᵀ，但仍缺有限扰动余项与分支包含保证。当前toy按行数是74随机数据/25状态，不可简单称“低冗余”；实际删边后的有效秩才决定完好性方法能否使用。
5. **公开文献也须逐式核查。** Hafez等2020公开PDF式(35)与(36)/(39)的超限事件/CDF差不一致；Nicola–Jaulin作者稿§3的Hessian归一化与协方差措辞亦不可直接迁移。已记录原页与独立解析检查，不推断作者代码或未取得正式版的内容。

未发现足以宣告PR115/116原批次整体无效的实现错误。上述主要是会影响下一轮比较有效性的合同与解释风险，原报告中已有的正确限制没有被改写。

## 交付与阅读顺序

|文件|用途|
|---|---|
|[LITERATURE_MATRIX.md](LITERATURE_MATRIX.md)|5篇核心全文的模型、公式号、保证对象、冗余、迁移和最小验证；背景与全文限制|
|[THEORY_AUDIT.md](THEORY_AUDIT.md)|固定模型核对、Hessian/噪声/偏移区分、集合反演与SS独立推导、候选区域到PL的缺环|
|[METHOD_OPTIONS.md](METHOD_OPTIONS.md)|仅2条条件式优先路线、排序、准入条件和否证标准|
|[DECISION_TREE.md](DECISION_TREE.md)|针对A/B六类可能结果的排查—文献—最小验证—反证表|
|[REFERENCES.bib](REFERENCES.bib)|5篇核心与1篇已核书目背景；访问等级见矩阵，不编造DOI|
|[HANDOFF.md](HANDOFF.md)|检查结果、边界、待补资料与PR交接|
|[notes/](notes/)|固定模型、三组全文笔记、环境、独立审阅及访问留痕|

## 两条优先候选

**1. 非线性噪声置信集反演＋有证据外包。** 优先作为低维离线参照，保留全部分支；不要求估计误差Gaussian，但必须有可信噪声模型、独立偏移/状态域和全域包含计算。可能非常保守或计算不可用，不保证优于当前区域。

**2. 逐故障假设可辨识性审查＋solution separation。** 更直接连接HMI事件，但先验随机机制、候选族、删链后秩与选择后分布必须先成立。未知故障位置的管理不能由B2已知链路或B3真注入代替。没有资料时不填写最终风险概率。

现在均不实现；NBP仅作为多峰表示参照，不另列第三条优先路线。下一步由决策表选择一个机制和一个验证，不把多个修正同时拼起来。

## 固定Git来源与环境

- 原工作区：`/home/ubuntu22/双车协同/uwb-coop-localization-ros1`；分支`experiment/two-car-independent-integrity-bridge-20261023`，完整HEAD `115b17deb2f848e596d1638a0b45cf360deae947`，初始status干净，未改动。
- 独立开发目录：`/home/ubuntu22/uwb-midterm-integrity-literature-c`；分支`research/midterm-integrity-literature-c`，固定起点PR116 **`34f364d77c0964f22563bad6e5869567fe5f163c`**。
- PR115独立只读checkout：`/home/ubuntu22/uwb-integrity-lit-pr115-readonly`，HEAD **`b340f6bd05a97ac3f80ea4796d4c317114f508a8`**；未自行合并。
- 回溯PR111 **`704842930f78da60836c7cf56d7a4fdb71b4aa39`**、PR112 **`cc3861bf054f96f88c381eb07f6f89b81ebf2618`**，核对相关固定树调用链。
- remote：`https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git`。仓库固定树及祖先目录未发现适用`AGENTS.md`。PR115无独立MATH.md，数学内容读取其PROTOCOL和实现，不虚称读过不存在文件。

## 检索与复核限制

范围跨机器人固定窗、RAIM、区间/集合估计与传感器网络，不限UWB关键词。公式仅依据原发表全文或明确标识的作者稿；只取得摘要者降为背景。Nicola–Jaulin正式2020书章身份已核实，但精读的是17页作者稿，未取得付费最终版。O'Brien–Rife2009及Joerger等2014全文未取得。未核实原论文配套固定版本代码；Codac官方文档仅为未来入口，未安装运行。

原PDF仅临时阅读，未随PR分发。两处公开文本公式疑点已做图像与解析核查；没有确认作者勘误，不推断作者实验代码。本文不是穷尽的系统综述。所有后续“最小实验”仅为建议，无执行结果。

复核入口：`python3 verify_delivery.py`只做文件、固定Git来源与BibTeX结构检查；`notes/INDEPENDENT_REVIEW.md`记录代数/适用性人工复核。它们不调用定位器，也不为旧实验新增风险证明。

## 本轮PR目标

实查PR115与PR116均仍为OPEN、未合并。因此本轮普通PR以PR116来源分支 `research/midterm-bias-region-b` 为目标，保持审阅差异仅为本目录；不将PR116已有实验变动混作本轮新增。开发起点仍锁定上述完整SHA，没有自行合并或改写其历史。将来上游合并后的重定向由后续审阅流程决定，本轮不自动操作。
