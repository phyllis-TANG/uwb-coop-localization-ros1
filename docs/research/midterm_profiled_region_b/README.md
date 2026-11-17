# B端：偏差解析消元与非线性外包效率

从PR124固定低维模型解析消去第四测距的区间偏差，保留完整四维噪声事件。阅读MATH、PROTOCOL、IMPLEMENTATION_CONTRACT及两阶段报告。只做已知参考位置的单目标二维/三维原型，不扩展真正双车或25维模型。

核心标准库即可运行；输入/统计依赖NumPy2.2.6，图依赖Matplotlib3.10.8。所有命令在仓库根目录。输出需不存在，不为验收重跑已完成搜索。

```bash
export PY=/path/to/venv/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
$PY tools/midterm_profiled_region_b/tests.py
# 便携状态解包后，零搜索独立验收
$PY tools/midterm_profiled_region_b/readback.py --results /path/results/deterministic --out /tmp/det-check.json
$PY tools/midterm_profiled_region_b/readback.py --results /path/results/random --out /tmp/random-check.json
$PY tools/midterm_profiled_region_b/inventory.py --results /path/results/random --stage random --out /tmp/inventory.json
$PY tools/midterm_profiled_region_b/analyze.py --results /path/results --out /tmp/profiled-analysis
sha256sum -c docs/research/midterm_profiled_region_b/SHA256SUMS
```

首次冻结执行入口（本批交付后无需重跑）：

```bash
$PY tools/midterm_profiled_region_b/execute.py --stage deterministic --freeze FULL_SHA --out /git/external/results/deterministic
$PY tools/midterm_profiled_region_b/execute.py --stage random --freeze FULL_SHA --out /git/external/results/random
```

随机入口强制检查同冻结阶段二GATE。未决盒全部进入外包，失败不会被替换；硬中断用inventory核查，不自动重跑不确定attempt。协议和600个随机完整输入均先冻结；通过确定性门槛后自动继续，无追加种子或预算。
