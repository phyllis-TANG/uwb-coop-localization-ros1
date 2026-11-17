# A端：参考车不确定性与区域保证条件

固定共同起点：`30f9379249a4e695acf75910c40862a770e6f4ce`（已合并PR123/124）。数学合同、20项输入与执行代码冻结：`c190f072d7fd844aa1fc96fb09492faa2ece9256`。只新增本任务tools/docs目录，PR目标main，不自动合并。

已完成20项确定性检查（20 PASS、0意外FAIL，其中10项确认反例）、20行闭式敏感性矩阵及独立读回。正式优化器/搜索/随机调用均0，无新Monte Carlo，无旧定位器重跑。开发仅1个helper，首尝试的参数包装错误与修复单列保留。

阅读顺序：PROTOCOL → MATH → MODEL_CONTRACT → ASSUMPTION_REGISTER → VALIDATION_REPORT → DUAL_ROBOT_NEXT_SPEC → DECISION_MEMO/HANDOFF。来源见SOURCES，完整输入和输出在INPUTS.json及results。

核心结论：A1可以保持共享参考位置作联合nuisance，也可用有证明的逐行范围外包；不能一般地把多行几何误差吸收到同一个扩宽b。A2采用参考集合事件与原测距事件的交集，联合界不要求独立；有效覆盖前提仍必需。同数据派生估计不能当独立似然重复融合。一般正定R的数学表达已给出，但一般相关R的可信区间计算和完整双车求解器没有在本轮实现。

## 环境和隔离

原A工作树`/home/ubuntu22/uwb-midterm-nonlinear-decomposition-a`，HEAD f354cf5e370d4ffc54077b7280ca97638a8bd585，Git状态干净。新工作树`/home/ubuntu22/uwb-reference-uncertainty-contract-a`，分支research/reference-uncertainty-contract-a，从指定完整提交建立，未追踪main改变研究基准。remote=https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git。未发现适用AGENTS.md，起始空间约27GB；进程检查仅见沙箱内进程，不代表宿主机没有其他任务。其他窗口目录未改。

独立Git外根`/home/ubuntu22/uwb-reference-uncertainty-contract-a-artifacts`保存venv、开发和正式输出。Python3.10.12，NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9；正式精确算术/读回只用标准库，绘图用Matplotlib，NumPy/SciPy并未参与认证。没有安装求解后端。ENVIRONMENT.json记录实际版本和路径。

## 无优化复核

在仓库根目录执行，PY可为Python3.10。无需SciPy或NumPy即可核验结果：

```bash
export PY=/home/ubuntu22/uwb-reference-uncertainty-contract-a-artifacts/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
sha256sum -c docs/research/midterm_reference_uncertainty_a/SHA256SUMS
$PY tools/midterm_reference_uncertainty_a/check.py \
  --results docs/research/midterm_reference_uncertainty_a/results \
  --out /tmp/reference-contract-readback.json
$PY tools/midterm_reference_uncertainty_a/plot.py \
  --results docs/research/midterm_reference_uncertainty_a/results \
  --out /tmp/reference-contract-figures
```

读回逐一检查全部20项保存输入/记录、独立有理关系、阈值证书及20行敏感性结果；不会执行旧搜索/定位。输出路径须不存在，不覆盖旧检查。

本轮实际冻结后执行命令（已经完成；仅重建正式验证时需在冻结checkout执行）：

```bash
$PY tools/midterm_reference_uncertainty_a/validate.py \
  --freeze c190f072d7fd844aa1fc96fb09492faa2ece9256 \
  --out /home/ubuntu22/uwb-reference-uncertainty-contract-a-artifacts/validation
```

runner验证HEAD和冻结文件SHA，先核对历史快照，独占创建输出目录。若源损坏则停止；局部断言失败保存并继续独立项。交付后的常规验收用check.py，不需要重执行验证或checkout旧代码。

独立环境可用`python3 -m venv --without-pip /tmp/reference-contract-venv`建立；核心检查无需安装包。绘图可用`uv pip install --python /tmp/reference-contract-venv/bin/python matplotlib==3.10.9`。本轮环境已就绪，不修改公共Python环境。

## 输出语义

- `INPUTS.json`：20项完整有理输入、判据及20行矩阵参数，先冻结。没有随机seed。
- `results/T01…T20.json`、`RESULTS.json`：逐项原输入、实际输出和判定；COUNTEREXAMPLE_CONFIRMED表示预定错误命题被否定，不是定位失败被删掉。
- `SENSITIVITY.csv`：精确分数字符串，单位m；prediction是测距预测范围，不是二维位置区域。对称松弛与精确单行范围分别保存。
- `RUN.json`：冻结身份、计划/实际/失败数、原始输入digest、历史文件核验及零调用计数。
- `READBACK.json`：独立读回20项及20行矩阵的结果；读回不是新增实验。
- `SOURCE_HASHES.json`：全部5442个固定来源tracked文件哈希；`FREEZE_MANIFEST`固定7个核心文件；`SHA256SUMS`覆盖本轮全部交付（排除自身）。历史源码、原结果、正文和月球任务目录未改。

三角不等式、集合距离范围、联合事件及白化维数有解析证明；有限确定性检查只核对实现/展示反例，不能替代全域证明。当前不输出实车参考误差界、PL/HMI或罕见风险保证。
