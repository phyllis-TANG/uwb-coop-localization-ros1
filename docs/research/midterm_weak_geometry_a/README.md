# A端：弱几何与非线性诊断

固定开发来源：`c51411433d30dc379bd69cf5fb20a11e196b7182`（PR109）；补充只读来源：`41ba0d3a6e69897ef6330cc9ad218253c7fb80ea`（PR108）。本轮仅增加两个同名任务目录。

这是既有输入上的初始化诊断，不是新seed确认。240个保存输入×3方法；复用720个原始配置，新增2880个初始化配置。新增5760个阶段/优化器调用，2873接受、7未驻点。开发冒烟另外12配置/24调用。原配置719接受、1未驻点；全部3600候选3592接受、8未驻点。最低代价选择仅在接受候选间进行，720个输入方法单元均有候选。

阅读 [REPORT.md](REPORT.md)、[PROTOCOL.md](PROTOCOL.md)、[DECISION_MEMO.md](DECISION_MEMO.md)。协议先于完整执行提交在 `fdafeb4`；执行源码提交 `22fe588`，完整SHA见results/START.json与SOURCE_CHECKS.json。所有输入来自仓库证据，无观测噪声生成。

## 环境和复核命令

实际工作树 `/home/ubuntu22/uwb-midterm-weak-geometry-a`；分支 `research/midterm-weak-geometry-diagnosis-a`。独立venv和原始阶段在 `/home/ubuntu22/uwb-midterm-weak-geometry-a-artifacts/`，该绝对路径不是复核依赖。Python3.10.12、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9；单线程BLAS。开始可用空间约29GB，运行后约23GB；任务原始阶段约88MB。原A工作树干净，未覆盖其修改；未发现适用AGENTS.md。当前沙箱仅能看到自身进程，不能推断宿主机无其他任务。remote为https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git。

从仓库根执行（输出目录必须不存在；不会覆盖旧结果）：

```bash
python3 -m venv /tmp/weak-a-venv
/tmp/weak-a-venv/bin/pip install -r docs/research/midterm_weak_geometry_a/requirements.txt
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
/tmp/weak-a-venv/bin/python tools/midterm_weak_geometry_a/readback.py --endpoints docs/research/midterm_weak_geometry_a/results/ENDPOINTS.jsonl.gz --output /tmp/weak-a-readback
/tmp/weak-a-venv/bin/python tools/midterm_weak_geometry_a/summarize.py --input /tmp/weak-a-readback --output /tmp/weak-a-summary
/tmp/weak-a-venv/bin/python tools/midterm_weak_geometry_a/diagnostics.py --results docs/research/midterm_weak_geometry_a/results --output /tmp/weak-a-diagnostics
/tmp/weak-a-venv/bin/python tools/midterm_weak_geometry_a/figures.py --results docs/research/midterm_weak_geometry_a/results --output /tmp/weak-a-figures
```

以上读回/汇总/诊断/图形入口不导入求解入口、不调用优化器或生成器。verify.py仅为独立目标交叉核验导入冻结core定义，不调用优化器；它的结果已保存。prepare.py只验证哈希并提取保存输入，已完成且不必再次运行。所有数学与选择规则见协议。

本次实际新增求解命令（复核不需要重跑）：

```bash
PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/ubuntu22/uwb-midterm-weak-geometry-a-artifacts/venv/bin/python tools/midterm_weak_geometry_a/run.py --output /home/ubuntu22/uwb-midterm-weak-geometry-a-artifacts/formal
```

完整求解已结束，无待恢复单元。若在新环境另行复现实验，先明确这会重新优化；原运行恢复必须使用results/START.json固定执行提交，CONTRACT核对全部执行源码。每阶段预写attempt、原子落盘；有attempt无结果会拒绝自动重跑，保留中断暴露记录；已完成阶段只读回。不要删除失败记录反复重跑。

## 文件合同

- INPUTS.jsonl.gz：240个原输入、显式四种初始化、720配置原P0/P1终点。原输入含truth供离线评价，initials函数只接受anchors/start两个参数。
- results/ENDPOINTS.jsonl.gz：2880配置的新P0/P1状态、代价、梯度范数、数值标签、nfev、耗时、调用数、solver输入哈希。
- results/readback/POINTS.npz：顺序对应ENDPOINT_METRICS.csv的index。q/trace/area95/reason为[3600,2,12]，视图0曲率/1固定先验噪声；12点按t,car排序。error=[3600,12,2]单位m；trace/area95单位m²，q无量纲；bias_q/variance=[3600,2]，非B2为NaN。gradient/scaled_gradient为[3600,25]，B1/B3仅前24维有意义、末维NaN；B2末维为偏差导数。NaN为不可用或明确不适用而非零。
- SELECTION.json记录原/选优index、接受组、稳定子集；GROUPS.csv按单输入内分组；PAIRS.csv保留全部720单元×10=7200候选对。
- summary：COVERAGE含逐时刻、六点平均、六时刻全部覆盖；METRICS逐车误差与尺度；PAIRED保留seed配对；BRANCH/FAILURES/WITHIN_GROUP解释分组和失败。
- COVERAGE中planned_rate_ci针对“全计划有效且覆盖”，valid_rate_ci另针对可用区间的覆盖；子集门槛不足20个有效seed则不报后者。未入子集不是算法失败，原因明确标为NO_SELECTED_OR_SUBSET。WITHIN_GROUP每seed先平均组内成员，不把成员数当n。
- diagnostics包含固定首seed的48个Hessian和2424个剖面点。图均从保存表格绘制。

SHA256SUMS.json排除自身，覆盖本交付所有其他文件；SOURCE_CHECKS.json记录81个源文件哈希，results/CONTRACT.json记录执行时源码。大体积r/J原始阶段在Git外；上述精简状态足以无优化重算全部交付指标。
