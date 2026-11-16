# 验收证据入口

结论见REPORT.md；独立复核代码为independent_acceptance.py，结果INDEPENDENT_CHECKS.json。B_ACCEPTANCE_RERUN和B_CHECKS_RERUN来自实际重跑；DEVELOPMENT_EVIDENCE.tar.gz保留完整人工失败、恢复和旧输入回归。FROZEN_*是被验收版本原字节副本，EXECUTION_PLAN.json记录来源、环境、路径和用户授权。

命令在仓库根运行，所有输出要求新路径：

```bash
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
UWB_PY=/home/ubuntu22/uwb-midterm-s1b-artifacts-20261116/venv/bin/python
"$UWB_PY" tools/midterm_simulation_validation/accept.py --out /home/ubuntu22/uwb-s2-confirmation-artifacts/acceptance-b-fixtures
"$UWB_PY" docs/research/midterm_validation_acceptance/independent_acceptance.py \
 --root /home/ubuntu22/uwb-midterm-s2-confirmation \
 --fixtures /home/ubuntu22/uwb-s2-confirmation-artifacts/acceptance-b-fixtures \
 --out /home/ubuntu22/uwb-s2-confirmation-artifacts/independent-acceptance.json
```

这两条是本轮已执行命令；复现使用新输出路径。正式运行在B固定SHA的独立checkout；正式结果交付到../midterm_simulation_confirmation/。本报告提交后才授权本执行器开始生成正式观测（用户已明确授权，无需另问）。
