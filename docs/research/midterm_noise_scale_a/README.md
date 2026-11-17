# A端：噪声尺度与弱几何机制

固定起点：PR112 `cc3861bf054f96f88c381eb07f6f89b81ebf2618`。PR112已合并（merge `5e6e365b3c4e150a5146e18d3078daa19b823f14`）；本分支仍直接从固定起点建立，不吸收移动main。只增加tools/midterm_noise_scale_a与docs/research/midterm_noise_scale_a。

冻结提交：`c88571f51d7165f568847c9338005ddf4880addb`；正式执行提交：`e97f94e7824f6bc5450319b59d14d501b8482418`。先完成PR112无需优化的诊断和seed查重，再提交协议、配置、清单；之后开发冒烟并执行全部矩阵。

- 旧证据：48代表终点重新投影；缓存一次NPZ，6144覆盖行、720选优身份、3592接受/8未驻点与数值结果完全一致，0优化。
- 新实验：240输入、40新seed、2400方法初始化配置、4800阶段/实际优化器调用；2232接受、168未驻点，无预算耗尽/异常/缺失。开发另外60配置、120调用，56接受、4未驻点。
- 新证据：所有480个输入方法单元有选优候选，57600二维边缘（两视图）均可计算。未驻点仍保留，最低代价选择只用数值接受和代价。

主要结论见[REPORT](REPORT.md)、下一步见[DECISION_MEMO](DECISION_MEMO.md)。本轮为探索性机制研究；新seed不使它成为独立方法确认。降低噪声同步改变数据相对先验的信息强度。

## 环境与复核

工作树 `/home/ubuntu22/uwb-midterm-noise-scale-a`，分支research/midterm-noise-scale-a；原工作树clean，完整HEAD为固定PR112提交。remote=https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git。未发现适用AGENTS.md。Python3.10.12，NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9。开始约21GB可用，独立checkout/venv后约18GB。进程检查只可见沙箱，不宣称宿主机空闲。大体积阶段与venv在 `/home/ubuntu22/uwb-midterm-noise-scale-a-artifacts/`，便携复核不依赖该路径。

从仓库根运行，输出目录须不存在；不会覆盖历史结果：

```bash
python3 -m venv /tmp/noise-a-venv
/tmp/noise-a-venv/bin/pip install -r docs/research/midterm_noise_scale_a/requirements.txt
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
/tmp/noise-a-venv/bin/python tools/midterm_noise_scale_a/legacy_diagnostic.py --output /tmp/noise-a-legacy
/tmp/noise-a-venv/bin/python tools/midterm_noise_scale_a/readback.py --inputs docs/research/midterm_noise_scale_a/results/INPUTS.jsonl.gz --endpoints docs/research/midterm_noise_scale_a/results/ENDPOINTS.jsonl.gz --output /tmp/noise-a-readback
/tmp/noise-a-venv/bin/python tools/midterm_noise_scale_a/summarize.py --input /tmp/noise-a-readback --output /tmp/noise-a-summary
/tmp/noise-a-venv/bin/python tools/midterm_noise_scale_a/contrasts.py --input /tmp/noise-a-readback --output /tmp/noise-a-contrasts
/tmp/noise-a-venv/bin/python tools/midterm_noise_scale_a/final_checks.py --results docs/research/midterm_noise_scale_a/results --output /tmp/noise-a-final-checks.json
/tmp/noise-a-venv/bin/python tools/midterm_noise_scale_a/figures.py --results docs/research/midterm_noise_scale_a/results --output /tmp/noise-a-figures
```

上述命令均不优化、不生成新观测。final_checks仅导入冻结求解入口的目标定义做独立r/J/receipt核验，优化器调用0。NPZ通过cached_npz一次加载为内存字典，循环里不再访问压缩包。

实际求解命令（验收无须重跑）：

```bash
PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/ubuntu22/uwb-midterm-noise-scale-a-artifacts/venv/bin/python tools/midterm_noise_scale_a/run.py --output /home/ubuntu22/uwb-midterm-noise-scale-a-artifacts/formal
```

完整运行已完成，无剩余配置。执行入口核验CONTRACT，保存每阶段attempt和原子结果；已完成阶段跳过，残留attempt无结果则拒绝自动重试，须保留暴露记录调查。正式调用硬上限4800；开发120，不能以“继续收敛”为由追加。

## 证据合同

results/INPUTS.jsonl.gz：240输入含标准噪声、真实轨迹、注入、实际白化sigma、先验中心、五初值。truth仅用于生成与离线评价，初始化只用公开survey、锚点和观测位移。ENDPOINTS.jsonl.gz含2400配置两阶段精简记录、完整状态、代价、梯度范数、终止标签、nfev、时间、solver receipt哈希和调用数。

readback/ENDPOINT_METRICS.csv的index对应POINTS.npz第一维2400。q/trace/area95/reason=[2400,2,12]，视图0曲率/1固定先验噪声传播，12点按(t,car)；error=[2400,12,2]单位m；trace/area95单位m²；梯度与尺度梯度=[2400,25]，B3末维NaN为明确不适用。B2偏差方差/归一化误差=[2400,2]，B3同项NaN。状态排列与白化见PROTOCOL，不能靠长度推测模型。

WEAK_CURVATURE.csv给所有有限终点的弱子空间与整体范数；WEAK_SUBSPACES.jsonl.gz保存基与投影矩阵。基在尺度坐标中，符号任意；接近重根按子空间处理。本次所有实际端点k=1，但合成重根旋转验证覆盖k>1路径。

SELECTION/GROUPS/PAIRS保留配对、候选组、全部候选对；summary含覆盖/误差/配对/失败表。每条件每方法40seed，每车点平均240点，每方法200初始化配置。BRANCH中的additional_initialization_nfev仅I1–I4，其余总成本从逐次表求和。COVERAGE中全计划有效且覆盖与有效区间覆盖的CI明确分列；子集不作全样本提升。

contrasts/SEED_METRICS先以seed内组成员平均，再跨seed比较；NOISE_CONTRASTS主对比已在协议固定。multiple_groups与weak方向指标重复car行只是方便联表，两个car行不是两个独立检验。GROUP_SEEDS含95/99点态和六时刻全部覆盖；WITHIN_GROUP汇总表为主要95%曲率及噪声视图。

SOURCE_MANIFEST与SHA256SUMS记录来源与交付哈希，后者排除自身。全部复核指标能由便携输入/状态重建，完整r/J阶段留Git外。
