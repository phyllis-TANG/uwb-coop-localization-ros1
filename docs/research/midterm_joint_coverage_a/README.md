# A端：故障与噪声失配的覆盖分析

已完成两批全部保存结果，未重新定位。入口：[REPORT](REPORT.md)、[中期新增段落](REPORT_DRAFT_ZH.md)、[决策建议](DECISION_MEMO.md)、[矩阵定义](MATRIX_DEFINITIONS.md)、[交接](HANDOFF.md)。分析前固定的协议和配置为ANALYSIS_PROTOCOL.md、CONFIG.json；这是已暴露结果的探索分析。

## 环境和来源

初始cwd=/home/ubuntu22；检查的已有A工作树为/home/ubuntu22/uwb-midterm-uncertainty-a，分支research/midterm-uncertainty-a，完整HEAD d39c99589bd15938484d64871981d45a9dd74efe，git status为空，remote为本GitHub仓库。祖先路径及固定源码树未找到适用AGENTS.md；可用磁盘约33GB；ps仅能看到当前沙箱命名空间的执行进程，不声称宿主无其他任务。

新建工作树/home/ubuntu22/uwb-midterm-joint-coverage-a，分支research/midterm-joint-coverage-a，起点完整SHA **764064f224ada7e793430bd47f5122a14b8d1f30**，未追踪或合并移动main。协议先提交 **9b885e9fea0eb594479ecd48a4d4b7b88e681765**。新venv在/home/ubuntu22/uwb-midterm-joint-coverage-a-artifacts/venv；Python3.10.12、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9，BLAS/OMP线程1。精确包需求在tools/midterm_joint_coverage_a/requirements.txt，实际版本在results/ENVIRONMENT.json。

源输入为仓库docs/research/midterm_mismatch_b/results/EVIDENCE-*.jsonl.gz及noise_exploration/results/EVIDENCE-*.jsonl.gz，不依赖其他机器绝对路径。B源冻结分别41653fff74255a3222b49933947f31c497640e0f、54ac42b60a11a0666e8840cf5bd8417a02a677e1。父目录的HANDOFF及SHA256SUMS覆盖两批；噪声子目录的README有生成前的历史说明，实际完成状态按RUN/清单/分片核验，不将旧文字当当前未执行。

## 实际完成与检查

|批次|条件×seed×方法|接受/未驻点/预算|每视图计划位置点|可用位置点|
|---|---:|---:|---:|---:|
|fault|72×100×4=28800|28419/367/14|345600|345600|
|noise|72×50×4=14400|14047/333/20|172800|172800|

各批独立n=100/50，车辆/时间点/方法/条件共享seed不能扩大n。每批288组独立矩阵交叉检查、110592位置覆盖行与1728偏差表行独立复算；代价/梯度重算差0，q显式公式相对差<3e-15。全部未接受结果保留。原型校验只求r/J，不调用优化器；工具导入时显式禁止scipy.optimize.least_squares。故障仅2400条B2具有真常b定义，噪声3600条均适用；其余偏差覆盖为空，不把注入均值当真b。

## 完整复现命令

在最终交付分支的仓库根执行，ART选择新的Git外目录。不要切回固定起点后期待那里已有本轮新增脚本。若浅克隆缺少B历史Git对象，先按完整SHA fetch这两个冻结提交供字节审计，不合并。

```bash
export ART=/tmp/uwb-joint-coverage-reproduction
mkdir -p "$ART"
python3 -m venv --without-pip "$ART/venv"
python3 -m pip --python "$ART/venv/bin/python" install -r tools/midterm_joint_coverage_a/requirements.txt
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export JPY="$ART/venv/bin/python"
"$JPY" tools/midterm_joint_coverage_a/audit.py --out "$ART/source001"
"$JPY" tools/midterm_joint_coverage_a/checks.py --out "$ART/FORMULA_CHECKS.json"
for batch in fault noise; do
  "$JPY" tools/midterm_joint_coverage_a/analyze.py --batch "$batch" --source-checks "$ART/source001/SOURCE_CHECKS.json" --out "$ART/$batch"
  "$JPY" tools/midterm_joint_coverage_a/summarize.py --batch "$batch" --input "$ART/$batch" --out "$ART/$batch-summary-final"
  "$JPY" tools/midterm_joint_coverage_a/figures.py --batch "$batch" --input "$ART/$batch" --summary "$ART/$batch-summary-final" --out "$ART/$batch-figures-final"
  "$JPY" tools/midterm_joint_coverage_a/verify.py --batch "$batch" --input "$ART/$batch" --summary "$ART/$batch-summary-final" --out "$ART/$batch-independent-checks.json"
done
```

实际执行使用同样入口、/home/ubuntu22/uwb-midterm-joint-coverage-a-artifacts根；故障图目录名为fault-figures，噪声最终图noise-figures-final；其它对应source001、fault/noise、fault-summary-final/noise-summary-final。执行中开发问题和版本差异见HANDOFF，非定位重新运行。package.py是本轮执行目录的打包工具，使用上述实际目录名；一般复现无需重新打包进仓库。

分析中断恢复（只对Git外完整分析目录使用）：

```bash
"$JPY" tools/midterm_joint_coverage_a/analyze.py --batch noise --source-checks "$ART/source001/SOURCE_CHECKS.json" --out "$ART/noise" --resume
```

完整片逐一核验源码/源分片/输出哈希后跳过；不完整片移到带时间后缀目录保留，再重新计算该**分析片**，不求解定位。源码哈希改变则拒绝继续，使用原执行版本或新的输出目录。源证据不匹配时audit保存SOURCE_FAILURE.json并停止依赖分析；本轮没有这种来源损坏。

## 直接检查已交付证据

不必重建全批矩阵即可独立读回：

```bash
for batch in fault noise; do
  "$JPY" tools/midterm_joint_coverage_a/verify.py --batch "$batch" --input "docs/research/midterm_joint_coverage_a/results/$batch" --summary "docs/research/midterm_joint_coverage_a/results/$batch/summary" --out "$ART/delivery-$batch-checks.json"
done
"$JPY" tools/midterm_joint_coverage_a/verify_hashes.py
```

输出拒绝覆盖，需新路径。SHA256SUMS以仓库相对路径记录本任务全部交付文件（清单自身除外）；每片DONE记录实际执行源码字节哈希与源EVIDENCE哈希。容器gzip/NPZ时间戳可能因重建变化，数值可独立比较；完整谱在Git外，EXTERNAL_SPECTRA记录哈希，可用分析入口重建。

## 证据字段与图表

每批results/{batch}/shard-NNN/含：

- RUNS.csv.gz：每条方法的身份、条件、seed、原数值分类、代价/梯度、数据/总残差RMS、逐车MSE、bias适用性。index为**片内行号**，用shard+index关联，不跨片猜索引。
- POINTS.npz：covariance形状(N,3,12,3)，视图[A_total,B_iid,C_true_noise]，块[t0.car1,t0.car2,…,t5.car2]，分量[xx,xy,yy]、单位m²；error(N,12,2)单位m；q(N,3,12)；reason同形。另存bias_variance、bias_q、bias_error、bias_eligible；无真常b时q/error为NaN，代表不适用而非缺失定位。半轴/面积可按MATRIX_DEFINITIONS从边缘无损重建。
- INFORMATION.csv.gz：data/total的秩、维数、最小/最大奇异值、尺度化Jacobian条件数、阈值敏感性和不可用原因。完整谱SPECTRA.npz只留Git外。
- CHECKS.json、DONE.json：分片核验与来源/输出哈希；部分代码最初在协议提交后未提交状态执行，字节哈希与后续对应提交在HANDOFF明确，不能只看analysis_head推断全部执行代码。

summary/COVERAGE.csv.gz保留每表全计划planned、子集selected_planned、not_selected、available、unavailable、covered，两种覆盖比及CI状态。all_times按整条六时刻轨迹为一个事件，unavailable_point_reasons仍按底层点说明，不能与轨迹不可用数混读。CSV空值=null/不足/不适用，不能填0。偏差表另外用eligible_planned、not_applicable区分模型无真常b与数值不可用。

MOMENTS提供逐车逐时刻经验均值、中心协方差、MSE、预测trace、q、95/99面积与长短半轴；PAIRED提供B2−B1/B0、C−B/A及噪声相对iid004对照、双方接受子集和配对分母；ASSOCIATIONS为描述性相关；FAILURES保留734条两批未接受记录（分表存，不合并推断）。CASES按协议各类最大C q选，不作为概率样本。

figures/fault与figures/noise共7张图：全部条件95/99点态覆盖、误差—尺度、噪声解释对比。白+为未驻点，红x/标题x为预算耗尽，!为不可用；标题写明计划分母、相关性和离线参照。DESCRIPTIVE是条件等权摘要，没有跨条件堆叠CI。所有偏差模型/噪声标签都保留，没有只画有利场景。

此交付不声称保护级、HMI、实车或罕见风险保证。下一步优先级及否证条件见DECISION_MEMO。
