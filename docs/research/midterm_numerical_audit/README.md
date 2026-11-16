# A端：跨端独立核验与数值诊断

先读 REPORT.md、SOLVER_RECOMMENDATIONS.md；B端复现见 COMMON_PANEL.md，交接见 HANDOFF.md。
本轮仅增加 `tools/midterm_numerical_audit/` 和本目录。未改旧标签、公共后端或实车配置，未合并 PR，未使用正式新种子。

固定来源：

- A / PR99：`ed17e3ad177b5d52c1470e85da9f7a8645dbada9`
- B / PR98：`8174445e3b8e473bef15a82d345b7a7e1d94ac05`
- 共同原始基准 / PR97：`df323eccdffd375a2fb255ebbfd734b6c2be4aac`

原工作目录 `/home/ubuntu22/双车协同/uwb-coop-localization-ros1` 干净，HEAD 为 `115b17deb2f848e596d1638a0b45cf360deae947`，origin 为指定 GitHub 仓库。祖先目录与两固定提交完整树未找到 AGENTS.md。当前进程命名空间只见本轮命令，不能据此判断其他窗口。磁盘开始可用约40GB，checkout后约38GB。系统 Python3.10.12 / NumPy2.2.6 / SciPy1.8.0 不兼容，未用于求解。复用隔离 Python3.10.12 / NumPy2.2.6 / SciPy1.15.3，清空 PYTHONPATH，固定 BLAS 线程1；没有安装系统包。

独立工作树 `/home/ubuntu22/uwb-midterm-numerical-audit` 从 A 固定 SHA 创建，分支 `research/midterm-numerical-audit`（创建前本地无重名，推送前远端无同名）。B detached 工作树 `/home/ubuntu22/uwb-midterm-numerical-audit-b-source` 仅只读使用，禁写字节码；两工作树共享 Git 对象库但索引、工作文件独立。未等待B新结果。执行前阅读两边 REPORT、CONFIG、README、求解源码及三份指定接口/数学/协议文档。

## 产物

- `results/A_RECLASSIFIED.csv`：2717行，保留原CSV全部列，追加 audit 前缀列；其中主矩阵2574、负对照143。`audit_rank`为实际目标的终点总秩。
- `results/B_RECLASSIFIED.csv`：768个方法运行，保留原status/success和SciPy状态，新增复核；不是1536逐车独立实验。
- `checks/A_DATA_RANKS.csv`：A全部终点与参考点的数据+运动秩、阈值敏感性、偏差零空间与信息，与含先验总秩分开。
- `results/SAVED_AUDIT.json`：先完成的原结果只读审计汇总。未对旧矩阵重新定位；B generate只重建输入并核对保存哈希。
- `results/PANEL_CONFIG.json`、`PANEL_INPUTS.jsonl`：共同面板配置、全部观测、初值、先验中心、噪声、truth（仅生成/离线评价）、B3 oracle补偿及哈希。
- `results/PANEL_ORIGINAL.csv`、`B2_PARITY.csv`、`B2_ENDPOINTS.json`：128原协议求解、96初/终点评估，以及32对A/B完整位置和偏差。原始梯度、尺度梯度、代价和条件数保留。
- `results/CONTINUATION.csv`：128次固定继续迭代诊断，与原结果分开；不得覆盖旧标签或作为新独立样本。
- `checks/OFFLINE_PANEL_ERRORS.csv`：原始/继续迭代的逐车误差，仅离线评价。
- `checks/FINITE_DIFFERENCES.csv`、`CHECKS.json`：读回与192项白化Jacobian差分核验；不调用优化器。
- `results/SOURCES.json`、`SHA256SUMS.json`、`ENVIRONMENT.json`：固定源码/原证据字节校验、结果哈希和环境。
- `results/EXTERNAL_INDEX.json`：Git外 `.../uwb-midterm-numerical-audit-artifacts/run001/PANEL_DETAILS.jsonl`（约7MB），含逐次原结果/继续结果、A/B初终点完整残差/Jacobian/原始和尺度梯度。可用共同面板命令重新生成。

A原估计取自其固定提交 EXTERNAL_INDEX 所指向的原 RAW.jsonl；读取前校验全部5个外部文件SHA，不使用活动未锁定结果。外部RAW若不可用，不能声称完成全部A终点读回；共同面板独立复现不依赖它。

完整复核命令（仓库根；输出目录必须不存在，禁止删除旧结果凑路径）：

```bash
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
UWB_PY=/home/ubuntu22/uwb-midterm-s1b-artifacts-20261116/venv/bin/python
B_ROOT=/home/ubuntu22/uwb-midterm-numerical-audit-b-source
A_RAW=/home/ubuntu22/uwb-midterm-s1b-artifacts-20261116/run001
"$UWB_PY" tools/midterm_numerical_audit/audit.py \
  --b-root "$B_ROOT" --a-raw "$A_RAW" \
  --out /tmp/numerical-audit-new --large /tmp/numerical-audit-large-new
"$UWB_PY" tools/midterm_numerical_audit/verify.py \
  --b-root "$B_ROOT" --a-raw "$A_RAW" \
  --results /tmp/numerical-audit-new --large /tmp/numerical-audit-large-new \
  --out /tmp/numerical-audit-checks-new
```

本轮实际将上述输出写入本目录 results、checks 和 EXTERNAL_INDEX 的Git外目录。求解共128次B原协议、32次A独立实现、128次继续诊断；没有重复2717次旧矩阵。所有新口径都是事后复核/建议，不冒充旧预登记。输入与数值核验通过，最后提交前另检验变更范围、Git diff及B工作树未变。

汇总JSON中的历史字段名 `optimality_gt_1e5`、`saved_optimality_gt_1e5` 在本脚本实际比较的是 **`>1e-5`**（字段名省略了负号）；以源码阈值、逐行连续数值和本说明为准，不解释为大于100000。CSV `reference_data_rank`为离线参考点，`audit_rank`为实际目标终点总秩；二者不能直接用于判断prior以外的可辨识性。

CSV由Python标准csv模块生成，保留CRLF原字节以保持结果哈希。目录级.gitattributes仅将CSV声明为不转换换行、CR-at-EOL，不改变数据。首次提交检查识别此格式后补齐声明；首次提交因新工作树缺少作者身份未完成，随后使用A提交已有的Codex身份作单次提交参数，未修改全局Git配置。
