# B端：集合内固定偏移与候选区域验证

固定来源PR116 `34f364d77c0964f22563bad6e5869567fe5f163c`。只新增本研究目录，原代码/输入/结果只读。正式20条件×30新seed=600次B2方法运行，最多1200个P0/P1调用；600条同输入真值仿射直接解是oracle诊断，不增加随机样本量。

协议/配置/seed在正式生成前冻结。开发仅seed26011601的20条件/40次调用。恢复使用PR116 recovery.py，attempt无结果拒绝自动重跑，失败结果不可覆盖。详见PROTOCOL、MATH、REPORT、DECISION_MEMO和HANDOFF。

Python3.10.12、NumPy2.2.6、SciPy1.15.3；绘图Matplotlib3.10.9。所有命令在仓库根目录，PY指向独立venv，输出目录必须不存在。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PY=/path/to/venv/bin/python
# 假求解器/代数接入检查，无真实优化器调用
$PY tools/midterm_inset_validation_b/test_contract.py --out /tmp/inset-contract.json
# 已交付结果：首选无优化器读回
$PY tools/midterm_inset_validation_b/analyze.py \
  --archive docs/research/midterm_inset_validation_b/results/EVIDENCE.jsonl.gz --out /tmp/inset-readback
$PY tools/midterm_inset_validation_b/verify.py \
  --archive docs/research/midterm_inset_validation_b/results/EVIDENCE.jsonl.gz \
  --results /tmp/inset-readback --out /tmp/inset-verified.json
$PY tools/midterm_inset_validation_b/figures.py --summary /tmp/inset-readback/SUMMARY.csv --out /tmp/inset-figures
```

执行/恢复命令（只在完整冻结checkout且需要接续该批时使用，不为验收重复运行）：

```bash
$PY tools/midterm_inset_validation_b/run.py --mode formal --freeze "$FREEZE" --out /path/outside/git/formal
$PY tools/midterm_inset_validation_b/run.py --mode formal --freeze "$FREEZE" --out /path/outside/git/formal --resume
```

LINEAR/GN与LINEAR/exact为同一仿射目标的两种一致计算，不能把它们当独立方法重复。LOCAL_MATRICES按[unit,NL/LINEAR,GN/exact,t,car,2,2或4]保存P、B及GN曲率。原始ledger留Git外；可携带归档含输入、P0/P1身份/结果/完成凭证和线性直接解。所有rho和不可用原因均保留，六时刻全覆盖另列。
