# B端：低维非线性测距置信集反演

固定起点 f9c27436836b814afdea47945887015dcb55fca5。仅二维位置及三维(x,y,b)，固定八个确定性机制案例，不运行25维模型或覆盖率Monte Carlo。用完整测量噪声事件反演；Decimal定向舍入、整数平方根及独立有理数读回构成可解释的条件性外包原型。

阅读顺序：SOURCES → MATH → PROTOCOL/CONFIG/INPUTS → RESULTS → REPORT → DECISION_MEMO → HANDOFF。未知测距偏差b不是先验中心偏移δc。搜索域与偏差域是仿真假设，不是实车标定误差界。

Python3.10.12；核心只用标准库。绘图使用NumPy2.2.6、Matplotlib3.10.8。独立venv可使用 `python3 -m venv --without-pip --system-site-packages /path/to/venv`，绘图依赖需已可用；保证核验无需NumPy或Matplotlib。

在仓库根目录执行，输出文件/目录不得已存在：

```bash
export PY=/path/to/venv/bin/python
$PY tools/midterm_nonlinear_region_b/tests.py
# 只读检查已保存树、证书和投影，不重复搜索/优化
$PY tools/midterm_nonlinear_region_b/check.py \
  --results docs/research/midterm_nonlinear_region_b/results \
  --out /tmp/nonlinear-region-readback.json
# 只读重绘及一次局部仿射直接解对照；不调用优化器
OPENBLAS_NUM_THREADS=1 $PY tools/midterm_nonlinear_region_b/plot.py \
  --results docs/research/midterm_nonlinear_region_b/results \
  --out /tmp/nonlinear-region-plots
sha256sum -c docs/research/midterm_nonlinear_region_b/SHA256SUMS
```

运行命令仅用于冻结版本的首次执行，本批交付后无需重跑：

```bash
$PY tools/midterm_nonlinear_region_b/run.py --freeze FULL_FREEZE_SHA --out /git/external/results
```

运行器要求HEAD等于冻结SHA、冻结文件哈希一致，独占锁及调用前attempt防止覆盖或自动重跑不确定状态。stage1通过后才执行stage2；预算中止保留所有队列。归档中的每个案例包含完整树、叶状态、输入、评价真值及精确有理数面积/半径；图只是显示，不是保证依据。
