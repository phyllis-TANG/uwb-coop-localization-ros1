# 夜间任务三：真实数据证据与中期汇报收束

状态：讨论材料完成；不是新算法/参考轨迹验收。本轮定位运行0、视频处理0、原始bag/MOV读取0；未启动或停止既有实车/ROS进程，未改系统/磁盘配置，未合并PR。

草稿PR：[#66](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/66)，分支已推送，未自动合并。
数值核对与格式修订交付提交为 `4776d6d8ed03501eb386180ac88d4dae734b114a`；后续仅补此链接及本包SHA。

## 基准与保护

原实际目录 `/home/ubuntu22/双车协同/uwb-coop-localization-ros1`，分支
`experiment/two-car-independent-integrity-bridge-20261023`，完整HEAD
`115b17deb2f848e596d1638a0b45cf360deae947`，开始检查工作区干净。

本任务worktree `/home/ubuntu22/uwb-evidence-midterm-20261028`，独立分支
`docs/20261028-evidence-midterm`；基准为本次远端读取的实际main
`7b67c66f2470d23f6c876f45b6543f72fab66391`，不是初始较旧origin/main缓存。
用户已核实main `74fa210e7cf6aa322eaebce19530510edb605d22` 是其祖先。

PR64固定head `d9eea02092511c6571fe1b06e5164ccb5007e1e7` 已合并为
`37ae826d3d5c56850d5248b30be46d1693f0cab1`；PR65固定head
`b2efc577e667c339a45741760e8c7623625f03bc` 已合并为当前读取main。
GitHub元数据和祖先校验见BASELINE.json；没有等待或自行合并，两个固定head均在读取基准内。

仅新增 `docs/research/paper_scope_20261028/evidence/`。未发现适用AGENTS.md。
既有ROS demo（含PID59092）和rosbag循环回放（PID61169）已存在约6天，保持原状；
没有把旧进程当本任务新运行。进程/磁盘快照在ENVIRONMENT.json：根盘约24GB可用，
三处挂载约513/197/90GB可用。本包只有小型文档/CSV/JSON和stdlib核对脚本，不复制图、
原视频/bag或解压归档；没有把Linux挂载猜成Windows I盘。标签为20261028，实际读取日期为UTC2026-10-27。

## 交付与结论

- CLAIM_EVIDENCE.csv：16条主张，区分实现、入图动作、性能/机制和参考边界；代码/配置/输入/产物SHA及能/不能支持和缺项。未知保留null。
- PR65_NUMERIC_CHECK.md及numeric_check/：仅从752条逐时刻紧凑表独立重算，736有效、16启动预测、40条冻结停点样本；最大原表差6.94e-18m。
- FIGURE_GUIDE.md / FIGURES.json：6幅既有图的来源、轴/单位、比较、结论及限制，SHA登记；全部只引用原图，不数值重绘、不拼时钟。
- CONFERENCE_OUTLINE.md：一项待查新/导师批准的“单车参照污染与历史残留机制审计”候选，不虚构正式创新或新方法。
- MIDTERM_OUTLINE.md：平台/数据、测距、固定窗口与IMU、双车合成、单车可靠性诊断、参考缺项及月面类比路线。
- SUPERVISOR_DECISION.md：已完成/建议/待决定分开，优先单车还是双车准入、创新类型、验证规模、参考档次/容差、题目/会议及实际截稿日均待导师决定。
- MINIMUM_COLLECTION.md：只为新主张补证据；A停点或B连续参考两档，不追认旧P/Q。DISCUSSION.md可直接作两分钟开场。

实包Q1→Q3人工末点差：004023 `.128488→.062804m`，005135 `.054857→.061176m`。
人工尺量/停车时态误差界未知，不能写成全程RMSE或总体收益；散布不是对真值误差，正常完成不是无故障。
PR62已有pseudo-Huber的双车传播，与PR63单车误归责是独立系统证据，尚非同一双车质量闭环因果验证。
PR64 continuous和checkpoints_only均not_accepted；不生成天线参考/插值轨迹，不以检测成功验精度。

## 实际阅读与独立性范围

按任务先读Outlook、PR61实际REPORT/METHODS、PR63 REPORT/导出修订、PR62 REPORT/历史就绪，
PR65 REPORT/FOUR_GROUPS/results与8冻结配置，PR64 README/MISSING_EVIDENCE/reference_validation。
另查数据manifest/QC、9月20日、10月10–11日及10月18日历史清单/原表，61份引用源文件在SOURCE_INDEX.json登记SHA与Git blob。

本机已有PR65 review/performance/controls三个归档，均重算整体字节SHA匹配；仅在内存打开八个性能run.json，
连接代码执行组合 `5e91a26851bf0ac9813388d505e32f2c86c3f808`、A源码
`12a1d94379b58c5a759b1698425fb90d48587609`、事件及冻结配置SHA。
八份完整source映射在numeric_check/run_manifests.json；合成96配置及PR62矩阵来源另列FROZEN_PROVENANCE.json。
没有提取归档、重读完整原图/影子/gyro日志，未重新逐486成员验算或重复原PR65的2208cost/1606消元；
这部分引用原native/portable回执，不能冒称本次再做了一遍数学验收。

PR63采用bias-null修订后的图/导出，原计算来源与修订来源分开；Q0/Q2缺bias不是0，真实0仍有效。
PR64实际阶段运行基于旧base加未提交源码，使用其run/source_lineage声明；不拿最终d9eea020
提交冒充每个早期阶段的执行源码。没有访问Windows原片确认本机可用，引用其已有I盘审计结论。

## 复核命令

在本worktree根目录，stdlib Python即可，不需运行算法或装依赖：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 docs/research/paper_scope_20261028/evidence/tools/recompute_pr65.py \
  --output docs/research/paper_scope_20261028/evidence/new_numeric_check
PYTHONDONTWRITEBYTECODE=1 python3 docs/research/paper_scope_20261028/evidence/tools/validate_package.py
git diff --check
```

数值脚本输出目录须新建；原本次结果在numeric_check/，不要原位覆盖。首次重算PASS；无估计器重跑。
SHA256SUMS.txt仅覆盖本包其余交付文件、不含自身；VALIDATION.json登记链接/来源/归属复核。

尚未完成且没有假装完成：导师决策、实际截稿日、文献查重、任何新补采/新参考验收、双车质量准入新实现。
建议先讨论决策单，是否继续由导师选择的主张决定，不默认启动补采、全视频或新定位矩阵。
