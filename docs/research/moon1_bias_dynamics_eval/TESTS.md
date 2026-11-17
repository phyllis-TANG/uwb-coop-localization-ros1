# 命令、验收与调用记账

实际cwd `/home/ubuntu22/uwb-moon1-numerics-timevarying-bias`。
下列变量仅缩短显示；FREEZE、attempt与dispatch保存实际完整命令/配置/代码身份。

```bash
PY=/home/ubuntu22/uwb-moon1-numerics-timevarying-bias-artifacts/venv/bin/python
ART=/home/ubuntu22/uwb-moon1-numerics-timevarying-bias-artifacts
DOC=docs/research/moon1_bias_dynamics_eval
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
"$PY" tools/moon1_bias_dynamics_eval/diagnose.py --out "$ART/diagnosis001"
"$PY" tools/moon1_bias_dynamics_eval/durable_checks.py --out "$ART/durable001"
# 在02af736734e272cd524cf38afb9991bb0b240f48干净checkout执行：
"$PY" tools/moon1_bias_dynamics_eval/continue_endpoints.py --cases "$DOC/diagnosis/CASES.json" --out "$ART/continuation001" --freeze 02af736734e272cd524cf38afb9991bb0b240f48
# 下列开发和验收在最终探索冻结之前执行：
"$PY" tools/moon1_bias_dynamics_eval/checks.py --out "$ART/checks001"
"$PY" tools/moon1_bias_dynamics_eval/batch.py --mode smoke --out "$ART/smoke001"
"$PY" tools/moon1_bias_dynamics_eval/readback.py --input "$ART/smoke001" --out "$ART/smoke_readback001"
# 读回对P1异常时保留P0失败诊断的处理补全后，仅重做零优化器验收：
"$PY" tools/moon1_bias_dynamics_eval/checks.py --out "$ART/checks002"
# 在7a22287b199060b4a7a6c0b68ea4ba9f5953eef9干净checkout执行：
"$PY" tools/moon1_bias_dynamics_eval/batch.py --mode explore --out "$ART/explore001" --acceptance "$DOC/ACCEPTANCE.json" --freeze 7a22287b199060b4a7a6c0b68ea4ba9f5953eef9
"$PY" tools/moon1_bias_dynamics_eval/readback.py --input "$ART/explore001" --out "$ART/readback001"
"$PY" tools/moon1_bias_dynamics_eval/archive.py --input "$ART/explore001" --out "$DOC/results"
"$PY" tools/moon1_bias_dynamics_eval/readback.py --input "$DOC/results" --out "$ART/portable_readback001"
```

这些目录本机已存在，不再次执行覆盖。再生成需替换新输出目录，不得在已有attempt目录自动恢复运行。
测试工具导入SciPy函数定义，但公式验收/读回不会调用优化器；durable_checks只使用两个假求解器接入（一个正常返回、一个模拟中断）。

|项目|输入|结果|实际优化器调用|
|---|---|---|---:|
|旧端点独立公式重算|PR117全部180状态/观测|目标/梯度/信息/169与11分类一致|0|
|精确Hessian检查|11个未接受端点，中心差分1e−5|最大绝对差9.91e−7，正定|0|
|局部Newton/longdouble|同11端点|预测4.05–17.82nm，保存预测与试点评价|0|
|假求解器持久化|成功结果、孤立attempt、竞争锁|重复/中断后重跑/并发均拒绝|0|
|统一继续|11失败+11固定分层接受对照|2旧失败转接受，9仍未接受，11对照接受|22|
|输入/J/配对验收checks001和002|暴露seed及零噪声，三窗四条件|独立重建/中心差分/标签拒绝/真值零残差/M0不变/M2平移通过|0|
|开发冒烟|暴露seed911170101、w0、4条件×3方法|12方法、P0/P1共24，最终12接受|24|
|冻结探索|新10seed、3窗4条件3方法|360方法、720调用、349接受、11未接受，无孤立attempt|720|
|原始与便携完整读回|新结果+旧180+22继续|全部PASS；读回CSV及摘要逐字节一致|0|

无噪声验收仅在真值处评价目标，不新增无噪声优化调用；step/ramp保留预期非零残差。
开发24、任务一22、任务二720，实际总计766；formal_runs=0。
所有失败和阶段计数以attempt/dispatch/RUN为准，不拿nfev或窗口点数冒充优化器调用/独立seed。

## 精度与证据

输入验收J中心差分最大差1.59e−8（阈值2e−6）。完整读回最大J差1.94e−8，残差差0、梯度差5.69e−14。
归档2760个JSON可恢复原文件字节并验证SHA256。source/配置在任务二执行期间未改变。
同窗轨迹20条一致，源reference与固定提交哈希一致；这不代替NPZ或原始PLY来源复建。
源文件与所有交付证据的哈希见FREEZE、MANIFEST及DELIVERY_MANIFEST。静态检查只触及新增文件。
