# 定位完好性试验交接（兼容修复 1.2.0）

实验标识：integrity-feasibility-v1.1

仓库：`/home/ubuntu22/双车协同/uwb-coop-localization-ros1`

当前实验目录：`/home/ubuntu22/双车协同/uwb-coop-localization-ros1/docs/field_tests/integrity_feasibility_v1_1_20261022`

阶段：全部已有项校验完成；未启动估计器；运行状态：{"completed": 31}。

原绝对输入路径仅作来源记录。恢复使用当前实验的sensors.jsonl或当前仓库的协议bag，并严格核对原SHA256；原执行源码锁、阈值和结果保持不变。

从上述仓库目录执行；依赖按tools/requirements-integrity-feasibility.txt提供：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/run_single_car_integrity_experiment.py --experiment docs/field_tests/integrity_feasibility_v1_1_20261022 --resume-only
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/verify_single_car_integrity_artifacts.py --experiment docs/field_tests/integrity_feasibility_v1_1_20261022
```

--resume-only仅核对已存在运行，任何缺失/未完成项即停止，绝不启动估计器、不重新选择阈值。兼容版本/源码快照与哈希见tools/integrity_compat/v1_2_0/manifest.json。

本交接文件为新恢复元数据，不覆盖原根目录HANDOFF或旧报告；不启动真实小车、不默认启用监测器、不合并main。
