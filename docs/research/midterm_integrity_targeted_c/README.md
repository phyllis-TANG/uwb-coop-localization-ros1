# C端：面向可实现安全量化方法的定向文献核查

研究题目：*Safety Quantification for Multi-Agent Cooperative Localization in Lunar Exploration*。

交付日期：2026-11-17。**建议先实现低维非线性可行集的可信外包验收模块**，用仿射解析基准和二维镜像双解检验完整性，再决定是否扩展短轨迹。先补“区域有没有包含全部合法解”的证据；不以增加初值、粒子或Monte Carlo次数替代。

本轮精读4篇核心文献，分别覆盖SIVIA基础、短历史置信域、连续轨迹管和固定窗SS。指定Kuwada2026已核实正式发表，全文未取得，保持为最接近工作线索。可靠负面结论与访问限制分开记录，没有据此降低安全量化目标或预设创新成立。

## 固定起点与范围

|项目|记录|
|---|---|
|原工作区|`/home/ubuntu22/双车协同/uwb-coop-localization-ros1`；分支 `experiment/two-car-independent-integrity-bridge-20261023`；完整HEAD `115b17deb2f848e596d1638a0b45cf360deae947`；检查时clean|
|新工作区/分支|`/home/ubuntu22/uwb-midterm-integrity-targeted-c` / `research/midterm-integrity-targeted-c`；建分支时clean|
|实际main/开发基点|`b492c17d719013c31a93168994afe40beed5001f`，PR118合并提交；PR118审阅头为 `4e79199e1fbe3d38d3a21b864690634a2b35c3c1`。已读合并后的三个主文档，包含最终公式排版修订|
|PR119只读|`e35f94fb89a71236bd04c7f25fc318b016ba592d`；独立detached checkout `/home/ubuntu22/uwb-integrity-targeted-pr119-readonly`；未合并|
|remote|`origin https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git`（fetch/push）|
|AGENTS.md|检查原路径/新路径祖先及固定main仓库目录树，未发现适用文件|
|修改范围|仅新增 `docs/research/midterm_integrity_targeted_c/`；不改其他窗口、历史实验、定位器及中期正文|

没有运行定位求解、Monte Carlo、bootstrap、作者求解程序或新实验。读取保存CSV仅用于核对PR119结论。没有安装新定位依赖；版权全文均留临时目录，未提交到仓库。普通PR目标main，不自动合并。

## 阅读顺序与文件

1. [LITERATURE_MATRIX.md](LITERATURE_MATRIX.md)：证据质量与迁移适用性两轴矩阵，四篇核心逐项条件。
2. [CLOSEST_WORK_COMPARISON.md](CLOSEST_WORK_COMPARISON.md)：最接近工作差异，不预设创新。
3. [THEORY_AUDIT.md](THEORY_AUDIT.md)：时间相关/联合概率、q-relaxed、外包/超时不变量、固定偏移、tube积分和SS事件。
4. [METHOD_OPTIONS.md](METHOD_OPTIONS.md)：最多两条路线、顺序、成本、否证与条件分流。
5. [VALIDATION_PROTOCOL.md](VALIDATION_PROTOCOL.md)：未执行的仿射、二维多解、边界/空集/无界/超时验收方案。
6. [PR119_BRIDGE.md](PR119_BRIDGE.md)：几何改善回答了什么、仍缺什么，固定SHA行证据。
7. [SEARCH_LOG.md](SEARCH_LOG.md)、[REFERENCES.bib](REFERENCES.bib)：检索范围、版本与全文限制。
8. [HANDOFF.md](HANDOFF.md)：后续执行入口、检查结果与待补资料。

`notes/`保存三份精读笔记、访问/环境清单及独立审阅，不含版权全文。`verify_delivery.py`只检查交付格式、链接和Git范围，不调用实验代码。

## 影响下一步的关键发现

- Drevelle2013的历史盒二项式风险需要独立性；空间采样并非证明。跨时刻常偏差/共模误差不能套成独立离群。
- 可靠外包必须保留全部合法分支、未决盒及超时队列；有限域外可能存在的解也不能悄然删去。现代库的保证不能替代应用层合同。
- PR119中0.50 m改善不能消除0.10 m不利结果；局部秩/有限初值单组不是全局唯一解证书。主曲率视图与固定先验噪声传播视图不同。
- 本轮找到Hafez2020的作者代码及正确尾项，不能从公开PDF印刷疑式推断实现同错；精确复现版本与复用许可尚未确认。
- 从候选区域到保护级仍缺域/误差界依据、故障覆盖、任务事件和输出合同。本轮不设最终风险值，不声称PL/HCPL/HMI或月面验证已完成。
