# B端：先验误差与偏移传播

只新增本研究目录；原 PR109 输入和结果只读。真实精度证据见 EVIDENCE.md，公式见 MATH.md，预定矩阵见 PROTOCOL.md/CONFIG.json，开发独立差分与线性恒等式见 DEVELOPMENT_CHECKS.json。原始状态在 Git 外，精简证据将在 results/EVIDENCE.jsonl.gz 交付。

Python3.10.12、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9。先建立独立 venv 并安装这些依赖。所有命令在仓库根目录执行，输出目录必须不存在；`PY` 指向该 venv 的 Python。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PY=/path/to/venv/bin/python
$PY tools/midterm_prior_propagation_b/check.py --out /tmp/propagation-development.json
# 仅在完整冻结提交的独立 checkout 运行；FREEZE 使用交付HANDOFF所列完整值。
$PY tools/midterm_prior_propagation_b/run.py --freeze "$FREEZE" --out /path/outside/git/new-run
# 恢复只补未持久化阶段，失败结果也不重跑。
$PY tools/midterm_prior_propagation_b/run.py --freeze "$FREEZE" --out /path/outside/git/new-run --resume
$PY tools/midterm_prior_propagation_b/analyze.py --run /path/outside/git/new-run --out /path/outside/git/summary
# 交付后首选：只读精简归档验收，不调用优化器，不需要历史外部输出目录。
$PY tools/midterm_prior_propagation_b/analyze.py --archive docs/research/midterm_prior_propagation_b/results/EVIDENCE.jsonl.gz --out /tmp/propagation-independent
$PY tools/midterm_prior_propagation_b/figures.py --summary /tmp/propagation-independent/SUMMARY.csv --out /tmp/propagation-figures
```

所有 seed 均已暴露；本轮不是新的独立确认。960次新增方法运行与1,200对旧结果复用分别呈现，阶段数不增加样本量。不计算保护级或风险保证，不把假设误差范围称为实际平台可信界。
