# 先验与非线性机制对照 B端

来源764064f224ada7e793430bd47f5122a14b8d1f30。完整实验定义见PROTOCOL.md；执行参数唯一来源CONFIG.json。36条件×100seed，14400非线性方法与14400真值处线性化诊断，不是28800独立随机样本。

使用独立Python3.10 venv，requirements.txt精确固定NumPy/SciPy；设置 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1。命令均在仓库根，python指向该venv。

```sh
python tools/midterm_prior_mechanism_b/checks.py --out /Git外/新开发目录
python tools/midterm_prior_mechanism_b/run.py --mode formal --freeze 完整冻结SHA --out /Git外/新正式目录
# 原样恢复，仅补未持久化阶段：上一命令追加 --resume
python tools/midterm_prior_mechanism_b/readback.py --run /Git外/正式目录 --out /Git外/新读回目录
python tools/midterm_prior_mechanism_b/analyze.py --input /Git外/读回目录 --out /Git外/新统计目录
python tools/midterm_prior_mechanism_b/readback.py --run docs/research/midterm_prior_mechanism_b/results --portable --out /Git外/新独立验收目录
```

恢复必须在原冻结checkout，源码/配置/HEAD/依赖一致。已有目录拒绝覆盖。所有数值失败保留；人工失败fixture隔离在开发目录，不能混入性能统计。可携带证据无需原机器目录即可核验，不调用优化器。

已阅读PR106 THEORY/REPORT/ANALYSIS_PROTOCOL/NOISE_MISMATCH_THEORY及analyze/diagnostics/summarize/check_formulas，原冻结CONFIG/VALIDATION_PROTOCOL/core/prototype/PR97数学实现，PR107 adapter/run/readback与失败保存实现。局部曲率、固定偏移和生成机制传播的区别见协议。

资源预计：开发36输入、432阶段加两次读回约4.2秒；按100倍估计正式存储低于1GB，另留审计/打包余量，至少6GB空闲、2worker。统计bootstrap和解析覆盖积分可能另需数分钟。正式进度不依据结果缩减。
