# A端不确定性一致性分析

核心入口：[REPORT](REPORT.md)、[THEORY](THEORY.md)、[中期中文初稿](REPORT_DRAFT_ZH.md)、[证据映射](EVIDENCE_MAP.csv)。全部分析已完成；仅分析保存状态，不重新拟合7200次定位。

固定源码起点：`fba539052f3ce2ed7d2ed35e79ac03198200c680`。
先提交的分析协议：`0788d4a86456bef37fac305e37e8495ec8f59a2a`。
输入：`docs/research/midterm_simulation_confirmation/results/ESTIMATES.jsonl.gz`，SHA256 `c1986afdd26a4e38c8807a6bdffb2d182745ba21f9a0435f446661fefe10635f`；配置和冻结代码SHA见results/RECOVERY.json。来源固定，不跟踪main变化。

## 环境与隔离

初始实际目录 `/home/ubuntu22/双车协同/uwb-coop-localization-ros1`，分支 `experiment/two-car-independent-integrity-bridge-20261023`，完整HEAD `115b17deb2f848e596d1638a0b45cf360deae947`，git status为空；remote为 `https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git`。检查祖先及固定树未找到适用AGENTS.md。初始可用空间约36GB，任务后34GB。进程检查在当前沙箱命名空间仅见执行工具/检查进程，不声称检查了宿主所有进程。未操作实车服务或其他工作树。

独立工作树 `/home/ubuntu22/uwb-midterm-uncertainty-a`，分支 `research/midterm-uncertainty-a`。独立venv及中间数据在 `/home/ubuntu22/uwb-midterm-uncertainty-a-artifacts/`。Python3.10.12、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9；未使用系统SciPy1.8.0与NumPy2.2.6的不兼容组合。依赖见tools目录requirements.txt。只新增本任务两目录。

## 复现命令

从此分支仓库根目录执行；ART必须指向新的Git外目录。已有分析目录不覆盖。输入完全来自仓库，不依赖本机旧实验绝对路径。

```bash
export ART=/tmp/uwb-uncertainty-reproduction
mkdir -p "$ART"
python3 -m venv --without-pip "$ART/venv"
python3 -m pip --python "$ART/venv/bin/python" install -r tools/midterm_uncertainty_a/requirements.txt
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export UPY="$ART/venv/bin/python"
"$UPY" tools/midterm_uncertainty_a/check_formulas.py --out "$ART/formula-checks.json"
"$UPY" tools/midterm_uncertainty_a/check_summary.py > "$ART/summary-checks.json"
"$UPY" tools/midterm_uncertainty_a/check_interface.py > "$ART/interface-checks.json"
"$UPY" tools/midterm_uncertainty_a/analyze.py --out "$ART/run001"
"$UPY" tools/midterm_uncertainty_a/summarize.py --input "$ART/run001" --out "$ART/summary001"
"$UPY" tools/midterm_uncertainty_a/figures.py --input "$ART/run001" --summary "$ART/summary001" --out "$ART/summary001/figures002"
"$UPY" tools/midterm_uncertainty_a/verify_delivery.py
```

最后一条独立检查交付压缩数组、41472覆盖行与manifest；前面命令重建外部证据。实际执行使用上述脚本和 `/home/ubuntu22/uwb-midterm-uncertainty-a-artifacts`。图初版颜色条遮挡在figures002修正，仅改排版；交付检查初版因逐行重复解压NPZ运行过慢被终止，缓存数组后完成检查，统计规则不变。

`package_evidence.py --artifacts "$ART" --destination NEW_EMPTY_DELIVERY_DIR` 可向已创建的新空交付目录打包；不能向当前已有results目录重复运行。SHA256SUMS.json以仓库相对路径记录脚本、文档和证据（不含自身）。gzip/NPZ时间戳和PROVENANCE中的当前HEAD可因复现变化，比较数值与非压缩谱哈希，不要求整个运行目录逐字节相同。

## 文件与数据约定

- `results/RUNS.csv.gz`：7200记录，index对齐NPZ，包含unit/condition/seed/method/原数值标签。
- `results/MARGINALS.npz`：7200×3视图×12位置块的2×2边缘，三个分量xx/xy/yy、单位m²；q、位置误差(m)、B2偏差误差/方差、相关系数与失败原因。块顺序t0.car1,t0.car2,…,t5.car2；视图顺序total_curvature、fixed_prior_noise、data_only。非B2偏差字段NaN并标NOT_A_BIAS_METHOD，不能当缺失方法结果。
- `INFORMATION.csv.gz`：14400数据/总矩阵的秩、最小/最大奇异值、Jacobian条件数与阈值敏感性；完整终点谱在Git外SPECTRA.jsonl.gz可重建，哈希见EXTERNAL_EVIDENCE。REFERENCE_INFORMATION.json保留288个真值参考矩阵的完整谱和B2偏差投影信息。
- `COVERAGE.csv.gz`：41472行，36条件×4方法×3视图×2车×2水平×3子集×8汇总（六时刻、点平均、轨迹全覆盖）。planned为全计划分母，selected_planned为子集计划，unavailable不含未入选；covered/available与covered/planned分列。CI按50seed聚类，CSV空值代表null、不足或不适用，不能填0。
- `BIAS_COVERAGE.csv.gz`、`EMPIRICAL_MOMENTS.csv.gz`、`ASSOCIATIONS.csv.gz`：偏差区间/耦合、逐车逐时刻经验矩、跨seed描述性相关。相关无多重比较显著性主张。
- `PRIOR_COMPARISONS.csv`、`NOT_STATIONARY.csv`：全部方法先验配对对照、25条原未驻点结果。
- `figures/`：95/99全部条件覆盖、误差/尺度、强先验、偏差/耦合、代表案例共6张图，标注单位与分母。
- `RECOVERY/CHECKS/SUMMARY_CHECKS/DELIVERY_CHECKS`及三个小例checks：真实执行证据。PROVENANCE保留分析开始时HEAD及脚本字节哈希（当时新代码尚未提交）；最终代码由交付SHA256SUMS另外固定。DELIVERY_CHECKS是在manifest生成前的数值核验，故其manifest计数为0；最终manifest校验命令另行运行，避免自引用。

核心与附加分开：DIAGNOSTIC_INTERFACE、NOISE_MISMATCH_THEORY、FAILURE_CASEBOOK、FUTURE_RESEARCH是附加储备。接口外层不改变主批次矩阵计算。所有结果是已暴露仿真的探索分析，无新增算法、正式seed、保护级或HMI保证。
