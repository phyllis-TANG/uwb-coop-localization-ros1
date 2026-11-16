# A端正式仿真交付

先读REPORT.md，交接见HANDOFF.md；开跑前验收见../midterm_validation_acceptance/REPORT.md。本次仅新增两个交付目录，不改B冻结源码、配置或公共后端。

冻结来源：PR102 `6317e977572b4e8fb8282211485356562ddc62d2`。先行验收提交：`8e9850fbbedd73116b93273a98b700b6d91eb077`。正式执行checkout `/home/ubuntu22/uwb-s2-confirmation-frozen-execution` 保持该B完整HEAD；交付分支 `research/midterm-s2-confirmation` 位于 `/home/ubuntu22/uwb-midterm-s2-confirmation`。两者工作文件/索引独立，共享Git对象，不合并任何PR。

结果：7200方法、1800配对单元、14400阶段全部完成，缺失0、有限7200、数值接受7175、未驻点25。独立n=50；P0/P1不是独立重复。正式起止UTC、依赖/来源/配置/计划见EXECUTION_MANIFEST、results/RUN.json与验收目录。全部正式seed现在已暴露，后续重复只能称回放，不能称新的未暴露确认。

## 必要证据

- `results/PER_RUN.csv`：7200逐次方法行，逐车MSE/RMSE、D、B2−B1、双方接受子集、P0/P1分类和终点梯度。空字段表示不可用，不是0；本批所有主误差有效，接受子集会为空。
- `results/SUMMARY.csv` / `GROUPS.json`：144组、1332项指标摘要，完整计划分母、有效seed数、均值和95%逐项配对区间。逐seed RMSE均值不等于sqrt(平均MSE)。
- `results/FAILURES.csv` / `NONACCEPTED.csv`：全分母失败表与25条未驻点明细。逐车超阈值在PER_RUN、GROUPS中，联合误差另列，不能混淆。
- `results/PRIOR_CONTRASTS.csv`：同seed先验条件配对差，使用冻结bootstrap的补充描述性分析，非新增预登记主端点。
- `results/ESTIMATES.jsonl.gz`：约7.5MB可携带证据，含完整RUN、1800输入（观测/噪声/初值/先验/truth/oracle）及7200方法的两个阶段估计、标量诊断和原状态。truth只生成/离线评价，oracle仅B3。
- `results/INDEPENDENT_CHECKS.json`、`frozen-verification.json`、`summary-crosscheck.json`、`PORTABLE_CHECKS.json`：A独立全状态读回、B冻结复核、两端统计比对、轻量压缩证据独立重算；都不调用优化器。
- `results/EVENTS.jsonl.gz`、`EXECUTION.log`：正式启动/完成事件与单次命令输出；无中断或重试，每阶段attempt=1。
- `results/RAW_FILE_HASHES.json.gz`：Git外16203个原文件逐文件SHA及大小。`EXTERNAL_INDEX.json`列出完整原目录、含r/J/梯度的22MB审计证据、95MB冻结完整汇总的SHA。约177MB原始阶段目录不提交Git。
- `figures/position_gains.png`、`bias_errors.png`、`prior_sensitivity.png`：逐车收益、偏差分布、先验敏感性；包含所有有限最终估计和不显著/负面结果。
- `SHA256SUMS.json`：本目录所有交付文件的字节SHA（不含自身）。

轻量证据省略可由冻结数学实现重建的残差/Jacobian/完整协方差和谱；原始完整文件在Git外保留，并有SHA索引。原始r/J/梯度逐项比对已在INDEPENDENT_CHECKS中完成。仅靠轻量包可再次核对估计、误差、代价、梯度范数与接受分类，不冒充含全部原矩阵的归档。

## 实际命令与无求解器复核

所有求解与复核使用Python3.10.12、NumPy2.2.6、SciPy1.15.3；画图另用Matplotlib3.10.9，BLAS线程1、清空PYTHONPATH。输出均排他创建，不覆盖旧结果。

以下正式命令**已经执行完成，不要为复核再次运行**：

```bash
cd /home/ubuntu22/uwb-s2-confirmation-frozen-execution
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
UWB_PY=/home/ubuntu22/uwb-midterm-s1b-artifacts-20261116/venv/bin/python
RUN=/home/ubuntu22/uwb-s2-confirmation-artifacts/formal-frozen
"$UWB_PY" tools/midterm_simulation_validation/pipeline.py run --mode formal \
 --frozen-commit 6317e977572b4e8fb8282211485356562ddc62d2 --out "$RUN"
"$UWB_PY" tools/midterm_simulation_validation/pipeline.py summarize --out "$RUN" \
 --save /home/ubuntu22/uwb-s2-confirmation-artifacts/frozen-summary.json.gz
"$UWB_PY" tools/midterm_simulation_validation/pipeline.py verify --out "$RUN" \
 --save /home/ubuntu22/uwb-s2-confirmation-artifacts/frozen-verification.json
```

首条stdout/stderr实际保存为Git外formal-execution.log，其原字节副本为results/EXECUTION.log。运行无中断，因此没有执行正式resume。恢复能力已在开发fixture实际验证，不能为了演示恢复重跑正式阶段。

默认复核使用仓库轻量证据，无需外部原目录、无需生成或拟合（输出用新路径）：

```bash
cd /home/ubuntu22/uwb-midterm-s2-confirmation
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
UWB_PY=/home/ubuntu22/uwb-midterm-s1b-artifacts-20261116/venv/bin/python
"$UWB_PY" docs/research/midterm_simulation_confirmation/verify_portable.py \
 --evidence docs/research/midterm_simulation_confirmation/results/ESTIMATES.jsonl.gz \
 --out /tmp/uwb-confirmation-portable-check-new.json
```

有原始目录时可重建所有独立统计（只读，不求解）；这也是本轮实际使用的入口，复核时换新的输出路径：

```bash
"$UWB_PY" docs/research/midterm_simulation_confirmation/readback.py \
 --run /home/ubuntu22/uwb-s2-confirmation-artifacts/formal-frozen \
 --out /tmp/uwb-confirmation-readback-new
"$UWB_PY" docs/research/midterm_simulation_confirmation/compare_summary.py \
 --frozen-summary /home/ubuntu22/uwb-s2-confirmation-artifacts/frozen-summary.json.gz \
 --independent /tmp/uwb-confirmation-readback-new --out /tmp/uwb-confirmation-crosscheck-new.json
"$UWB_PY" docs/research/midterm_simulation_confirmation/plot_results.py \
 --results /tmp/uwb-confirmation-readback-new --out /tmp/uwb-confirmation-figures-new
```

本轮readback实际输出Git外independent-results；compare_summary输出summary-crosscheck.json；plot_results输出figures。pack_evidence.py从原EVIDENCE生成轻量包与原始文件SHA，verify_portable.py验证后才复制入仓库。正式源码没有因看到结果改变，新增代码只负责独立审查、统计和画图。
