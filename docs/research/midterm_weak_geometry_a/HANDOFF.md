# A端交接

已完成完整矩阵与读回，未合并任何PR。起点c51411433d30dc379bd69cf5fb20a11e196b7182，补充只读41ba0d3a6e69897ef6330cc9ad218253c7fb80ea。本任务代码/文档仅在tools与docs下midterm_weak_geometry_a目录，未改公共后端、原配置、原结果或论文。

已完成：先冻结协议和30seed清单；81源哈希核验；240保存输入提取；12开发配置冒烟；2880新增初始化配置（5760调用）；720原配置仅读回；全部3600候选的误差/曲率/覆盖/分组；seed配对统计；48个预定Hessian和2424剖面点；图与报告。原、新、开发三个计数不混用。运行源码完整HEAD与协议提交完整HEAD分别在results/START.json、SOURCE_CHECKS.json。

验收应运行README的无优化读回命令。保留的INPUTS和ENDPOINTS为便携精简证据，不依赖本机路径。所有候选最终有限，全部总信息满秩；8个未驻点未删除。主统计包括有限原终点；多初值选择本身按用户要求限制接受候选，均有候选。条件化稳定子集不得当作全计划性能。

原始阶段含r/J保存在Git外约88MB；仅删除这一Git外副本也不会影响复核。源SHA哈希、文件哈希、solver输入哈希和初始化数组可联结。阶段attempt文件是调用前记录，已完成stage不重复执行；存在attempt却无stage时程序拒绝自动重跑，需明确说明中断是否已进入优化器，不能悄悄重算抹去暴露。

汇总脚本在不改变协议、输入、估计或分组的情况下补充了valid_rate_ci字段，区别“全计划有效且覆盖的比例区间”和“有效子集覆盖率区间”。首次统计表保存在Git外，最终表才随PR交付。该改进不涉及定位重跑；小于20个有效seed的条件区间明确不足。bootstrap只抽seed。

剩余研究问题而非未交付工作：30个已暴露seed不能确证总体欠覆盖；有限初始化不能排除未发现终点；近代价分离不能证明局部极小；组内条件化无法完全区分非线性、选择效应与固定先验偏移。下一步最小必要实验见DECISION_MEMO，尚未执行、不预设成功。

恢复与推送：本地工作树为/home/ubuntu22/uwb-midterm-weak-geometry-a；分支research/midterm-weak-geometry-diagnosis-a。若网络推送失败，先运行git status确认本提交，再执行git push -u origin research/midterm-weak-geometry-diagnosis-a；创建普通PR，base=main，不自动合并。main已包含固定起点，PR只应含两个新增目录。
