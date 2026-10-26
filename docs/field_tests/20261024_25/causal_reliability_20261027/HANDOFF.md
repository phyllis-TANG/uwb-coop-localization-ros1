# A端阶段交接：正式矩阵前

当前分支 analysis/a-side-se2-integration-20261027；独立工作树 /home/ubuntu22/uwb-a-nightly-20261027。起点32445a299b3f4674b865c4d78c4f662e51b5b857；原算法工具与7128abc无差异。

规格、九种同六维EKF比较、冻结80计划行/60唯一组合及独立回读实现完成。47原基线+17参数+25新增集成测试通过。两版各4个smoke及逐行独立回读通过；v2只增加诊断/审核，不改策略或阈值，旧源码及全部产物保留。PRE_MATRIX.json和validation/记录实际结果。

正式60组合矩阵尚未启动。本提交将冻结源码/配置后再运行；生成结果都在Git外新目录，不把smoke或PR47四维480组当正式本轮结果。T10已有模板仍缺真实初值/记录绑定、水平杆臂、时间来源，不等待B，不进行留出包定位或现场误差评价。

下一条命令（当前Git外目录不存在才执行；首次不加--resume）：

```bash
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-a-nightly-20261027-artifacts/venv/bin/python tools/field_20261024_25/causal_reliability/run.py --output /home/ubuntu22/uwb-a-nightly-20261027-artifacts/matrix_v1 --max-seconds 7200
```

source_lock/输入/配置/输出均匹配时才可显式--resume；累计任务预算从2026-10-26T18:15:14Z起计6小时，未因暂停重置。检查点和原始日志在 /home/ubuntu22/uwb-a-nightly-20261027-artifacts/checkpoints 和 logs。后续交接会补分车结果、负结果、独立回读和NAS归档/SHA，当前尚不宣称这些已生成。
