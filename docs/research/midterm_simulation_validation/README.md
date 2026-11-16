# B端正式验证冻结候选

本轮formal_runs=0。仅修补失败处理、统一配置、冻结协议；人工失败与开发回归没有混入性能统计。FIX_REPORT说明证据，VALIDATION_PROTOCOL定义矩阵和统计，FREEZE_MANIFEST锁定内容，HANDOFF给A验收流程。

环境：Python3.10 / NumPy2.2.6 / SciPy1.15.3。本机可复用下列解释器，其他机器按CONFIG安装相同版本。所有命令从冻结checkout仓库根目录执行，输出目录必须在Git外且不存在。`checks.py`仅使用暴露开发seed26011601（配置变更检查另用已暴露26011602），不使用formal seeds。

A先验收（不会运行正式种子）：

```bash
PY=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python
$PY tools/midterm_simulation_validation/accept.py --out /home/ubuntu22/uwb-validation-A-acceptance
```

验收完成、另行决定进入正式验证后运行。必须将`FREEZE_SHA`设为本交付回执中的完整冻结HEAD，不用活动分支浮动HEAD或PR merge SHA：

```bash
FREEZE_SHA=<交付的40位完整HEAD>
OUT=/home/ubuntu22/uwb-validation-formal-frozen
$PY tools/midterm_simulation_validation/pipeline.py run --mode formal --frozen-commit "$FREEZE_SHA" --out "$OUT"
```

仅在同一冻结checkout和依赖下恢复；无需人工删除失败记录：

```bash
$PY tools/midterm_simulation_validation/pipeline.py resume --mode formal --frozen-commit "$FREEZE_SHA" --out "$OUT"
$PY tools/midterm_simulation_validation/pipeline.py summarize --out "$OUT" --save "$OUT/summary.json.gz"
$PY tools/midterm_simulation_validation/pipeline.py verify --out "$OUT" --save "$OUT/verification.json"
```

`--save`排他创建，已有汇总/检查文件拒绝覆盖；若要对恢复后结果重新汇总，使用新的派生文件名，例如summary-after-resume.json.gz。只读复核不指定`--save`时只输出stdout，无文件变更。run/resume拒绝正式条件过滤和非冻结配置；不会按结果切换协议。development模式供后续已授权回归，允许`--conditions c00`缩小检查，正式模式没有这种过滤。

完整状态保存在stages/<condition-seed>/<method>-P0/P1.json.gz；RUN.json有解析配置、SHA和计划。inputs包含共同观测、单独的离线truth/oracle及噪声。任何null必须按缺失处理。summary的rows保留两阶段及配对差，groups给全分母计数、有效配对数、均值和区间状态。人工fixtures目录与正式目录隔离，不能拼接。

只新增tools/midterm_simulation_validation/和docs/research/midterm_simulation_validation/。旧prototype仅只读导入目标函数，旧结果不变。本PR以PR101来源分支为base，不合并任何PR。
