# Moon_1 定位接口与短窗口验证

本交付是 CPU 数值定位冒烟验证，全部采用 **height-oracle**，未启动 Isaac/GUI/车辆动力学。
接口与12次无噪声验收通过；带噪180/180完成，169接受、11未通过冻结梯度门槛。formal_runs=0。

- [协议](INPUT_PROTOCOL.md)、[配置与固定seed](CONFIG.json)、[数值配置](SOLVER.json)
- [报告](REPORT.md)、[决策](DECISION_MEMO.md)、[交接与物理仿真接口](HANDOFF.md)
- [环境](ENVIRONMENT.md)、[参数来源](PARAMETERS.md)、[测试与命令](TESTS.md)
- [冻结回执](results/FREEZE.json)、[输入与代码哈希](results/MANIFEST.json)、[无噪声](results/ACCEPTANCE.json)、[独立读回](results/READBACK.json)
- [逐运行指标](results/PER_RUN.csv)、[逐窗汇总](results/SUMMARY.csv)、[双方接受配对汇总](results/PAIRED_ACCEPTED.csv)、[条件配对差](results/CONTRASTS.csv)、[完整状态](results/STATUS_ALL.csv)

## 无大型资产读回

在仓库根目录，以独立环境安装 requirements.txt 中的固定版本。不要修改共享环境。

```bash
python3 -m venv /tmp/moon1-eval-venv
/tmp/moon1-eval-venv/bin/python -m pip install -r tools/moon1_localization_eval/requirements.txt
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 /tmp/moon1-eval-venv/bin/python tools/moon1_localization_eval/readback.py --input docs/research/moon1_localization_eval/results --out /tmp/moon1-eval-readback-new
```

输出目录须不存在。读回不调用优化器，不需要原始PLY、GT或NPZ；压缩包是分开的JSON对象映射（键为unit/method文件名去掉.json）。
measurements没有参考轨迹或故障标签，reference只供评价，estimates保留全部180个有限状态、梯度及局部协方差。
不是只保存有利运行；PNG固定显示第一个seed，部分曲线数值状态未接受，须结合STATUS_ALL读取。

## 完整重生成

本次数值代码冻结于 `e235299f804207421a6713bae25a2c39aa420b01`，最终交付仅添加证据与文字。
使用该提交的独立干净checkout，按TESTS命令先验收再batch；每次使用新输出目录。
需要PR114新资产 `moon1_scene.npz`，SHA256 `ac283d70505a5c1f4869dbb7be84af88041de2d74bf56dcfc2360bcb513de97f`（114428字节）。
通过PR114 README和RUN中的来源/命令重新生成或由资产持有人提供此文件；本PR不重新下载数据、不覆盖或重复提交资产。
路径是本机历史运行记录，不假设另一主机存在。

原始批次9.2MiB保存在Git外；交付压缩证据约3.4MiB。RUN记录原文件哈希，MANIFEST记录交付文件哈希。
解压对象后用 `json.dumps(obj, indent=2, allow_nan=False) + "\n"` 恢复原文件字节，可以验证RUN的文件哈希。
