# P-S1b：偏差可辨识性分析 A 端

固定基准 `df323eccdffd375a2fb255ebbfd734b6c2be4aac`（PR97）。先读 REPORT.md；B 端使用 S2_INTERFACE.md。仅此目录及 tools/midterm_simulation_s1b 新增文件，没有修改定位后端、旧结果、设备或 PR97。

环境与隔离：初始工作区 `/home/ubuntu22/双车协同/uwb-coop-localization-ros1`，干净，分支 `experiment/two-car-independent-integrity-bridge-20261023`，HEAD `115b17deb2f848e596d1638a0b45cf360deae947`。origin 为 `https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git`。祖先目录及基准 Git 树未发现 AGENTS.md。当前进程命名空间未见其他任务进程；不能据此判断其他窗口。初查磁盘可用40GB，实验后约38GB。

实际独立 checkout：`/home/ubuntu22/uwb-midterm-s1b-identifiability-20261116-clean`；分支 `research/midterm-s1b-identifiability`，创建时远端无同名分支。GitHub 新克隆的稀疏 checkout，只展开所需基准目录；对象及索引独立。最初本地复制 `/home/ubuntu22/uwb-midterm-s1b-identifiability-20261116` 因源仓库缺失部分历史对象而放弃，未在该副本开展实验、提交或推送。该失败副本保留，原工作区未改动。GitHub只读查询发现PR97已处于MERGED状态，本任务没有合并或修改它，仍以固定提交为父基准。

Python：系统 `/usr/bin/python3` 3.10.12 的 NumPy2.2.6/SciPy1.8.0存在兼容警告，未用于拟合。独立环境 `/home/ubuntu22/uwb-midterm-s1b-artifacts-20261116/venv/bin/python`：Python3.10.12、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9。完整包版本在 tools/midterm_simulation_s1b/requirements.txt。系统 ensurepip 缺失，先生成 venv，再用宿主 pip 的 `--python` 安装；没有安装或修改系统包。

协议先冻结于 `005c78f3c466f6892b53ae7c34410ef177cee377`。配置SHA256 `8bbb68db376c4f86d42e66548daa8866151668db84c51be69478795c70e3b7cc`。计算时 HEAD 为冻结提交、analyze.py尚未提交；RUN.json同时绑定执行脚本SHA，该脚本随后原字节提交于 `b64a9c7ff0860f92159d392a608a3b7b07064c9f`，不将其误称计算时HEAD。全部为开发实验，不是盲确认。

复现命令（仓库根执行；OUT和PUB必须是尚不存在的新目录）：

```bash
python3 -m venv --without-pip /tmp/s1b-venv-new
python3 -m pip --python /tmp/s1b-venv-new/bin/python install -r tools/midterm_simulation_s1b/requirements.txt
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=
export MPLCONFIGDIR=/tmp/s1b-mpl-new
UWB_PY=/tmp/s1b-venv-new/bin/python
OUT=/tmp/s1b-run-new
PUB=/tmp/s1b-review-new
"$UWB_PY" tools/midterm_simulation_s1b/analyze.py --out "$OUT"
"$UWB_PY" tools/midterm_simulation_s1b/summarize.py --run "$OUT" --out "$PUB"
"$UWB_PY" tools/midterm_simulation_s1b/decompose.py --run "$OUT" --out "$PUB"
```

不要以已提交 results 为新输出位置。三个脚本均拒绝覆盖其输出。无需实测bag或硬件，基准 identifiability.py 只读导入作解析函数一致性核对。模型和估计器代码没有联网步骤。

结果入口：

- CONFIG.json/PROTOCOL.md（另有IMPLEMENTATION_CONSTANTS.json列明原实现常数，不改变冻结配置）：噪声、场景、种子、先验、初值、失败阈值及冻结矩阵。
- SOURCES.json：五份指定基准文件SHA；SEED_AUDIT.json、SEED_BASELINE_AUDIT.json：种子冲突检查及可访问范围。
- results/INFORMATION.json：76个信息矩阵的完整25维奇异谱、全部零空间、位置块谱及投影信息；SUMMARY版便于读表。
- results/PER_RUN.csv：2717次逐次结果；SUMMARY.csv按场景、噪声、变体汇总，包含逐车位置、偏差和四类失败率。
- results/PAIRED.csv、PAIRED_SUMMARY.csv：配对先验中心、强度和初值敏感度；每个噪声条件n=12，不把变体视为新重复。
- results/BIAS_DECOMPOSITION.csv：逐次“偏差误差=测距噪声−几何距离误差+残差”分解。
- results/OBSERVATIONS.jsonl.gz：247份观测、实际注入噪声、真值和锚点；truth仅用于生成、评价和明确标注的理想先验对照。
- results/CHECKS.json、READBACK.json、checks/：解析差分、退化反例、误差/代价重算、实际日志。
- results/EXTERNAL_INDEX.json：Git外 `/home/ubuntu22/uwb-midterm-s1b-artifacts-20261116/run001` 的逐文件SHA和大小。RAW.jsonl保留全部估计、初值、先验中心和求解器消息；可由命令重新生成。提交的谱、逐次指标和观测足以审查核心结论。
- SHA256SUMS.json：交付代码、证据和文档的内容索引（自身和后续HANDOFF不纳入，避免自引用）。

环境复查发现宿主shell继承ROS的PYTHONPATH，实际NumPy/SciPy/Matplotlib均来自独立venv。清空PYTHONPATH后按同一冻结矩阵完整回放，PER_RUN/INFORMATION/CHECKS/RAW逐字节一致；见checks/ISOLATION_REPLAY.json。回放不是新增seed或新统计证据。requirements仅登记独立venv安装包，未包含环境继承的ROS元数据。

扩展种子审计核对了固定基准174份登记/配置文本，36份非文本或大文件排除，未发现本批seed冲突；范围和每份SHA见SEED_BASELINE_AUDIT.json。该审计的第一次对象大小遍历在稀疏克隆中触发了非必要历史对象下载，已中止并改为只批量读取所选登记文本；没有扩大实验或更改seed。
