# B端：固定偏移集合与随机波动候选区域

本轮formal_runs=0、真实优化器调用数=0。仅新增两个本研究目录，从PR111固定提交704842930f78da60836c7cf56d7a4fdb71b4aa39出发；不修改旧冻结代码、输入、报告或中期正文。

- MATH.md：灵敏度、噪声协方差、集合支持函数及保守外包圆证明。
- PROTOCOL.md / CONFIG.json：覆盖计算前冻结的分析选择。
- RECOVERY.md / recovery.py：后续运行可接入的保守恢复组件；旧入口保持不变。
- REPORT.md / DECISION_MEMO.md / HANDOFF.md：结果、局限、后续最小设计与交接。

Python3.10.12、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9。独立venv安装后，在仓库根目录执行；所有输出目录必须不存在。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PY=/path/to/venv/bin/python
$PY tools/midterm_bias_region_b/test_recovery.py --out /tmp/bias-region-recovery.json
$PY tools/midterm_bias_region_b/test_math.py --out /tmp/bias-region-math.json
# 只读复算旧状态，不调用优化器
$PY tools/midterm_bias_region_b/analyze.py --out /tmp/bias-region-recompute
$PY tools/midterm_bias_region_b/readback.py --results /tmp/bias-region-recompute --out /tmp/bias-region-verified.json
$PY tools/midterm_bias_region_b/figures.py --summary /tmp/bias-region-recompute/SUMMARY.csv --out /tmp/bias-region-figures
```

POINTS.csv.gz为逐时刻候选表；PER_SEED.csv.gz按每车每seed六时刻汇总，不能把多rho/方法当独立样本。SUMMARY含all/accepted/inside/outside四个视图及全计划分母；PAIRED_DIFFERENCES固定比较rho.01/.05相对noise_circle rho0。原曲率和噪声椭圆的radius字段是最大半轴，圆为半径，面积另列，不混称等面积半径。

LOCAL_MATRICES.npz按ENDPOINTS顺序保存P/B/curvature，维度分别为[终点,3视图,6时刻,2车辆,2,2或4]；state按25维填充，B0最后一维NaN。status是全局信息状态，逐边缘不可用原因见POINTS。压缩矩阵不是新的优化结果；原输入/状态依赖PR111仓库内便携归档，哈希冻结。

所有rho只是假设敏感性集合；当前survey偏移不默认属于5cm球。线性Gaussian结论不自动推广到非线性端点，不称保护级或安全保证。

审计入口readback.py只将NPZ一次性载入内存，再调用冻结verify.py的全部独立核验；避免循环反复解压。该交付期性能适配不改数学、候选选择或结果。完整逐点POINTS表保留Git外，按上述命令可从仓库固定源重建；Git内携带压缩逐seed表和全部局部矩阵。
