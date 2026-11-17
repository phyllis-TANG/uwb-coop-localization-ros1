# A端：非线性误差分解与退化Gaussian区域

固定起点`f9c27436836b814afdea47945887015dcb55fca5`；分析合同冻结提交`8659412f0988a5cec95a118702287b8994ea379f`。仅新增本任务两目录，PR目标main，不合并。结果见[REPORT](REPORT.md)，推导见[MATH](MATH.md)，下一步见[DECISION_MEMO](DECISION_MEMO.md)。

已完整分析PR119的1200和PR121的600个保存最终端点。两批分别统计；115200新逐点区域记录、28800逐seed/车记录。新增观测0、非线性优化器调用0、Monte Carlo0。首时刻仿射秩1支持缺口已补齐，但非线性对照不继承保证。

## 环境与运行

实际工作树`/home/ubuntu22/uwb-midterm-nonlinear-decomposition-a`，分支`research/midterm-nonlinear-decomposition-a`。起始目录/home/ubuntu22不是Git仓库；原A树HEAD e35f94fb89a71236bd04c7f25fc318b016ba592d且干净。独立树从指定共同完整SHA建立，没有使用移动main。remote为https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git。未发现适用AGENTS.md。进程检查仅限本沙箱，未操作其他窗口；起始磁盘可用约34GB。

独立venv `/home/ubuntu22/uwb-midterm-nonlinear-decomposition-a-artifacts/venv`：Python3.10.12、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9；BLAS单线程。系统ensurepip不可用，使用uv安装到独立venv，未改全局环境。完整运行、中断诊断目录及便携交付前产物在同级Git外artifacts目录。

## 无优化复核命令

在仓库根执行；PY指向上述venv或用`uv venv --python python3.10 /tmp/decomposition-venv`及`uv pip install --python /tmp/decomposition-venv/bin/python -r docs/research/midterm_nonlinear_decomposition_a/requirements.txt`建立独立环境。输出目录必须不存在。

```bash
export PY=/home/ubuntu22/uwb-midterm-nonlinear-decomposition-a-artifacts/venv/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
sha256sum -c docs/research/midterm_nonlinear_decomposition_a/SHA256SUMS
$PY tools/midterm_nonlinear_decomposition_a/test_math.py --out /tmp/decomposition-tests.json
$PY tools/midterm_nonlinear_decomposition_a/analyze.py --out /tmp/decomposition-readback
$PY tools/midterm_nonlinear_decomposition_a/summarize.py --input /tmp/decomposition-readback --out /tmp/decomposition-summary
$PY tools/midterm_nonlinear_decomposition_a/verify.py --input /tmp/decomposition-readback --summary /tmp/decomposition-summary --out /tmp/decomposition-verify.json
$PY tools/midterm_nonlinear_decomposition_a/figures.py --input /tmp/decomposition-readback --summary /tmp/decomposition-summary --out /tmp/decomposition-figures
```

也可跳过重算，直接对交付表独立验收：

```bash
$PY tools/midterm_nonlinear_decomposition_a/verify.py --input docs/research/midterm_nonlinear_decomposition_a/results --summary docs/research/midterm_nonlinear_decomposition_a/results/summary --out /tmp/decomposition-portable-verify.json
```

入口不导入执行runner、不生成随机观测；运行时profile守卫拒绝scipy.optimize函数或观测生成器调用。直接SVD/QR与解析χ²分位数不计为非线性优化。SOURCE_HASHES以固定起点5211个tracked文件为核验范围；新目录不进入历史不变性范围。新增文件自身在SHA256SUMS中。

## 数据合同

- `DECOMPOSITION.csv.gz`：1800逐端点，保留batch、方法、seed、初值、数值标签、选择/终点组、偏移/先验、秩/条件数、重建误差；每项位置/逐车RMS、有符号及绝对偏差、真值和终点弱子空间大小。所有大小均在先定义状态尺度后计算，不根据数组长度猜方法。
- `VECTORS.jsonl.gz`：同顺序完整参考、ΔN、ΔL、三项状态向量、合成差、弱子空间、奇异值及原始梯度。三项顺序gradient/remainder/jacobian；位置24维，B2另b，B3无b；尺寸单位m，弱投影为缩放坐标。范数不可加，抵消另列。
- `REGION_MATRICES.jsonl.gz`：7200唯一位置块，含74列噪声响应G块、协方差、结构支持基、四维中心响应B和固定均值。单位m/m²；4维δ是同一个中心偏移，不是逐点独立偏移。
- `REGIONS.csv.gz`：115200行，每行含seed、车、时刻、偏移、rho、点态/联合、AFFINE或NL_COMPARE、秩、支持距离、覆盖、半径/面积、可用原因。`accepted/category`始终是对应**历史非线性端点**标签；AFFINE解均直接唯一，不把这些标签当仿射求解失败。接受子集表示按对应NL端点接受条件筛选。
- `noise_support`为rho0的真实支持集合，退化时面积0；`outer_circle`是Minkowski和的保守外包，不是精确集合成员判定。`radius`对noise_support是最大半径；rank0为单点。支持容差是数值检查，不是物理余量。
- `summary/DECOMPOSITION_SEEDS`先对同seed候选平均；`DECOMPOSITION_SUMMARY`的p025/p975是seed分布分位，不是置信区间。`ASSOCIATIONS`只是同条件seed描述关联。全部有限、接受、I0、selected、selected_group分别保留，不混淆条件化。
- `summary/REGION_SEEDS`的car=0表示双车12块，其余为各车6块；`REGION_SUMMARY`同时给全计划、子集、可用、覆盖及完整覆盖。`point95`的all_covered是经验合取；只有`joint95`且AFFINE、同一δ在球内等假设成立时有联合理论保证。`EPOCH_SUMMARY`给每时刻每车分母与秩。常量簇也不赋予罕见风险区间。
- `CHECKS/VERIFY/TESTS`为实际检查结果；历史4800条不可用未修改。`SOURCE_HASHES`记录全部固定来源，`SHA256SUMS`记录本轮精简交付。Git外中断目录不是证据来源。
