# 交接与验收

- 开发起点：PR109 `c51411433d30dc379bd69cf5fb20a11e196b7182`。
- 补充只读来源：PR108 `41ba0d3a6e69897ef6330cc9ad218253c7fb80ea`，`docs/research/midterm_joint_coverage_a/MATRIX_DEFINITIONS.md`、README、REPORT。
- 完整冻结提交：`027a4693a2039c7534b8ffef070f12435aec04fd`。先提交推送，再执行960次求解。冻结后求解/数学/主分析源码未改变；supplement.py、acceptance.py是交付期只读统计和人工缺失测试入口，不影响求解。
- 交付提交请用 `git rev-parse HEAD`，避免将自身SHA写进自身内容；PR及最终回复提供完整值。
- 独立工作区 `/home/ubuntu22/uwb-midterm-prior-propagation-b`；分支 `research/midterm-prior-propagation-b`。
- Git外原始目录 `/home/ubuntu22/uwb-midterm-prior-propagation-b-artifacts/run`，含480输入及1920阶段，运行日志/锁/事件保留。只读PR108工作区 `/home/ubuntu22/uwb-pr108-propagation-readonly`。
- 新增960方法运行（952接受、8未驻点、0不可用、0预算耗尽/异常/警告）；另旧结果1200对（2400端点，基准8/目标10未接受）。全部计划已完成，无待补运行。

## 建议验收（不启动求解）

在仓库根目录，将PY设为Python3.10.12且NumPy2.2.6/SciPy1.15.3的独立venv，输出目录必须不存在：

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PY=/path/to/venv/bin/python
$PY tools/midterm_prior_propagation_b/analyze.py \
  --archive docs/research/midterm_prior_propagation_b/results/EVIDENCE.jsonl.gz \
  --out /tmp/prior-propagation-readback
cmp /tmp/prior-propagation-readback/SUMMARY.csv docs/research/midterm_prior_propagation_b/results/SUMMARY.csv
cmp /tmp/prior-propagation-readback/PER_PAIR.csv docs/research/midterm_prior_propagation_b/results/PER_PAIR.csv
$PY tools/midterm_prior_propagation_b/supplement.py \
  --archive docs/research/midterm_prior_propagation_b/results/EVIDENCE.jsonl.gz \
  --rows /tmp/prior-propagation-readback/PER_PAIR.csv --out /tmp/prior-propagation-subsets
$PY tools/midterm_prior_propagation_b/acceptance.py --out /tmp/prior-propagation-acceptance
```

最后一项验证冻结/交付哈希，并在独立人工副本中将一个B0终点设为缺失，检查完整分母和汇总链路；不改主证据或主统计，不调用优化器。可用状态重建包括cost、物理梯度、MSE；新阶段另核残差。未接受但有限仍复核；不可用状态保留为空。

`SHA256SUMS.json`覆盖交付工具和文档/表/图/归档，排除自身及最终验收回执results/ACCEPTANCE.json以避免循环哈希。FREEZE_MANIFEST同时约束旧数学依赖与四个PR109证据分片；EVIDENCE_INVENTORY列现场资料逐文件固定提交与SHA。冻结HEAD元数据嵌在便携EVIDENCE首条META。

## 结果读取

- PER_PAIR：每个方法配对×车辆×3预测视图；不能把多行增加为样本n。
- SUMMARY：完整条件分母、所有有限结果、预测误差及MSE差seed区间。
- ACCEPTED_PAIR_SUMMARY：两端均数值接受子集，明确标注分母。
- FAILURES：目标端点；ALL_ENDPOINT_FAILURES：两端所有未接受比较记录，重复基准不是新的失败个体。
- EVIDENCE.jsonl.gz：可携带压缩输入、基准/目标状态、新P0/P1残差和阶段状态，约18MB；无需Git外原始目录即可读回。
- REPORT/EVIDENCE/MATH/DECISION_MEMO分别回答证据缺口、局部公式、适用范围和后续方向。

本轮只有假设敏感性范围，不提供真实平台可信先验上界、保护级或HMI风险保证。已知结果后的探索性旧seed复用不能称独立确认。不会自动合并PR，也不要求现场重新采集。
