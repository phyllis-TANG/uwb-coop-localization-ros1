# 实测数据接入与Moon_1研究合流

从[报告](REPORT.md)和[固定协议](PROTOCOL.md)开始。恢复了PR128合并后的未完成任务，新增三包固定1—20秒实测入口、六次独立/协同SE(2)对照及便携读回。Moon_1代码、历史结果和其他窗口保持只读。

- CONFIG.json：实际设施、外参、工程权重、历史校正、初值与预算。
- FREEZE.json：运行使用的代码与输入SHA256；Git冻结提交失败的时序偏差见REPORT。
- ACCEPTANCE.json：原bag/便携输入一致、差分、异常输入等验收。
- results/NUMERICS.csv：全六项数值结果；均有限，0/6通过1e-5梯度门槛。
- results/METHOD_CHANGES.csv：方法间位置变化，不是真值精度。
- results/portable.json.gz：完整输入、端点、Jacobian及调用账本。

使用Python 3.10、numpy==2.2.6、scipy==1.15.3、matplotlib==3.10.9、rosbags==0.10.11。现有独立环境位于/home/ubuntu22/uwb-field-moon1-integration-artifacts/venv。

零优化器复核（解包至一个不存在的新目录，不覆盖已有结果）：

```bash
set -e
PY=/home/ubuntu22/uwb-field-moon1-integration-artifacts/venv/bin/python
$PY tools/field_moon1_integration/unpack.py docs/research/field_moon1_integration/results/portable.json.gz /tmp/field-moon1-readback
OPENBLAS_NUM_THREADS=1 $PY tools/field_moon1_integration/verify.py /tmp/field-moon1-readback
```

原始输入验收可执行`tools/field_moon1_integration/validate.py`，需要仓库中对应原bag（哈希先核验）。运行入口`run.py OUTPUT`有六调用上限、独占锁和调用前attempt；已有RUN一律拒绝自动重跑。本轮已完成，无需再次调用。将来新实验应单独立项和冻结，不能覆盖或将同包回放算作新独立样本。

历史缺少连续真值、外参原点与同步标定，实测结果属于条件开发。formal_runs=0。没有将实测融入Moon_1噪声分布、没有真实月面校准声明。
