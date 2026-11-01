# 命令与已执行范围

本轮已完成。不要重新启动历史 batch.py/field_batch.py、B1/B2 run.py、37 profile或正式10条件矩阵。下面旧输出目录只作读回；若确需复现开发短例，输出改成全新目录。本轮没有推送分支、创建PR或云端定时任务。

实际代码工作树 `/workspace/work/uwb-sim-imu-prep-20261101`；开发代码执行提交 `86188b7527810807260fe86e1bdf4c0f1f518301`，六个运行均记录该提交且 worktree_dirty=false。之后的docs交付变更不是原执行源码；逐文件锁和PLAN可确认Python/配置未变。

```bash
cd /workspace/work/uwb-sim-imu-prep-20261101
export UWB_TASK_ROOT=/workspace/work/uwb-sim-imu-prep-20261101-run
export UWB_PY="$UWB_TASK_ROOT/venv/bin/python"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
```

独立环境实际安装：Python3.12.14，NumPy2.2.6，SciPy1.15.3；Linux CPU。原环境没有修改。准备命令为：

```bash
python -m venv /workspace/work/uwb-sim-imu-prep-20261101-run/venv
/workspace/work/uwb-sim-imu-prep-20261101-run/venv/bin/python -m pip install numpy==2.2.6 scipy==1.15.3
```

实际执行过的合同检查及开发短例命令（输出已存在，勿原样再跑）：

```bash
"$UWB_PY" -m unittest discover -s tools/two_car_sim_dev_20261101 -p 'test_contract.py' -v
"$UWB_PY" tools/two_car_sim_dev_20261101/smoke.py --output "$UWB_TASK_ROOT/smoke-v1"
```

smoke 的20条精确子进程argv在 `smoke-v1/PLAN.json:commands`，日志在 `smoke-v1/logs`。只有seed7、static_moving、nominal/car1_wall_14，M2/M3/M3W025共六个定位单元。每子进程150秒上限；运行器事件循环120秒上限；Git外总证据小于100MB。31次状态发布/run、29 accepted、2 warmup；0–1秒无发布也留在32秒评价分母。

无需优化即可读回已有单元：下面 output 名称须新，父目录须存在。

```bash
"$UWB_PY" tools/two_car_sim_dev_20261101/readback.py \
  --run "$UWB_TASK_ROOT/smoke-v1/runs/car1_wall_14/M3W025" \
  --events "$UWB_TASK_ROOT/smoke-v1/inputs/car1_wall_14/events.jsonl.gz" \
  --output "$UWB_TASK_ROOT/review-weighted-new.json"
"$UWB_PY" tools/two_car_sim_dev_20261101/evaluate.py \
  --run "$UWB_TASK_ROOT/smoke-v1/runs/car1_wall_14/M3W025" \
  --input "$UWB_TASK_ROOT/smoke-v1/inputs/car1_wall_14" \
  --reference-run "$UWB_TASK_ROOT/smoke-v1/runs/car1_wall_14/M2" \
  --nominal-run "$UWB_TASK_ROOT/smoke-v1/runs/nominal/M3W025" \
  --nominal-input "$UWB_TASK_ROOT/smoke-v1/inputs/nominal" \
  --output "$UWB_TASK_ROOT/review-evaluation-new.json"
```

独立调用生成/运行接口的例子（这些 `example-new-*` 目录本轮未创建；不代表追加执行要求）：

```bash
"$UWB_PY" tools/two_car_sim_dev_20261101/generate.py \
  --spec tools/two_car_sim_dev_20261101/development_static_moving.json \
  --condition nominal --output "$UWB_TASK_ROOT/example-new-input"
"$UWB_PY" tools/two_car_sim_dev_20261101/run.py \
  --events "$UWB_TASK_ROOT/example-new-input/events.jsonl.gz" \
  --config "$UWB_TASK_ROOT/example-new-input/config.json" \
  --method M3W025 --output "$UWB_TASK_ROOT/example-new-run"
```

本地应用交付diff：在基于 `6c8b23087739418faa2169bf08ccae80d2d884c1` 的独立干净分支，先 `git apply --check /path/to/code.patch`，审查后 `git apply /path/to/code.patch`。补丁只新增两个专属tools/docs目录，不包含现场脚本。完整审查包带 code.patch、源码、HANDOFF、JSON合同、全部开发日志/输入/结果和SHA；不需要本地I盘或新实测bag。
