# P-A0现状与缺口（本次实际main b23188d）

|项目|状态|代码/配置|输入及结果|边界或待核对|
|---|---|---|---|---|
|可访问IV相关稿|已有但待核对|docs/research/conference_paper_v003_20261101/{PAPER_OUTLINE,MODEL_AND_CALCULATIONS}.md|docs/research/paper_evidence_completion_20261103/incoming/Outline_readable.txt（11月3日大纲，IV Conditional Analysis）|仓库没有完整当前投稿Word/TeX；不能认定外部最新IV稿与此完全相同，不修改稿件|
|D/C/T定义|已有且可复现|MODEL_AND_CALCULATIONS §4；paper_evidence_completion/verify_bundle.py|field_readback/static_pair_rows及FIELD_PER_RECORD|D=协同MSE−独立MSE，C=historical−raw，T=G2−G1；负D为收益，不能与RMSE差混用|
|历史S1|已有但待核对|大纲证据索引S1；早期ROS接口模拟|2历史模拟bag清单，未重新解码|接口证据，不作当前主性能证据|
|历史S2|已有且入口可用，旧全矩阵未重跑|tools/two_car_fixed_lag_fgo_v1/{simulate,frontend,graph}.py、config.json|历史24方法单元/3seed，旧6维状态|不同于本批PR88/91含IMU后端；不复制旧编号|
|现有较新仿真|已有且可复现|tools/two_car_sim_dev_20261101/{generate,adapter}.py；tools/two_car_mechanism_20261101/PROTOCOL.json|PR91 development/PER_SEED.csv，本轮BASELINE_SIMULATION|seed7静动nominal96秒M2/M3复现，无参数调整；原Python3.12.14与本机3.10.12差异已记录|
|独立/协同动态实现|已有且可复现|tools/two_car_imu_fgo/{core,frontend}.py；configuration.py及逐run config|M2禁peer；M3完整peer；M3W025固定代价.25|每车XY/yaw/gyro bias共8维；融合墙UWB、单方向peer、wheel Odom、gyro。不是加速度/磁力计全IMU融合|
|静态I/J与固定校准|已有且数值可复现|paper_evidence_completion/static/confirmation_adapter.py；runs/*/{raw,historical}/config.json|10包20profile轨迹、combined_results.json|I无peer/J完整/W025固定缩权；无新增gyro因子；historical用既定Car2系数，不重新拟合、不视为真实全链健康|
|静态有效窗/参考|已有且可复现|各run summary.phase_windows_s、reference|field_readback/static_common_times；160配对行|共同accepted交集，同一记录内窗口不独立。主五包n=2+3，全部正常10包n=4+6|
|动态停点参考|已有且可复现|dynamic/runs configs、references及原评价脚本|5文件单元/15方法轨迹/32停点车条目|A1/B1开发，A2/B2原冻结后已暴露；B2中断前后分开，不把停靠点当连续真值|
|原始实测数据|已有但本批不重解码|原catalog/manifest与SOURCE_MANIFEST列Windows原路径；本机既有T02缓存可读|本批实际计算只用当前Git保存导出轨迹/参考/配置|不宣称全部116条原件已核对；新11月数据的原Windows路径并非当前云端可直接读；不需原bag阻塞读表|
|统计bootstrap|尚未定位独立的记录级统计bootstrap结果|源码bootstrap主要为前5秒初始化，不是统计重采样|已查大纲与随包脚本|本批用留一与seed级t区间；不把初始化bootstrap误称稳健性bootstrap|
|留一记录|本批完成|field_analysis.py、supplement.py|FIELD_LEAVE_ONE_RECORD及ALL10版本|主五包与扩大10正常包分开；不将同包窗口作为额外record|
|窗口敏感性/误差分解|已有且本批独立读回|verify_bundle.py；static_scope_20_readback|20条五scope结果；模型文档§5分解|不重复择新窗、不把事后范围改写成确认实验|
|参考点扰动|已有条件敏感性|原shared reference精确包络公式|每轴±2cm估计，球半径sqrt(2)*.02|不是校准置信区间，本批不新增无依据扰动|
|来源字节身份|部分完成|SOURCE_MANIFEST、FIELD_IDENTITY_CHECK、FIELD_RECONSTRUCTION|139/141可严格匹配（含CRLF重建）；两历史setup说明未匹配|原失败保留；数值所需轨迹/配置/参考均通过，仍不可称全包来源完备|
|P-S0单链扫描与确认|本批完成|propagation.py、PLAN、FROZEN|S0_PER_RUN/SUMMARY、三张布局/误差/收益图|开发两布局全部幅值，确认限G2主场景50seed；不泛化为两布局全部扫描已确认|
|P-S1偏差可估计性|本批完成诊断|identifiability.py|S1_INFORMATION/S1_INITIALIZATION/CHECKS|25维简化XY+单偏差；无噪声拟合/局部秩，不是完整8维gyro固定窗增广|
|完整保护级/P-S2方法优势|尚未完成且本批不要求|无新在线策略|不修改论文结论|可进入限定诊断原型的预登记；全后端对照仍需明确信息合同|
