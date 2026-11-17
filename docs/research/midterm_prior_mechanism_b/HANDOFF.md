# B端交接与独立验收

起点 `764064f224ada7e793430bd47f5122a14b8d1f30`；观测生成前冻结 `5223d08ed219bafeb092df6f598b842308dee33e`。交付HEAD见PR及git rev-parse HEAD，避免文件自引用。只新增本任务的两个目录，原结果、公共后端及冻结源码均只读。

工作区 `/home/ubuntu22/uwb-midterm-prior-mechanism-b`，Git外原始目录 `/home/ubuntu22/uwb-midterm-prior-mechanism-b-artifacts/formal`，独立venv在同 artifacts 下。Python3.10.12、NumPy2.2.6、SciPy1.15.3，图使用Matplotlib3.10.9。所有复核输出必须选尚不存在的路径。

```sh
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
# 在交付checkout、使用上述venv；只读压缩证据，不调用优化器：
python tools/midterm_prior_mechanism_b/readback.py --run docs/research/midterm_prior_mechanism_b/results --portable --out /tmp/prior-mechanism-audit
python tools/midterm_prior_mechanism_b/analyze_cached.py --input /tmp/prior-mechanism-audit --out /tmp/prior-mechanism-analysis
python tools/midterm_prior_mechanism_b/figures.py --input /tmp/prior-mechanism-analysis --out /tmp/prior-mechanism-figures
```

携带分片保存输入、真值和显式注入作离线诊断、先验机制、三个随机流规则、P0/P1/LINEAR状态/失败/估计、配置和来源。完整残差/J/协方差在Git外；便携读回按明确测量次序重建，无需原机器目录。LINEAR是依赖真值的仿射诊断，不是可部署算法，也不是新增独立样本。B0本批不读任何peer故障，B1仍漏建模，B2估自由常偏差，B3知道真实注入。

如原始运行需恢复，只在冻结提交独立checkout执行：

```sh
python tools/midterm_prior_mechanism_b/run.py --mode formal --freeze 5223d08ed219bafeb092df6f598b842308dee33e --out /绝对路径/原始目录 --resume
```

已有失败属于已完成；恢复不重跑。已完成矩阵无需再次定位；同seed重放不得称新验证。新方向必须另拟协议/种子，不能用本批调参后宣称独立验证。报告中的sigma比较在random_correct组同时改变生成prior精度和权重，不等于固定观测的纯权重效应。

验收顺序：核验SHA256SUMS；运行portable读回；核对3600输入、14400非线性/14400线性记录、43200阶段和完整分母；核对覆盖不可用理由及接受子集；阅读REPORT与DECISION_MEMO。所有CI按100seed、逐项解释，不推论保护级或罕见风险。

统计推荐analyze_cached.py，它仅一次读取数组后调用原冻结analyze函数；原入口也可执行但反复解压较慢。等价验证与首次只读统计中断说明见ANALYSIS_IO_NOTE.json，仿真结果没有重跑或更改。

最终完成：3600输入，14400/14400非线性、14400/14400直接线性；非线性65未驻点，其余14335接受；线性14400均通过直接核验，所有估计有限、缺失0。6400个传播二维块因奇异不可用，另有总曲率逆区间，不把这些块当成功或当解非唯一。PER_RUN的LINEAR行所附P0_category只是同输入非线性方法的配对背景，直接线性本身没有P0/P1或SciPy优化状态。

最终线性/非线性散点图使用自动包含全部数据的坐标范围（某些漏建模B1线性MSE超过1m²），生成命令：

```sh
python tools/midterm_prior_mechanism_b/plot_full_range.py --input /tmp/prior-mechanism-analysis/SUMMARY.csv --out /tmp/prior-mechanism-figures/linear_nonlinear_full_range.png
```

其余图沿用冻结figures.py；原开发散点轴上限为1的图仅保留在Git外历史图目录，交付采用full_range图，没有删去极端条件。
