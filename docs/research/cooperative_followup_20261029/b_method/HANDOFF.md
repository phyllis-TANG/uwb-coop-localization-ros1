# B交接：可辨识性与候选机制必要性

**决定：必须先补可信信息。** 当前没有值得进入下一轮的候选；停止增加例子、种子与性能实验。
供10月29日讨论的一页结论见[B_DECISION.md](B_DECISION.md)，推导/四命题边界见[B_ANALYSIS.md](B_ANALYSIS.md)，
算法输入/假设/未知证据和具体实验室信息用途见[B_ASSUMPTIONS.json](B_ASSUMPTIONS.json)。
这不是“所有约束无用”的判断，也不是新算法贡献或真实精度通过。

## 实际基准与保护

- 原cwd `/home/ubuntu22/双车协同/uwb-coop-localization-ros1`；分支
  `experiment/two-car-independent-integrity-bridge-20261023`；完整HEAD
  `115b17deb2f848e596d1638a0b45cf360deae947`；初始git status干净。
- 读取实际远端main为 `0ef38e8b84dc88cb7b0e26fea595ac05c5162676`，包含PR71
  `aa6d272f9dcb7180d7548a06cb11d5d28445b2dd`，且PR72已合并；没有回退到PR71旧main。
  其后55个新增文件均属PR72原probe的tools/docs目录，不在本PR重复增加。
- PR72固定head仍按 `1cc7713a7e48776474788a07a1b41040f9df9330` 读取，执行源码仍为
  `312180ef51c6ea4ba394bc85618674ec36ff786d`。SOURCE_INDEX逐项验证所读PR72文档/表与固定head字节一致，
  原core.py也与其执行提交一致；合并状态不提升科学结论。
- 本worktree `/home/ubuntu22/uwb-cooperative-b-method-20261029`，分支
  `research/20261029-b-method-identifiability`。仅新增两个专属b_method目录，不改根HANDOFF、
  算法/几何/原报告/原数据/其他窗口或PR67/70/72，未reset/clean/自行合并。
- 祖先与目标路径未发现适用AGENTS.md。既有ROS demo PID59092、rosbag loop PID61169及其他Codex任务保持原状。
  根盘约19GB空余、数据挂载约513/197/90GB空余，快照见ENVIRONMENT.json。没有新归档/视频/bag/缓存或大型环境；
  仅少量文本/JSON/stdlib代码，没有猜测Windows I盘到Linux的映射或改磁盘配置。

## 已完整阅读与本轮动作的层级

1. 完整阅读PR71路线README、PHASE0_ANALYSIS，另读其解析程序；完整阅读PR72 REPORT/METHODS/FROZEN_CONFIG/HANDOFF。
   输入文档中的未来采集/扩展指令不作为额外授权；未启动这些工作。
2. **自己实际重算：** 预登记两个一维解释，同一在线量(0.30,1.00)m及正确peer=1m，准确局部源相反。
   精确有理数检查10类性质：观测身份、误差支持、平移增量不变、J梯度/H正定、KKT、C=K、实际位置预算等。
   不依赖健康标签作输出决策；C/K在A/B各有(.26,.04)/(.04,.26)m绝对误差，4cm是影响不是绝对精度。
3. **仅核对汇总：** Decimal对PR72原metrics四行求K−C，故障窗−.578934/−.105053mm，
   恢复Car1−.078008mm、Car2+1.001213mm；分母14/10且两个scope一致。
   成本读8行原表，不将旧J/I历史耗时与派生裁剪拼成同期速度比。没有从原轨迹重算RMSE。
4. **引用原报告：** 私有参照/完整prior/逐发布预算与原14+27+7测试及完整归档回读由PR72提供，
   本B没有重验它们、没有读取54MB大归档或原始实包。并未把本次数学PASS称作真实定位精度通过。
5. **新建议：** 先明确同状态独立天线点/有效误差界、运动传播有效期、安装/时钟/peer适用界，
   或明确裁剪不能满足的实际额外合同；届时候选和廉价对照须拥有同一信息与允许损害。未提出新权重/FSM/算法名。

共同偏差只在符号边界分析中讨论，不伪装成B2“至多一源有偏”模型内的第三个数值例。
若可信初值/健康绝对观测已打破歧义，或理想无冲突/单偏差模型可辨识，必须承认该限定情况；
不得把代理模型升级为原始四锚所有几何不可能定理。B4候选试验未开启，二维配置0、新seed0、FGO/IMU/实车0。

## 冻结、命令与检查

预登记提交 `d5aa03d`；实际本B执行源码 `bb99db00e798bdf0d3e0e65dced0588ede3811d1`。
results/run.json中dirty=true是写结果后查询Git导致结果文件未追踪，源代码已提交且SHA未改；
不能把后续讨论文档提交冒充计算源码。配置、脚本、预登记及输入表SHA在run.json，原文来源SHA在SOURCE_INDEX.json。

实际命令（仓库根目录，stdlib Python；勿覆盖已有results）：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/cooperative_followup_20261029/b_method/analyze.py \
  --output docs/research/cooperative_followup_20261029/b_method/results
PYTHONDONTWRITEBYTECODE=1 python3 tools/cooperative_followup_20261029/b_method/verify.py
git diff --check
```

实际结果为results/exact_worlds.json、pr72_compact_check.json和run.json。只计算一次在线输出，两个解释均完整保留，
没有搜索或按结果增删配置。CHECKS.json为只读SHA/归属/结果一致性检查；SHA256SUMS.txt覆盖本包其余文件，不递归含自身。
算法输入/假设中尚无证据的量保持null；没有以小协方差、收敛或静态重复性补造可信证书。

剩余事项只属后续决定：是否能取得能排除一种角色解释的可信信息；若实际要求仅对等影响预算，裁剪已满足，
新增机制还需独立的实际必要性。没有据此批准更多路线/预算/新矩阵；本次可提前结束。
