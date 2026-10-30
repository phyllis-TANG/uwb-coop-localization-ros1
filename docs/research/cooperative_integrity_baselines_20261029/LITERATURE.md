# 文献依据与实际阅读边界

PR67固定HEAD `71e31e61d6a49e0f738c37b5c909e43a89a282d2`：本轮读取literature的READING_LOG、BASELINES、PAPERS相关P1及COMPARISON记录，不修改/搬入旧目录。PR67曾全文阅读不等于本轮取得原文。

|文献|本轮实际范围|与本轮接口的关系|
|---|---|---|
|Hafez等，RA-L 2020，DOI [10.1109/LRA.2020.2975769](https://doi.org/10.1109/LRA.2020.2975769)|NSF指定全文入口[10203881](https://par.nsf.gov/servlets/purl/10203881)两次502；核对官方IEEE元数据/摘要及PR67的固定全文笔记，未声称本轮重新阅读全文|PR67定位§II-B Eq.(5)、§III (11–13)、§IV-A (17–19)、§V-A (33)、Algorithm 1；包含fixed-lag SS、prior故障、相关解分离与风险/可用性。独立排除历史和共享噪声差分是构件适配；本轮2D统计、三源组和工程噪声并非完整原风险方法复现|
|Arana等，IJRR 2020，DOI [10.1177/0278364920960517](https://journals.sagepub.com/doi/10.1177/0278364920960517)|官方HTML可读，本轮选读§1、§2.1/2.4、§4.1–4.4；非逐页全部附录重证|时间窗前故障进入prior偏差；序列创新检测的分布/阈值需要相应高斯、独立性与已知协方差条件。本轮没有这些标定，不能把鲁棒后验残差套成标称卡方|
|Xiong/Cheong/Dempster/Xiong，PLANS 2020，DOI [10.1109/PLANS46316.2020.9109996](https://doi.org/10.1109/PLANS46316.2020.9109996)|[ION官方完整摘要及出版元数据](https://www.ion.org/publications/abstract.cfm?articleID=17389)；全文需download credit，未取得/未绕过|摘要明确CIM、去中心KF、共同/特有源分解和全局/局部创新，来源分解与逐车监测已有先例；未从摘要虚构具体公式或完整复现|

本轮按公开数学构件独立实现，未复制作者MATLAB。PR67已记录Hafez公开代码未核实许可，故不移植作者代码。原文全文缺口不阻塞本轮工程SS构件、已知模型数值检查与开发对照；阻止声称原文风险保证已复现。实现差异、近似与未监测故障见FROZEN_SPEC，不将SS、source grouping、prior或鲁棒核视为创新。
