# Moon_1数值验收与时变偏差探索

本轮两项任务已完成，**formal_runs=0**。从PR117固定提交出发，仅新增本目录及tools/moon1_bias_dynamics_eval。
原始180端点仍为169接受/11未接受；22次固定继续仅2个旧失败转接受，实际端点变化为纳米量级。
360次探索完成720阶段调用，最终349接受/11未接受；未降低梯度门槛，未追加或择优重跑。
全部使用height-oracle、人工已知信标及预定peer链路；不是物理仿真或正式风险确认。

- [报告](REPORT.md) · [数值诊断](NUMERICAL_DIAGNOSIS.md) · [决策](DECISION_MEMO.md) · [交接](HANDOFF.md)
- [冻结协议](PROTOCOL.md) · [CONFIG/seed](CONFIG.json) · [SOLVER](SOLVER.json) · [继续设置](CONTINUATION.json) · [seed审计](SEED_AUDIT.json)
- [环境](ENVIRONMENT.md) · [命令与验收](TESTS.md) · [零优化器验收](ACCEPTANCE.json)
- [逐seed结果](results/PER_RUN.csv) · [完整阶段状态](results/STAGES.csv) · [逐时刻残差](results/PEER_RESIDUALS.csv)
- [全有限/双方接受汇总](results/SUMMARY.csv) · [常偏差平移检查](results/CONSTANT_SHIFT.csv)
- [旧180端点](diagnosis/ENDPOINTS.csv) · [22案例名单](diagnosis/CASES.json) · [继续对照](continuation/CONTINUATION.csv)
- [生成回执](results/FREEZE.json) · [实际调用](results/RUN.json) · [便携哈希](results/MANIFEST.json) · [独立读回](results/READBACK.json)

## 零优化器完整读回

无需原PLY、GT、NPZ、USD或GUI。在仓库根目录运行，输出目录必须不存在：

```bash
python3 -m venv /tmp/moon1-bias-venv
/tmp/moon1-bias-venv/bin/python -m pip install -r tools/moon1_localization_eval/requirements.txt
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 /tmp/moon1-bias-venv/bin/python tools/moon1_bias_dynamics_eval/readback.py --input docs/research/moon1_bias_dynamics_eval/results --out /tmp/moon1-bias-readback-new
```

完整入口读取本轮360结果，也重算PR117旧180端点与22继续端点；不调用优化器。
它核对2760个归档JSON字节哈希，独立公式重算目标/J/梯度、原标签、信息秩/尺度、输入生成与配对，输出表和图。
源码和协议冻结于 `7a22287b199060b4a7a6c0b68ea4ba9f5953eef9`；最终提交只补报告和证据。

## 输入与文件分离

本轮**使用已提交reference派生输入**，核实固定提交归档哈希与同窗轨迹一致，不声称重新验证NPZ来源链。
新观测以10个新seed生成，和PR117旧带噪观测分开。reference保存真值/注入，measurements严格无故障标签，estimates保存P0/P1及attempt。
每个gzip为JSON映射，键是相对于对应目录的文件路径，包含.json后缀。仅评价程序读取reference。
恢复原字节：`json.dumps(object, indent=2, allow_nan=False) + "\n"`，与MANIFEST原文件SHA256核对。
原始批次约18MiB放Git外；压缩核心证据约1.8MiB，另提交表/图。根目录与实际argv见FREEZE/TESTS，不假设其他机器路径存在。

## 再生成（本轮不再执行）

任务一冻结SHA `02af736734e272cd524cf38afb9991bb0b240f48`；任务二冻结SHA如上。
使用相应提交的独立干净checkout及新Git外目录，按TESTS命令运行。已有attempt不能自动重跑，不能覆盖本轮结果。
不需要PR116或合并整个分支；持久化执行组件为本目录新增，并完成假求解器检查。
