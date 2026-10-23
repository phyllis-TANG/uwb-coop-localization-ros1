# 定位完好性监测可行性试验：已完成

当前实验仓库：`/home/ubuntu22/双车协同/uwb-coop-localization-ros1`。
实验分支：`experiment/integrity-feasibility-v1-20261022`。
固定基线：`13aeade4c6b13ffa55b0acfafe65c29136067c0f`（PR37）。收尾远端main已更新至`21d3d48476579837caa6aee4e1027cf57b9d18e3`（PR38，仅双车离线对照新增），本轮没有切换或合并。

正式交付目录：`docs/field_tests/integrity_feasibility_v1_1_20261022`；先读该目录README.md和results_reviewed/CONCLUSION_ONE_PAGE_ZH.pdf，再读results_reviewed/REPORT.md。

完成31次估计器运行：2实测+5正常开发+24冻结诊断；37项单车/监测测试、4项评价测试通过。两历史包逐次发布最大差<1e-15m。冻结阈值M1=1.0，M2=0.062191200771030145m；连续2次触发，无自动剔除。实际运行总耗时约52.47s，单条最大2.32s，未触及180s/3600s预算。2769次发布与11076条排除假设记录校验通过。

v1保留故障标签NumPy bool写JSON失败和全部完成产物。v1.1只修复标签序列化，按原执行哈希导入10个完成项，8个仿真输入逐字节重生成相同；不重复开发或正常诊断、不调整阈值。ALL_RUNS.csv/JSON覆盖31个逻辑估计运行+1次尚未进入估计器的生成失败。results保留初次评价，results_reviewed为正式版，增加报警起始归因、历史实测阈值迁移失败及0.50m未覆盖说明。

关键结论：M1会吸收持续偏差后停报；M2对持续/渐增偏差保留更多报警覆盖，但有名义误报与恢复尾巴。仿真阈值在历史正常包005135仍使M2报警78/92状态，不可直接部署。仅两锚明确不可监测，延迟状态报警不是当前车辆实时保护。下一轮优先共享墙锚故障，先核验参考与独立真值。

恢复/核对必须显式指定v1.1目录，切勿使用默认v1：

```bash
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/run_single_car_integrity_experiment.py --experiment docs/field_tests/integrity_feasibility_v1_1_20261022 --phase all
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/verify_single_car_integrity_artifacts.py --experiment docs/field_tests/integrity_feasibility_v1_1_20261022
```

已实际执行恢复检查：31项全部按源码、配置、输入与输出哈希校验后跳过，没有重复启动估计器。协议、source_lock、各run.json、version_lineage及final_source_hashes共同标明执行来源。源码或配置变化必须另起版本；不要覆盖已完成运行。此阶段无剩余运行或待处理失败，不自动扩大网格。

原仓库`/home/ubuntu22/uwb/uwb-coop-localization-ros1`保持原HEAD `f0bc463b6b97d1ac85c2d6f4239d0d1bd30c9835`及干净状态；原bag、备注、历史结果和已有ROS/仿真进程不变。没有启动真实小车，没有推送或合并。
