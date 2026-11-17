# Moon_1 阶段一：场景复建与高差审计

[报告](REPORT.md) · [冻结协议](PROTOCOL.md) · [配置](CONFIG.json) · [交接](HANDOFF.md)

本次从已有LuSNAR模拟场景融合PLY与GT复建NPZ和新版CSV。9个NPZ数组与旧文件一致；20Hz忽略高差失配RMS0.230184mm、最大0.639510mm，固定−0.03m高差RMS0.204533mm。选择B：保留小效应结果，优先运动退化/测距偏差接口；专门研究高差时先使用独立标记的解析坡面。

formal_runs=0，nonlinear_solver_calls=0。没有定位性能或覆盖结论。所有旧资产只读，USD/GUI/ROS未运行。原始采样155点和重采样352点不是独立实验重复。

## 复建

在干净的本PR代码checkout执行，OUT必须为未存在的Git外目录。环境仅需CPU：

```sh
python3 -m venv --without-pip /tmp/moon1-audit-venv
python3 -m pip --python /tmp/moon1-audit-venv/bin/python install -r tools/moon1_height_audit/requirements.txt
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
/tmp/moon1-audit-venv/bin/python -m unittest discover -s tools/moon1_height_audit -p 'test_*.py' -v
/tmp/moon1-audit-venv/bin/python sim/isaac_lab/moon1/test_antenna_geometry.py
/tmp/moon1-audit-venv/bin/python tools/moon1_height_audit/run.py \
  --ply /path/to/moon1_fused_lidar.ply \
  --gt /path/to/Moon_1/gt.txt \
  --old-dir /path/to/old/moon1/output \
  --out /tmp/moon1-rebuild-new
/tmp/moon1-audit-venv/bin/python tools/moon1_height_audit/verify.py \
  --input /tmp/moon1-rebuild-new --out /tmp/moon1-readback-new.json
```

执行前确保有 `db45d94d03061e6828afb25d841c2b1777d0af48` Git对象；生成器、依赖和后端高度配置会逐字验证该版本，主输入在输出建立前盘点。新路径必须不存在，旧输出不会被覆盖。迁移路径后manifest绝对路径和文件封装哈希可能变化，数值比较看逐数组/字段，不要求字节强行一致。

缺资产时只运行合成测试并报告缺项，不能称Moon_1复现。最小复建输入为本报告记录哈希的融合PLY、GT；旧NPZ/CSV/summary用于旧新比较。没有旧文件时需先明确这是“新生成”而非完整历史对照，本入口会报缺项。六帧TXT用于上游来源审计，不是本轮重新融合的必要输入。大文件不随PR分发，无需下载完整Moon_1.zip。

## 只读验收便携证据

```sh
/tmp/moon1-audit-venv/bin/python tools/moon1_height_audit/verify.py \
  --input docs/research/moon1_height_audit/results \
  --out /tmp/moon1-portable-readback-new.json
```

便携包包括507行几何时序、70行统计、1014条压缩支持追踪与图。读回无需运行优化器；没有原NPZ时会明确 `scene_support_rechecked=false`，没有源文件时列unavailable，不声称重新验证原始地形/来源。完整运行的检查另见READBACK_WITH_GRID.json。

- INPUTS：当前文件身份、大小、结构，不是旧生成证明。
- COMMANDS/ENVIRONMENT/RUN：实际生成命令、软件环境、冻结执行提交及哈希。
- provenance/uwb_replay.manifest：本次派生链；未生成USD保持不可用。
- COMPARISON：新旧9数组、所有CSV/summary字段。
- TIMESERIES/METRICS：米、秒；图中测距差转换为mm。
- SUPPORT_TRACE：逐端4节点/权重/donor/EDT/原PLY最近XY距离与分层。
- STRATUM_CONTRIBUTIONS：描述性平方和分配，不是因果归因。
- RANK：自由3D双车单距离，权重1，秩1；不是定位精度。
- TEST_COMMANDS及日志：合成验收与实际资产只读复核分开。

数据来源为[LuSNAR](https://github.com/zqyu9/LuSNAR-dataset)，本机上游README快照身份已记录。按其学术引用要求使用；不在本PR分发原数据，也不把历史README作为最新授权查询。代码入口见 [tools README](../../../tools/moon1_height_audit/README.md)。

交付CSV统一为LF换行，数值不变；原生成文件保持原样。PACKAGING记录封装前后哈希，RUN记录原输出哈希，SHA256SUMS记录仓库交付字节。
