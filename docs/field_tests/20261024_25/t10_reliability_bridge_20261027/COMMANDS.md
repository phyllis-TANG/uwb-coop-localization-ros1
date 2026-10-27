# 实际命令与运行条件

在干净独立工作树 e038868f2b1995a0b88f962ce80203a6e2a6460e 执行。其整棵Git树与公开 db2aac52cbd687f53f0456f00875859212487a84 相同；提交元数据不同的原因及逐源SHA见 SOURCE_IDENTITY.json。没有重跑或改写执行记录。

依赖环境：Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0，隔离venv使用系统只读依赖；OPENBLAS_NUM_THREADS=1、OMP_NUM_THREADS=1。PR53原执行使用NumPy 2.4.1，本轮全部原基线实际逐行比对差值为零。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
# 五套相关测试，依次为47、17、25、6、6项，共101项。
for suite in causal_baselines parameter_clock_prep causal_reliability t10_exploratory t10_reliability_bridge; do
  "$PYTHON" -m unittest discover -s "tools/field_20261024_25/$suite" -p 'test_*.py' -v
done
"$PYTHON" tools/field_20261024_25/t10_reliability_bridge/bridge.py --packet "$T10_PACKET" --output "$RESULTS"
"$PYTHON" tools/field_20261024_25/t10_reliability_bridge/audit.py --results "$RESULTS" --pr53-results "$PR53_RESULTS" --output "$NEW_AUDIT"
"$PYTHON" tools/field_20261024_25/t10_reliability_bridge/report.py --results "$RESULTS" --audit "$NEW_AUDIT" --output "$NEW_REPORT"
"$PYTHON" docs/field_tests/20261024_25/t10_reliability_bridge_20261027/inspect_equivalence.py "$RESULTS" "$NEW_EQUIVALENCE_JSON"
# 原严格预检查另写新目录，实际退出2，未被探索性入口放宽。
"$PYTHON" tools/field_20261024_25/causal_reliability/preflight_t10.py --output "$NEW_STRICT_CHECK"
```

所有输出目录均需新建，完整日志在Git外结果归档。没有通过ROS、串口或硬件执行任务，没有定位回放T09/T11/T13/T15，没有下载/解码视频，没有修改共享manifest、geometry、PR51严格配置或冻结估计器。
