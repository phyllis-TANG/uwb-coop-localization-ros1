# B端交接与验收

## 固定来源与提交

起点PR111：`704842930f78da60836c7cf56d7a4fdb71b4aa39`。检查时其已是origin/main祖先，本轮从固定提交独立checkout，无merge/rebase，不依赖A端。分析冻结提交：`e843fb0cb494cd46fd853010119301b787c7f371`。交付SHA由最终Git提交和PR提供，文件内不写自身引用。

独立分支research/midterm-bias-region-b，工作区/home/ubuntu22/uwb-midterm-bias-region-b。结果目录/home/ubuntu22/uwb-midterm-bias-region-b-artifacts/analysis，venv在同一artifacts父目录。仅新增本研究两个目录，不修改原代码/证据/正文。

**formal_runs=0，真实优化器调用数=0。** 本轮复用2160条PAIR、3360唯一方法终点、1680配对输入；3334接受、26未驻点、0不可用终点。候选564480条逐点记录，554240可用、10240边缘奇异不可用；候选多行不是额外样本。

## 首选验收

Python3.10.12/NumPy2.2.6/SciPy1.15.3，图需Matplotlib3.10.9；根目录运行，输出路径必须不存在：

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PY=/path/to/venv/bin/python
$PY tools/midterm_bias_region_b/test_recovery.py --out /tmp/bias-region-recovery.json
$PY tools/midterm_bias_region_b/test_math.py --out /tmp/bias-region-math.json
$PY tools/midterm_bias_region_b/analyze.py --out /tmp/bias-region-recompute
$PY tools/midterm_bias_region_b/readback.py --results /tmp/bias-region-recompute --out /tmp/bias-region-verified.json
cmp /tmp/bias-region-recompute/SUMMARY.csv docs/research/midterm_bias_region_b/results/SUMMARY.csv
cmp /tmp/bias-region-recompute/PAIRED_DIFFERENCES.csv docs/research/midterm_bias_region_b/results/PAIRED_DIFFERENCES.csv
```

analyze对来源归档和冻结文件核验哈希。readback用独立未缩放QR算GN算子、直接H方程算精确噪声响应，再重算全部逐点覆盖/尺寸和逐seed聚合；不调用优化器。压缩CSV的gzip时间头可变，不比较压缩字节来判定数值一致；解压内容可比较。NPZ也以数组内容核验。

冻结verify.py原实现会在循环反复解压NPZ，首次只读核验因此停止，日志保留audit-slow-interrupted.log；新增readback.py只改加载策略、复用全部原断言，不改候选计算。无结果作废/重跑优化，没有根据覆盖反向调整配置。

## 数据与证据

Git内：压缩PER_SEED、LOCAL_MATRICES、ENDPOINTS、SUMMARY、PAIRED_DIFFERENCES、全部旧数值失败表、计数、独立核验、六幅全条件图、源码与冻结/交付哈希。Git外：完整POINTS.csv.gz约18MB及执行/核验日志；EXTERNAL_ARTIFACTS记录每个原始产物的SHA256和大小。固定旧输入在PR111便携归档，不重复复制。

重算POINTS不需要Git外目录，可完全从仓库内固定源生成。矩阵含每端点每车每时刻P、B与曲率视图，足够重建候选；真值、观测、原状态可通过ENDPOINTS身份回到固定归档。

## 后续运行器接入边界

仅recovery.py是供未来新运行使用的组件。identity必须由真实输入、解析配置及执行代码计算；P1实际起点与依赖版本也应纳入身份。已有失败只读恢复；attempt无结果拒绝自动调用；不确定状态没有清空重试入口。旧PR111 run.py不变，不能声称它获得了新保证。详见RECOVERY.md。

本批候选是明确假设下的局部表达，survey实际偏移全部不在5cm球内；正确中心弱几何仍需非线性/分支与有限样本分析。不提供HCPL、保护级或部署安全保证。下一轮600次B2机制面板只是DECISION_MEMO建议，本轮未运行。
