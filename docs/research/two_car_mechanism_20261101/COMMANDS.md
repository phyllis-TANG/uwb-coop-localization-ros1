# 已执行命令与只读续接

采用main `1835472dd34087f1701f8ee8bd8f300b8c742cef` 建独立worktree `/workspace/work/uwb-two-car-mechanism-20261101`，分支 `analysis/20261101-two-car-mechanism`。原工作树/PR88源目录/现场脚本均不改。依赖numpy2.2.6、scipy1.15.3、Python3.12.14；绘图matplotlib3.10.8。独立venv位于以下Git外根。

```bash
cd /workspace/work/uwb-two-car-mechanism-20261101
export UWB_RUN=/workspace/work/uwb-two-car-mechanism-20261101-run
export UWB_PY="$UWB_RUN/venv/bin/python"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
```

协议DEV的提交为30747e1，内容SHA见PROTOCOL_DEV.sha256.json；12个长开发单元用aa12d7f执行。最终协议及分析代码在5ad1e55冻结，内容SHA见PROTOCOL.sha256.json；所有正常校准和独立test定位单元使用该干净提交。之后只汇总/打包/报告，不把交付提交冒充在线执行源码。

实际执行范围（目录已完成，**不要原样重跑**）：

```bash
"$UWB_PY" -m unittest discover -s tools/two_car_mechanism_20261101 -p test_contract.py -v
"$UWB_PY" tools/two_car_mechanism_20261101/matrix.py \
  --protocol docs/research/two_car_mechanism_20261101/PROTOCOL_DEV.json \
  --partition development --output "$UWB_RUN/development-v1"
"$UWB_PY" tools/two_car_mechanism_20261101/matrix.py \
  --protocol docs/research/two_car_mechanism_20261101/PROTOCOL.json \
  --partition calibration --output "$UWB_RUN/calibration-v1"
"$UWB_PY" tools/two_car_mechanism_20261101/matrix.py \
  --protocol docs/research/two_car_mechanism_20261101/PROTOCOL.json \
  --partition test --output "$UWB_RUN/test-v1"
```

每个partition的RUN_INDEX.json保存完整子进程argv、实际源码/协议提交、逐文件依赖锁和输入/输出/读回SHA，logs保存每条命令stdout/stderr。已有目录拒绝覆盖，不自动重试或补seed。PROTOCOL_DEV仅允许开发seed7，最终协议才允许正常参考和独立test seed；旧PR88入口的seed7保护没有删除。

只读数值核验不运行优化器。先将ARTIFACTS.json列出的同一partition各seed归档解压到同一父目录，保留 `test-v1` 等目录层级。下面示例输出文件/目录必须不存在：

```bash
"$UWB_PY" tools/two_car_mechanism_20261101/readback.py \
  --run "$UWB_RUN/test-v1/runs/20261101201-static_moving-car1_wall_14/M3W025" \
  --events "$UWB_RUN/test-v1/inputs/20261101201-static_moving-car1_wall_14/events.jsonl.gz" \
  --output "$UWB_RUN/one-cell-review-new.json"
"$UWB_PY" tools/two_car_mechanism_20261101/analyze.py \
  --matrix "$UWB_RUN/test-v1" \
  --protocol docs/research/two_car_mechanism_20261101/PROTOCOL.json \
  --output "$UWB_RUN/test-review-new"
"$UWB_PY" tools/two_car_mechanism_20261101/metric_readback.py \
  --matrix "$UWB_RUN/test-v1" --analysis "$UWB_RUN/test-review-new" \
  --protocol docs/research/two_car_mechanism_20261101/PROTOCOL.json \
  --output "$UWB_RUN/test-review-new/METRIC_READBACK.json"
```

图表只读取独立test的保存指标，不解码bag或求解：

```bash
export MPLCONFIGDIR="$UWB_RUN/mpl-config"
"$UWB_PY" tools/two_car_mechanism_20261101/plots.py \
  --analysis "$UWB_RUN/test-analysis-v1" --output "$UWB_RUN/figures-new"
```

全量运行级指标为results/test/PER_SEED.csv；运行级区间为RUN_LEVEL_INTERVALS.csv；恢复、因子支持和独立检查分别为RECOVERY_PER_SEED.csv、FACTOR_SUPPORT.json、METRIC_READBACK.json；FRAMES.jsonl.gz保留所有时刻和unknown。校准/开发资料分目录，不能累计成独立验证样本。

核心读器重算所有保存目标和每次消元的H/g/affine/常数以及gyro/receipt支持；另一指标读器从published.csv独立几何与单独truth重新算逐车误差、配对平方差、分母、恢复与区间。两者均不调用优化器；共享JSON格式、公开数学方程/分布函数及IO范围如源码所示，不冒称另一研究者完成了技术审稿。

全有限配对字段补齐后的分析源码为1fb34a7；开发/正常参考完整读表对应v2，旧v1原字段与逐帧文件均精确相同，见READOUT_AMENDMENT及检查收据。所有优化仍采用各自原冻结源码。

若要字节级重现输入身份/源SHA，需在独立干净worktree使用对应原优化提交（最终5ad1e55，开发aa12d7f）；当前交付head的读表修订会改变整套source hash，但不改变已保存轨迹。单纯审查应使用上面的只读命令，避免重复运行。
