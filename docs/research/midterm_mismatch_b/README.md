# B端扩展故障压力测试

先读PROTOCOL、CONFIG和SEED_REGISTRY。开发/冻结记录与结果报告分离；本批是在阅读既有结果后设计，不追溯预登记。结果完成后见REPORT、REPORT_DRAFT_ZH和HANDOFF。

独立checkout `/home/ubuntu22/uwb-midterm-mismatch-b`，venv与所有展开数据位于 `/home/ubuntu22/uwb-midterm-mismatch-b-artifacts`。固定依赖见requirements.txt；执行前设置：

```bash
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/ubuntu22/uwb-midterm-mismatch-b-artifacts/venv/bin/python
```

开发检查（仅已暴露seed，新目录）：

```bash
$PY tools/midterm_mismatch_b/checks.py --out /tmp/mismatch-dev-new
```

正式执行必须在冻结完整HEAD且工作区干净时使用。完成后复核不要再次求解：

```bash
$PY tools/midterm_mismatch_b/run.py --mode formal --freeze <完整冻结SHA> --out <新的Git外目录>
# 如中断，保持相同冻结checkout与依赖，仅补缺失阶段：
$PY tools/midterm_mismatch_b/run.py --mode formal --freeze <完整冻结SHA> --out <同目录> --resume
```

独立原始矩阵读回与统计，不调用优化器，输出拒绝覆盖：

```bash
$PY tools/midterm_mismatch_b/readback.py --run <原始目录> --out <新读回目录>
$PY tools/midterm_mismatch_b/analyze.py --results <读回目录> --out <新统计目录>
$PY tools/midterm_mismatch_b/plots.py --results <读回目录> --analysis <统计目录> --out <新图目录>
```

可携带EVIDENCE分片包含完整输入、注入、估计、两阶段状态/标量，省略可重建的r/J/协方差。Git外原始阶段与文件级SHA保留全部矩阵；只用Git内分片即可核对估计、误差、代价、梯度和接受状态，不重新生成观测/拟合：

```bash
$PY tools/midterm_mismatch_b/readback.py --evidence docs/research/midterm_mismatch_b/results --out /tmp/mismatch-portable-new.json
```

主统计使用全部有限P1估计，数值接受子集附列；null不可用不填零。未完成清单MISSING.json与实际分母一起保存。B3_full_oracle掌握完整逐测量偏差，非部署方法；B2依然只估一个预定候选常值。
