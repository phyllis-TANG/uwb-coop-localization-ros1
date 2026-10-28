# 执行记录与回读命令

实际工作目录`/home/ubuntu22/uwb-peer-dcs-minimal-20261028`；解释器`/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python`。环境`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`，TMPDIR在本任务Git外tmp，制图MPLCONFIGDIR也在该tmp。下列列出执行程序/参数；重定向日志路径及run.json保留执行证据，不应再次执行run补结果。

```bash
python tools/cooperative_dcs_probe_20261028/prepare.py --old /home/ubuntu22/uwb-peer-gate-probe-20261028-artifacts --output /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/evidence-v1
python tools/cooperative_dcs_probe_20261028/test_contract.py
python -m unittest discover -s tools/two_car_fixed_lag_fgo_v1 -p 'test_*.py' -v
python tools/cooperative_dcs_probe_20261028/run_matrix.py freeze --root /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/evidence-v1 --test-log /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/tests-v3/contracts.log --frozen-log /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/tests-v1/frozen-f0.log
python tools/cooperative_dcs_probe_20261028/run_matrix.py run --root /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/evidence-v1
python tools/cooperative_dcs_probe_20261028/evaluate.py --matrix /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/evidence-v1 --output /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/evaluation-v1
python tools/cooperative_dcs_probe_20261028/present.py --evaluation /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/evaluation-v1 --matrix /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/evidence-v1 --output /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/presentation-v1
python tools/cooperative_dcs_probe_20261028/pack.py --artifacts /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts --output /home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/archives-v1
```

freeze/run的实际argv和输入/源码身份见RUN_PLAN与各run.json；测试日志见review，v1/v2/v3原日志在归档。作者PDF来自LITERATURE.json的URL，下载原文件SHA固定；无bag/视频下载。

可迁移回读只运行解包后的`delivery-source-v1/tools/cooperative_dcs_probe_20261028/evaluate.py --matrix <解包根>/evidence-v1 --output <全新输出目录>`，随后present.py使用该评价输出；不运行在线求解器。源码路径保持归档层级，独立audit由相同相对根解析。完整逐文件MANIFEST和归档SHA先核对，portable回读记录另见ARTIFACTS.json/review。
