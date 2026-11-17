# 测试命令、输入与结果

所有命令在 `/home/ubuntu22/uwb-moon1-localization-interface` 执行。下列变量仅缩短显示，回执ACCEPTANCE/COMMANDS保存完整argv。

```bash
PY=/home/ubuntu22/uwb-moon1-localization-interface-artifacts/venv/bin/python
ART=/home/ubuntu22/uwb-moon1-localization-interface-artifacts
SCENE=/home/ubuntu22/uwb-moon1-height-audit-20261117-artifacts/rebuild001/scene/moon1_scene.npz
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
"$PY" tools/moon1_localization_eval/checks.py --scene "$SCENE" --out "$ART/acceptance001"
# 此时提交冻结代码/配置/协议/验收，clean HEAD为以下SHA。
"$PY" tools/moon1_localization_eval/batch.py --scene "$SCENE" --out "$ART/batch001" --acceptance "$ART/acceptance001/ACCEPTANCE.json" --freeze e235299f804207421a6713bae25a2c39aa420b01
"$PY" tools/moon1_localization_eval/readback.py --input "$ART/batch001" --out "$ART/readback001"
"$PY" tools/moon1_localization_eval/readback.py --input docs/research/moon1_localization_eval/results --out "$ART/portable_readback001"
```

本次stdout/stderr重定向到ART下对应同名.log。新主机需替换路径、使用不存在的输出目录；不覆盖本轮证据。
完整重生成必须在数值冻结SHA的干净checkout执行。最终文档提交不改变数值源文件和协议；普通读回可在最终版本运行。

| 检查 | 输入 | 实际结果 | 实际优化器调用 |
|---|---|---|---:|
| 源码编译检查 | 新增7个Python文件 | 通过 | 0 |
| 无噪声匹配 | 实际PR114 NPZ，三窗，M0/M1/M2及M2+.3m | 12/12接受，最大位置分量误差4.09e−15m | 12 |
| 中心差分J | 固定初始化，步长1e−5 | 最大1.79e−8<2e−6 | 0 |
| 平面特例交叉 | 新模型对只读旧模型 | r/J差0 | 0 |
| 非法输入 | 缺字段、truth/quality、NaN、非法时间、零尺度、负测距 | 优化前INVALID_INPUT | 0 |
| 秩亏信息 | 零J、共线几何fixture | rank亏，covariance=null | 0 |
| 人工预算耗尽 | 实际窗口观测，max_nfev=1 | BUDGET_EXHAUSTED | 1 |
| 异常/非有限返回 | 两个人工optimizer stub | EXCEPTION/NONFINITE | 0（仅stub各1） |
| 输入隔离 | reference路径伪装为合法measurement | 普通CLI明确拒绝 | 0 |
| M0独立性 | 只改变peer距离 | 消费哈希、初值、目标及批次解不变 | 0额外 |
| 冻结带噪批次 | 3窗×4条件×5seed×3方法 | 180完成、169接受、11未接受；27.42s批次耗时 | 180 |
| Git外独立读回 | 60观测+60参考+180状态 | PASS，残差/梯度差0，J中心差分1.70e−8 | 0 |
| 压缩包独立读回 | 提交的三个分离JSON.gz | 同样PASS，无原始资产依赖 | 0 |
| 压缩恢复字节 | 三包对象按原indent=2恢复 | 与原始300个JSON逐字节一致 | 0 |

实际SciPy合计193=开发1+无噪声12+带噪180；没有新的非线性矩阵、P1或择优重跑。formal_runs=0。
人工fixture只证明接口/数值分支；原场景结论来自哈希匹配的PR114资产及三个实际窗口。
旧CSV不支持隐式直接求解，必须生成本协议measurement；缺少oracle高度等字段明确拒绝。

## 配对接受子集表的复算规则

从PER_RUN按(window,condition,method)分组，计划分母固定5；只对paired_accepted=True行计算
car1_rmse_m、car2_rmse_m、car1_benefit_m2、car2_benefit_m2的算术均值，空集留空。
paired_accepted要求同一unit的M0和当前方法都被接受；输出PAIRED_ACCEPTED.csv保留每组实际计数。
该子集用于透明诊断，不能隐藏STATUS_ALL的11个失败，也不能把跨组计数当新增seed。

生成证据压缩包时每种目录独立建立 {文件stem: JSON对象} 映射，gzip mtime=0；没有混入真值到measurement。
RUN记录原JSON哈希；MANIFEST记录交付文件SHA256与大小。源码哈希与FREEZE/ACCEPTANCE匹配，未在批次后改动。
