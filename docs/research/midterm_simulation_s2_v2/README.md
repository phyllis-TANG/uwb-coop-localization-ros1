# B端增广原型数值协议 v2

仅开发诊断，formal_runs=0。固定来源与差异见ALIGNMENT；先登记NUMERICAL_PLAN，再完成共同面板原协议128次、替代256次及补充108×两阶段。结果及限制见REPORT，后续见HANDOFF。没有修改旧代码、公共后端、论文结论或实车配置。

- PER_RUN.csv：600次求解阶段逐行；P1是继续段，total_nfev/total_elapsed_s另含P0。不能把阶段数当独立n。
- INPUT_HASHES.csv与common_inputs.json.gz/supplement_inputs.json.gz：59条件完整输入/评价truth分开存放；32共同条件与B原结果哈希逐项一致。
- original_results.json.gz：保留原B.solve输出（含原状态、原协方差）及附加诊断。alternatives_results.json.gz、supplement_results.json.gz保存各次状态、残差、梯度、谱、完整零空间、warnings。
- PROTOCOL_COMPARISON.csv、STOP_CLASSIFICATION.csv、SUPPLEMENT.csv、CONTROLLED_PAIRS.csv：全分母对照。
- CHECKS.json、CHECK_LOG.txt：600状态独立残差、代价、差分梯度、误差及来源复核。SOURCE_LOCK与SHA256SUMS用于完整性审查。

复现使用B原环境：Python3.10.12 / NumPy2.2.6 / SciPy1.15.3。系统默认SciPy1.8.0不兼容，勿使用该组合。A必须为固定ed17e3a的只读checkout，并含tools/midterm_simulation_s1b及对应docs。

```bash
PY=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python
OUT=/home/ubuntu22/uwb-midterm-s2-numerics-v2-artifacts/new-run
$PY tools/midterm_simulation_s2_v2/run.py --stage original --out "$OUT"
$PY tools/midterm_simulation_s2_v2/run.py --stage alternatives --out "$OUT"
$PY tools/midterm_simulation_s2_v2/run.py --stage supplement --out "$OUT"
$PY tools/midterm_simulation_s2_v2/check_and_report.py --out "$OUT" --a-root /home/ubuntu22/uwb-s2-v2-a-readonly
```

求解脚本拒绝覆盖同阶段已有结果，无formal模式。复核脚本不求解，但会重写本v2目录的派生表和压缩证据；仅在自己的开发checkout使用。原始展开结果在独立Git外目录，本次run1约24MB；仓库只保留压缩可审查证据与小表。求解耗时不含事后信息/误差计算；P0原elapsed含B原信息计算，因此非严格求解器速度基准。
