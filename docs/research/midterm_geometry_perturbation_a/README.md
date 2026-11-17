# A端：共线几何与不确定性失准机制

固定起点PR115：`b340f6bd05a97ac3f80ea4796d4c317114f508a8`。冻结及正式执行SHA：`19a6c6a3ff94d81d9ff905aea6b94a1d31c5070b`。未吸收移动main，不修改历史代码、结果、中期正文或月球任务目录。

PR115在开始和交付前检查时尚未合并。本轮新PR以其来源分支research/midterm-noise-scale-a为base，清晰展示本轮两个新增目录；依赖PR115但不等待或自动合并它。

完整执行：3几何×40新seed×B2/B3×5初值=1200配置，2400阶段及实际优化器调用；1181接受、16未驻点、3预算耗尽，0异常/缺失。开发另30配置/60调用，全接受。每seed实际五初值、噪声、运动、先验在三几何下逐项相同。主要结果见[REPORT](REPORT.md)及[DECISION_MEMO](DECISION_MEMO.md)。

## 环境

实际工作树/home/ubuntu22/uwb-midterm-geometry-perturbation-a，分支research/midterm-geometry-perturbation-a。原工作树clean，完整HEAD为上述固定来源；remote=https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git。未发现适用AGENTS.md。Python3.10.12、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9，独立venv、单线程BLAS。开始可用约17GB；进程检查仅可见本沙箱，不宣称宿主机无其他任务。

Git外目录/home/ubuntu22/uwb-midterm-geometry-perturbation-a-artifacts保存独立venv和完整阶段r/J（正式原始目录约36MB）。交付约11MB，便携输入与终点不依赖上述绝对路径。

## 无优化复核命令

在仓库根执行，输出路径须不存在，不覆盖已有结果：

```bash
python3 -m venv /tmp/geometry-a-venv
/tmp/geometry-a-venv/bin/pip install -r docs/research/midterm_geometry_perturbation_a/requirements.txt
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
/tmp/geometry-a-venv/bin/python tools/midterm_geometry_perturbation_a/readback.py --inputs docs/research/midterm_geometry_perturbation_a/results/INPUTS.jsonl.gz --endpoints docs/research/midterm_geometry_perturbation_a/results/ENDPOINTS.jsonl.gz --output /tmp/geometry-a-readback
/tmp/geometry-a-venv/bin/python tools/midterm_geometry_perturbation_a/summarize.py --input /tmp/geometry-a-readback --output /tmp/geometry-a-summary
/tmp/geometry-a-venv/bin/python tools/midterm_geometry_perturbation_a/contrasts.py --input /tmp/geometry-a-readback --output /tmp/geometry-a-contrasts
/tmp/geometry-a-venv/bin/python tools/midterm_geometry_perturbation_a/group_summary.py --input /tmp/geometry-a-contrasts/SEED_METRICS.csv --output /tmp/geometry-a-contrasts/GROUP_SUMMARY.csv
/tmp/geometry-a-venv/bin/python tools/midterm_geometry_perturbation_a/information.py --results docs/research/midterm_geometry_perturbation_a/results --output /tmp/geometry-a-information
/tmp/geometry-a-venv/bin/python tools/midterm_geometry_perturbation_a/information_summary.py --results docs/research/midterm_geometry_perturbation_a/results --output /tmp/geometry-a-information-summary
/tmp/geometry-a-venv/bin/python tools/midterm_geometry_perturbation_a/final_checks.py --results docs/research/midterm_geometry_perturbation_a/results --output /tmp/geometry-a-final-checks.json
/tmp/geometry-a-venv/bin/python tools/midterm_geometry_perturbation_a/verify_delivery.py --results docs/research/midterm_geometry_perturbation_a/results --output /tmp/geometry-a-delivery-checks.json
/tmp/geometry-a-venv/bin/python tools/midterm_geometry_perturbation_a/figures.py --results docs/research/midterm_geometry_perturbation_a/results --output /tmp/geometry-a-figures
```

这些入口不生成新观测、不调用优化器；final_checks只导入旧目标定义核对r/J及实际solver receipt。NPZ一次载入内存，避免重复解压。information_summary/figures/final_checks的上述命令直接核验仓库交付表；若要检查新生成表，可将对应子目录组装到新results根再传参。

实际正式命令（已完成，验收不应重跑）：

```bash
PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/ubuntu22/uwb-midterm-geometry-perturbation-a-artifacts/venv/bin/python tools/midterm_geometry_perturbation_a/run.py --output /home/ubuntu22/uwb-midterm-geometry-perturbation-a-artifacts/formal
```

执行使用非阻塞OS独占锁、调用前attempt、独占原子结果写入及文件/目录fsync。进入输出目录即扫描孤立attempt，任何attempt缺结果就拒绝继续，既不重跑该配置也不先跑其他配置。已完成记录只读；调用上限2400。并发进程拒绝和孤立attempt保留已测试。完整运行无待恢复单元，失败不清空。

## 文件与数学合同

- PROTOCOL/CONFIG/SEEDS/FREEZE_MANIFEST：预提交设计及执行依赖哈希；SOURCE_MANIFEST和SHA256SUMS为交付来源/文件清单，后者排除自身。
- GEOMETRY_PRECHECK：真实源轴(1,0)、法向(0,1)，δ=0/.1/.5后锚点。输入中的initials始终由未扰动锚点生成。
- INPUTS.jsonl.gz：120输入，保存真实轨迹、标准噪声、实际sigma、先验与五初始状态。ENDPOINTS.jsonl.gz：1200配置的P0/P1状态、分类、梯度范数、预算/耗时和receipt哈希。
- EXECUTION_LEDGER.jsonl.gz：2400次attempt/阶段配对及原始文件哈希、输入digest、调用数、阶段类别；完整r/J原始文件在Git外。
- readback/ENDPOINT_METRICS.csv的index与POINTS.npz首维1200一致。q/trace/area95/reason=[1200,2,12]，视图0总GN曲率逆、1固定先验噪声传播；12点按(t,car)，状态24位置按(t,car,xy)，B2另有第25维偏差。error单位m，trace/面积单位m²；gradient/scaled_gradient=[1200,25]，B3最后一维NaN为不适用。NaN不可用不填零。
- WEAK_CURVATURE/WEAK_SUBSPACES保存所有有限端点最弱子空间；全有限与接受候选分组均保留，精确Hessian不作强制协方差逆。
- information按range(54行)、range_motion(74行)、total(78行)分别给秩、条件横向信息与消去纵向/偏差后的有效横向信息，单位m⁻²。条件信息不是边缘信息。TRUTH_DESIGN_INFORMATION只有6个确定性设计点，不增加seed数。
- summary给原I0/selected等主表；contrasts/GEOMETRY_CONTRASTS给配对差；GROUP_SUMMARY将原I0、selected、选优组、全部有限和接受候选的覆盖/尺寸/可用率放在同一行。组内先平均成员再平均seed，因此weighted_covered_points是等权点数，不能当作额外独立样本。
- 每条件每方法40seed，每车240点、每方法200配置。主曲率覆盖与固定先验噪声视图分列；六时刻全部覆盖不等于点态95%保证。multiple_groups等组级指标重复在两车行仅方便联表，不是两个独立检验。
