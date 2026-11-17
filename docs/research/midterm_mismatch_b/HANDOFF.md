# A端及评审交接

两批独立冻结、独立统计；禁止把它们描述为共同预登记。两者均在读过历史结果后设计，分别在自己的观测生成前冻结。原公共代码、历史7200结果和原冻结数学目标未修改；不合并PR。

- 共同起点：`fba539052f3ce2ed7d2ed35e79ac03198200c680`。
- 故障压力测试冻结：`41653fff74255a3222b49933947f31c497640e0f`。
- 独立噪声探索冻结：`54ac42b60a11a0666e8840cf5bd8417a02a677e1`。
- 完整交付提交号由PR head/git rev-parse HEAD确定，避免文件自引用。

## 环境和运行

Python3.10，精确NumPy/SciPy见 requirements.txt；新建独立venv安装。运行前设置：

```sh
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
```

以下命令中的 python 必须来自该venv，且在仓库根执行。原始运行目录位于Git外 `/home/ubuntu22/uwb-midterm-mismatch-b-artifacts/fault-formal` 和 `noise-formal`。这两个已有目录拒绝覆盖。需要接续原始任务时，在对应冻结提交的独立checkout执行（不是交付HEAD）；加 `--resume` 只补尚未持久化阶段，已有失败也是完成。

```sh
python tools/midterm_mismatch_b/run.py --mode formal --freeze 41653fff74255a3222b49933947f31c497640e0f --out /绝对路径/原故障目录 --resume
python tools/midterm_mismatch_b/noise_run.py --mode formal --freeze 54ac42b60a11a0666e8840cf5bd8417a02a677e1 --out /绝对路径/原噪声目录 --resume
```

已经完整完成的批次不需再次执行定位。不能将同seed重放称为新验证。若仅复现，应另开目录、明确标注重放且不能增加样本量。

## 携带证据独立验收（不调用优化器）

交付checkout即可执行；输出路径必须尚不存在：

```sh
python tools/midterm_mismatch_b/readback.py --evidence docs/research/midterm_mismatch_b/results --out /tmp/fault-portable-audit.json
python tools/midterm_mismatch_b/noise_readback.py --evidence docs/research/midterm_mismatch_b/noise_exploration/results --out /tmp/noise-portable-audit.json
```

EVIDENCE分片包括完整观测、实际注入、真值供离线复核、P0/P1状态/估计/失败信息、配置、源码哈希和依赖；输入的6×9测量顺序、运动和prior信息足够重建完整J。Git外保留逐阶段r/J/梯度/局部信息与协方差；RAW_SHA256对应这些原始文件。精简归档中的信息矩阵状态保留，不把非有限协方差伪造为有限。SHA256SUMS.json核验交付文件字节。

若持有原始目录，可重建全表及审计矩阵，仍不调用优化器：

```sh
python tools/midterm_mismatch_b/readback.py --run /绝对路径/fault-formal --out /绝对路径/新fault-readback
python tools/midterm_mismatch_b/analyze.py --results /绝对路径/新fault-readback --out /绝对路径/新fault-analysis
python tools/midterm_mismatch_b/noise_readback.py --run /绝对路径/noise-formal --out /绝对路径/新noise-readback
python tools/midterm_mismatch_b/noise_analysis.py --results /绝对路径/新noise-readback --out /绝对路径/新noise-analysis
```

PER_RUN、FAILURES、NONACCEPTED、SUMMARY、PAIRED_INTERVALS和NOISE_CONTRASTS均为可独立读取的CSV。全分母主统计和接受子集分开；车辆、时刻、跨条件共享seed不能增加独立n。两个REPORT分别给出实际结果。没有HMI、保护级、长期故障检测或实车保证。

## 最终验收数量

故障批次完成28800/28800，数值未接受381（未驻点367、P1预算14）；噪声批次完成14400/14400，数值未接受353（未驻点333、P1预算20）。两批均无缺失或不可用估计；误差主统计保留全部有限结果。交付目录中的压缩分片已再次独立读回，分别核验57600及28800阶段，通过且未调用优化器。

数值未接受不是缺失；错误候选/多链路和相关噪声导致的大误差可以发生在数值已接受时。后续工作见两批各自NEXT_STEPS.md。
