# Moon_1趋势偏差与高度误差敏感性

本次完成预冻结探索：1920次唯一方法运行、3840次探索优化器调用；1844接受、76个NOT_STATIONARY完整保留。开发32次方法/64次调用，总真实调用3904，formal_runs=0。只新增本目录和tools/moon1_trend_height_eval；不修改历史资产或冻结后端。

先读[REPORT](REPORT.md)、[DECISION_MEMO](DECISION_MEMO.md)。观测证据与缺口见[UNCERTAINTY_CONTRACT](UNCERTAINTY_CONTRACT.md)，模型见[MATH](MATH.md)，预定对比见[PROTOCOL](PROTOCOL.md)，配置见[CONFIG](CONFIG.json)、[SOLVER](SOLVER.json)、[SEEDS](SEEDS.json)。环境、命令和验收分别见[ENVIRONMENT](ENVIRONMENT.md)、[TESTS](TESTS.md)、[HANDOFF](HANDOFF.md)。

固定基线0c3dbbb59a5c65087e073ad1c49eaed397f2958b；开发提交96fddaabd3dfcb3f3e668e4a736bcd7b07761a2f；探索冻结提交648ad7411fece15efc6ce75a31f8eb60e431e406。冻结后不修改数值源码、协议、配置或门槛。新增报告和verify_delivery.py仅整理及复核既有结果。

## 无优化器独立复核

从仓库根目录运行，输出目录必须未存在：

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/ubuntu22/uwb-moon1-trend-height-sensitivity-artifacts/venv/bin/python  docs/research/moon1_trend_height_eval/verify_delivery.py  --input docs/research/moon1_trend_height_eval/results  --out /tmp/moon1-trend-height-independent-new
```

其他机器使用Python3.10、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9的独立环境替换解释器。无需原NPZ、GPU、Isaac或GUI。脚本禁止真实least_squares调用，重建全部输入、阶段数值状态、统计及图，运行数学与假求解器持久化测试。实际执行回执见results/INDEPENDENT_CHECK.json和READBACK.json；本次完整表与原始目录读回逐字节一致。

## 便携证据

results/reference.json.gz、measurements.json.gz、estimates.json.gz彼此分离；attempts/dispatch保留调用前记录、输入与阶段身份，含全部失败。MANIFEST.json保存压缩归档哈希和每个原JSON文件哈希。FREEZE保存完整代码SHA、来源、环境与依赖哈希，PLAN为480组输入计划，RUN/BUDGET记录3840次调用。

PER_WINDOW、SEED_METRICS、SUMMARY、DENOMINATORS、PAIRED_SEED_COMPARISONS、COMPARISON_SUMMARY提供完整分母和逐seed配对；STAGES提供所有3840阶段；PEER_RESIDUALS提供每时刻残差；HEIGHT_REALIZATIONS保存真实高度误差实现。局部信息和协方差块在estimates归档，完整矩阵可由保存端点/J重算。DELIVERY_MANIFEST覆盖新增交付文件（不含清单自身）。大型未压缩结果保留Git外，不需要再求解来恢复归档。

图固定展示首seed及全部20seed，不选择有利案例。M0的peer残差仅诊断、不进入目标；局部协方差不含未建模高度误差，不是保护级或覆盖保证。
