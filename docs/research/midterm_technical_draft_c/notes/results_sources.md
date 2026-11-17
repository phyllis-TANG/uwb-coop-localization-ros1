# 第4–5章来源键与核验记录

这些是技术初稿的内部来源简称，不是新增外部参考文献。源文件路径相对仓库根；CSV行号从表头为第1行计，压缩CSV指解压后的逻辑行。所有正文结果仅摘录保存结果；本窗口没有调用定位求解器。

## 固定来源

|简称|固定完整提交|根目录与身份|
|---|---|---|
|R0|`5f5d77d49ba54299a70a948a0dc404b6608e7207`|`docs/research/midterm_simulation_confirmation/`，P-S2正式确认；git log显示REPORT在该提交交付|
|R106|`d39c99589bd15938484d64871981d45a9dd74efe`|`docs/research/midterm_uncertainty_a/`，PR106已审查头|
|R107F|`afafabbd2b7f8f25fe38ba99f539dab8baf2491c`|`docs/research/midterm_mismatch_b/`，PR107故障批次|
|R107N|`afafabbd2b7f8f25fe38ba99f539dab8baf2491c`|R107F下`noise_exploration/`，同PR独立后续噪声批次|
|R108|`41ba0d3a6e69897ef6330cc9ad218253c7fb80ea`|`docs/research/midterm_joint_coverage_a/`，通过独立只读checkout读取；非从主线假设恢复|
|R109|`c51411433d30dc379bd69cf5fb20a11e196b7182`|`docs/research/midterm_prior_mechanism_b/`，开发固定起点|

正文共同背景：P-S1来源`docs/research/midterm_simulation_phase1/REPORT.md`，最后修改提交`df323eccdffd375a2fb255ebbfd734b6c2be4aac`；P-S1b来源`docs/research/midterm_simulation_s1b/REPORT.md`，最后修改提交`eac874af58e949b9bb06eb97e3d2443ea99fe4cd`。这些目录在R109固定checkout可读。它们与原研究大纲的历史S1/S2不是相同命名层次。

## 表与主要数值锚点

|正文对象|文件与定位|核验/限制|
|---|---|---|
|表4-1及失败分类|R0 REPORT开头及“数值、误差与分母”；R106 REPORT 5–11行；R107F REPORT 3–18行；R107N REPORT 3–10行；R108 REPORT“来源”；R109 REPORT 7–23行|核对36/72条件、50/100seed；方法数不同于阶段数；R106/R108不新增定位，R109线性不新增seed|
|表4-2原基线|R0 REPORT“已知受影响链路下”表；SUMMARY完整表|逐seed RMSE均值而非sqrt(mean MSE)，50seed、peer+.3、survey sigma .5|
|原曲率覆盖|R106 REPORT 19–31行；COVERAGE.csv.gz，id=c03/c11/c31, method=B2, view=total_curvature, level=.95|每格300相关点、独立50seed；强先验轨迹0/50不作概率0|
|表4-3故障|R108 `figures/fault/DESCRIPTIVE.csv`：constant行26/32；multi_link74/80；ramp122/128；step170/176；wrong_link218/224；zero266/272|已直接解析CSV核对双车mean/min/max，按百分数保留两位；每类12条件的描述均值，不跨条件CI|
|表4-4噪声|R108 `figures/noise/DESCRIPTIVE.csv`：AR行28/30/34/36；iid004行76/78/82/84；iid008行124/126/130/132|已直接解析CSV，B_iid/C_true_noise、B2/.95双车核对；每类24条件、独立n=50|
|n32剩余欠覆盖|R108 `results/noise/summary/COVERAGE.csv.gz`：50178/50179行为车1点平均/全时刻；50242/50243为车2|核对车1点221/300、CI[.613333,.846667]；轨迹34/50与43/50；不解释为轨迹名义95%|
|m28/n32均值波动分解|R108 `results/fault/summary/MOMENTS.csv.gz` 与 noise对应文件；筛选m28/n32、B2、car1、C_true_noise，六时刻均值|REPORT §1/§4给出正文四舍五入；MSE中empirical_trace使用ddof=1，需要(n−1)/n系数|
|表4-5六组先验|R109 `results/SUMMARY.csv`：p18–p23/B2/nonlinear与truth_linearized，行150/151、158/159、166/167、174/175、182/183、190/191|已直接解析保存CSV核对全部车1MSE，不重新求解|
|表4-5覆盖|R109 `results/COVERAGE.csv`：p18–p23、B2、curvature、level=.95、subset=all、aggregation=point_average、car1/car2|车1行28418/28610、29954/30146、31490/31682、33026/33218、34562/34754、36098/36290；双车数值同时对照REPORT表|
|强survey差异|R109 `results/PAIRED_COMPARISONS.csv`，行4230：comparison=survey_minus_correct，base_id=p21/other_id=p22、B2、car1、nonlinear、metric=MSE；REPORT §2|0.047673和[.045531,.049913]m²为同seed差；报告97.5%来自MOMENTS均值项，不是随机解释比例|
|正确中心剩余缺口|R109 COVERAGE行28418：p18/B2/nonlinear/car1，544/600，CI[.86,.946667]；REPORT §3|98接受seed子集仍欠覆盖，但不能宣称全局最优|
|6400奇异块|R109 REPORT 21行附近；PROTOCOL“二维边缘”与HANDOFF计数|691200块含两种模型、两个视图；固定中心weak线性t0机制传播奇异；不等于总信息秩亏|

## 图形检查

- 图4-1 `figures/noise_explanations.png`：原样复制R108图，已查看实际图像。图标题明确每噪声24条件、每条件50seed/300点、无pooled CI；子图标题中的“+”“x”分别为未驻点与预算耗尽存在标记。
- 图4-2 `figures/prior_linear_nonlinear_full_range.png`：原样复制R109图，已查看实际图像；脚本`tools/midterm_prior_mechanism_b/plot_full_range.py:21`设置xscale、yscale均为log，范围自动容纳全部数据。保留超过1m²的线性极端点，不沿用开发图的1m²截断。
- 完整覆盖图4-3a/4-3b由FIGURE_TABLE_INDEX索引；正文未截取热图局部以突出有利方法。
- 图片是原字节复制，因此无需新绘图数值一致性流程；原始脚本、源表与复制SHA见图表索引和`evidence/SOURCE_COPIES.json`。

## 第5章计划与证据的分界

A-NL/B-PRIOR只是插入接口和后续验收要求，未写入已完成运行、结果或保护级结论。新诊断应独立登记固定提交及是否增加新观测/优化调用。师兄原始方案状态由主证据目录统一记录；本章未提供任何无原文支持的HCPL公式、风险分配、作者或DOI。
