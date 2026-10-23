# 首轮定位完好性监测可行性试验（v1.1）

正式交付入口：

- [一页中文结论 PDF](results_reviewed/CONCLUSION_ONE_PAGE_ZH.pdf)；[中文结论 Markdown](results_reviewed/CONCLUSION_ZH.md)
- [详细报告](results_reviewed/REPORT.md)；[图表索引](results_reviewed/FIGURES.md)
- [冻结协议](protocol.json)、[纯估计器配置](estimator_config.json)、[冻结阈值](thresholds.json)、[源码锁](source_lock.json)
- [全部逻辑运行与失败](ALL_RUNS.csv)、[运行检查点](run_inventory.json)、[产物校验](artifact_verification.json)
- [逐时刻误差/统计量/报警](results_reviewed/timeseries.csv)、[全部区间](results_reviewed/intervals.csv)、[逐运行指标](results_reviewed/metrics.csv)、[实测监测回算](results_reviewed/historical_monitor_timeseries.csv)
- 原始逐更新残差、独立排除先验与时间戳：`runs/<id>/output/updates.jsonl`；仿真输入 `sensors.jsonl` 与评价用 `truth.csv`、`fault_labels.json` 分离。
- [37项单车测试日志](single_car_tests.log)、[4项指标测试日志](metric_tests.log)、[实际依赖](runtime_dependencies.json)

原仓库保持干净；本轮独立分支 `experiment/integrity-feasibility-v1-20261022`，基线完整HEAD为 `13aeade4c6b13ffa55b0acfafe65c29136067c0f`。只监测，不自动剔除、不启动小车、不推送或合并。

共31次估计器运行：2实测、5开发、24冻结诊断；仅一次故障标签生成失败，尚未进入估计器，详见[原v1记录](../integrity_feasibility_v1_20261022/GENERATION_FAILURE.md)。v1.1只修复NumPy布尔标签JSON写盘；10项完成结果按原执行哈希复用，8个复用仿真输入已在修复版逐字节重生成核对。阈值未变，不重跑开发集和正常诊断。[版本谱系](version_lineage.json)。

`results`保留初次评价；`results_reviewed`为正式复核版，补充原已报警/新报警起始审计、实测阈值迁移失败和0.50m未覆盖限制。定位器、生成模型和冻结阈值未因结果改动。

## 复现与恢复

在仓库根目录使用现场已存在离线依赖，不必安装或启动ROS：

```bash
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tools -p 'test_single_car_*.py' -v
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tools -p 'test_integrity_evaluation.py' -v
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/run_single_car_integrity_experiment.py --experiment docs/field_tests/integrity_feasibility_v1_1_20261022 --phase all
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/verify_single_car_integrity_artifacts.py --experiment docs/field_tests/integrity_feasibility_v1_1_20261022
```

恢复命令必须显式给出v1.1路径；脚本默认目录为原v1故障档案，不能用作本轮恢复。已实际验证31项全部校验后跳过，没有重复启动工作者。源码、协议、输入或已有输出哈希不符即停止。新的报告输出目录必须不存在；从零重跑应作为单独复现实验保留，不能覆盖本轮证据。

```bash
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/uwb-integrity-mpl python3 tools/report_single_car_integrity.py --experiment docs/field_tests/integrity_feasibility_v1_1_20261022 --output /tmp/integrity-report-reproduction
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps MPLCONFIGDIR=/tmp/uwb-integrity-mpl python3 tools/export_integrity_conclusion_pdf.py --results /tmp/integrity-report-reproduction
```

哈希清单相对于仓库根目录；`ARTIFACT_SHA256SUMS.txt`不包含自身。`source_lock.json`锁定运行期间估计/生成源码；评价、验证、导出脚本另见`final_source_hashes.json`，各运行原执行哈希另存于run.json。原始bag、既有备注及历史报告不改写。

收尾远端核对：main已更新至PR38 `21d3d48476579837caa6aee4e1027cf57b9d18e3`，相对本轮基线增加2个提交，内容为双车三包离线对照；没有修改本轮单车固定窗口文件。本轮仍固定PR37，不切换、不混入新结果。完整差异见 `remote_final_check.json`。
