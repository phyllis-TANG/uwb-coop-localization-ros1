# 运行前计划 v1
基线 PR81 fed9157008530663280aa2413ef708e345e678e3；计算核 74fa210e7cf6aa322eaebce19530510edb605d22。main a86a230b6f06c54e4a3a518417aed89a2a9af4b6 未包含 PR81；不合并其他 PR。
工作树 /home/ubuntu22/uwb-integrity-validation-20261030，分支 analysis/20261030-integrity-validation-v1，创建时 clean。未发现适用 AGENTS。当前进程命名空间不提供宿主进程全景；不操作其他进程。可用47GB，无独立挂载数据盘。使用已授权工作区RAM生成，不访问NAS。
负责目录仅 tools/integrity_validation_20261030 和 docs/research/integrity_validation_20261030。TMP/TEMP/TMPDIR 指向后者/tmp。新增产物总额100MB，单元前检查已用量与余量，预留10MB；完整审计只保留4101 nominal及5101三个主场景，其余仅紧凑分数/轨迹/声明。原输入只读，不保存raw流。
已读PR81 REPORT/FROZEN_SPEC/COMMANDS/ARTIFACTS/spec及测试；PR77 G3边界、PR78历史恢复HANDOFF、数据用途矩阵及PR76 HANDOFF。原核19文件导入时校验。原生G1同输入等价校验仅4101，测试覆盖历史排除/交叉相关/缺测秩亏/失败。
Python沿用 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python，numpy2.2.6 scipy1.15.3。G1/初始化/20秒窗/聚合/完整prior固定，监测不反馈。
完整单元见UNITS.csv：6正常校准+24主验证+条件允许40边界，总计70。四图/profile/时间帧不作独立重复。仓库代码及文档seed字段检索未发现4101–4106、5101–5108用途记录；结论限已查本地记录，101/211/307继续开发。验证必须在冻结提交后启动；首5101三场景完成先检查点。
B0 q=3；B1 network工程sigma=.2 alpha=.01。B2 alpha=.01，C乘scale²，候选.25/1/2，共用保存分数。仅正常可计算状态：两车各6次平均报警占用<=.05且每次<=.10，选择同时满足的最小共享尺度。若无候选，报告目标未满足并取原1作对照。校准不读误差/故障/AL；输出CALIBRATION.csv及FROZEN_VALIDATION.json并提交后才生成验证。
主对照B0、B1_network原尺度、B2_local尺度1和选定尺度；保存原全部分数供敏感性，不挑唯一赢家。
边界共同墙+.15/.60 [24,38)、+.30 [24,31)/[24,52)、+.30 [24,38)墙raw AR(1) rho=.7边际sigma=.04。rho是失配压力，不是实测估值。匹配seed不移动peer/Odom/初值抽样；AR从各墙原独立标准噪声作平稳递推，首样本保留原噪声；各墙独立。adapter逐标量检查仅登记项改变。
评价AL=.05/.10/.20仅假设；逐车HMI=XY误差>AL且available且未报警，另报越限未报警含unknown。所有63发布为主分母，另列共同可算。报告启动unknown、报警占用、可用/拒判、XY/yaw/相对误差、开销、报警提前延迟及删失。state与虚拟时间分开。恢复实际故障结束后10秒，late至64，混合bin/短尾不删；nominal相同索引配对。按seed汇总均值及范围，不推罕见风险。
实质错误：保留旧结果/失败记录，标记已暴露，不将修复同seed称未暴露验证。预算不足在单元边界停，不删旧结果。不临时扩seed/参数/组合故障。无改算法义务。
实测独立承接PR77 T02固定5–35/45–75/85–155/165–195/205–238.7543窗口；先查缓存/几何/时间/初值。缺B2输入明确列项，可先B1；无独立XY不算HMI/FAR/FNR/精度。留出T09/11/13/15不调参；T10仅恢复证据不改accepted。
PR82待主研究检查点后独立分支修复，不装Isaac、不下载原数据，真实SHA不可得明确空缺。
