# A端交接与执行清单

## 已完成

核心：固定树恢复/哈希核验，先提交分析协议，7200保存状态无优化器读回，三种矩阵、全部36条件四方法的位置/偏差覆盖，25未驻点保留，seed聚类统计，解析交叉验证，六张图，THEORY、REPORT、中期中文初稿及逐条证据映射。

附加：显式状态/白化/噪声/先验诊断接口；权重失配与时间相关理论；对应解析例；FAILURE_CASEBOOK；最多三个可否证的FUTURE_RESEARCH问题。均已完成。附加内容不是新的正式实验，不要求全部纳入中期报告。

固定起点完整SHA `fba539052f3ce2ed7d2ed35e79ac03198200c680`；分析前协议提交 `0788d4a86456bef37fac305e37e8495ec8f59a2a`。最终交付提交可由本分支 `git rev-parse HEAD` 查询，最终消息给出完整值；避免在同一提交内自引用其哈希。源配置与7个冻结求解/执行文件哈希保存在results/RECOVERY.json。执行时分析代码字节哈希在PROVENANCE，交付完整文件哈希在SHA256SUMS.json。

实际工作树 `/home/ubuntu22/uwb-midterm-uncertainty-a`，分支 `research/midterm-uncertainty-a`；独立环境及原始分析产物 `/home/ubuntu22/uwb-midterm-uncertainty-a-artifacts`。Git外保留run001、summary001、日志和完整终点谱；仓库精简证据约13MB（含9MB逐点NPZ），不提交venv和冗余中间数据。复现只需仓库中的原压缩输入、当前脚本与requirements，完整命令见README。

## 检查结果

恢复1800输入、7200方法，7175接受、25未驻点；未调用定位优化器，未新增定位seed。残差/J与原型144组合一致、保存代价/梯度一致，Schur边缘交叉误差约2.36e-12。三类位置区间在全部终点均可计算；真值参考32/288矩阵秩亏，明确分列。解析例、分母聚类和接口失效检查通过；独立交付读回复算41472覆盖行。源结果、冻结代码、实车配置没有修改。

## 仍未解决的研究问题

GN线性化在弱几何下的误差、固定先验偏移的非线性分解、真实噪声相关的可估计性和分支概率尚未独立验证。每条件仅50seed、数据已暴露；没有多重比较校正或全局校准保证。未找到可逐式对齐的师兄原文，不能称HCPL复现。

禁止把参考点区间不可用写成7200终点不可用，禁止把点态95%写成轨迹95%，禁止把先验中心变化的非单调效应概括为强先验总坏/总好。不更改原25条未驻点标签，也不以局部矩阵满秩声称结果可靠。

## 提交与恢复

仅新增 tools/midterm_uncertainty_a/ 和 docs/research/midterm_uncertainty_a/。普通PR base=main，不自动合并。若网络推送失败，保留本地提交，执行 `git push -u origin research/midterm-uncertainty-a`，再创建同名head、base=main、draft=false的PR；不要重跑定位，也不要改动或覆盖已有结果。
