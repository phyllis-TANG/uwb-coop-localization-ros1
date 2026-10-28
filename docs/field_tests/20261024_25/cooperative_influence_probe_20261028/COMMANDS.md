# 命令与阶段索引

实际工作目录`/home/ubuntu22/uwb-cooperative-influence-minimal-20261028`。解释器`/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python`，BLAS/OMP单线程，PYTHONDONTWRITEBYTECODE=1；结果和matplotlib缓存均在本任务Git外目录。以下python指该解释器。无conda/系统依赖改动、无ROS命令。

```bash
python tools/cooperative_influence_probe_20261028/prepare.py
python tools/cooperative_influence_probe_20261028/test_contract.py
python tools/cooperative_influence_probe_20261028/test_index.py
python -m unittest discover -s tools/two_car_fixed_lag_fgo_v1 -p 'test_*.py' -v
python -m unittest discover -s docs/field_tests/20261024_25/research_roadmap_20261028 -p 'test_analytic_mechanism.py' -v
python tools/cooperative_influence_probe_20261028/run_development.py freeze
python tools/cooperative_influence_probe_20261028/run_development.py run
python tools/cooperative_influence_probe_20261028/evaluate.py --root /home/ubuntu22/uwb-cooperative-influence-minimal-20261028-artifacts/evidence-v1 --output /home/ubuntu22/uwb-cooperative-influence-minimal-20261028-artifacts/evaluation-v1
python tools/cooperative_influence_probe_20261028/present.py --evaluation /home/ubuntu22/uwb-cooperative-influence-minimal-20261028-artifacts/evaluation-v1 --output /home/ubuntu22/uwb-cooperative-influence-minimal-20261028-artifacts/presentation-v1
python tools/cooperative_influence_probe_20261028/package.py
```

test_contract分v1失败、v2九项通过、v3十三项通过；各原日志与源版本保留，BUG_01解释分类修复。index测试单独1项，原F0 27项、解析7项。freeze在所有上述最终测试通过且源码本地提交后执行，run只一次。16单元全部完成，不因交付HEAD变化再执行run。

可迁移回读命令：`python <解包根>/delivery-source-v1/tools/cooperative_influence_probe_20261028/evaluate.py --root <解包根>/evidence-v1 --output <全新输出目录>`。读器没有在线solver/Jacobian依赖，不是重跑实验。必须保留归档相对源码目录，先核验归档与MANIFEST SHA。获取方式见ARTIFACTS.json；验证回执见review。

源码、输入与配置身份：RUN_PLAN/RUN_INDEX、INPUT_BINDINGS、FROZEN_CONFIG、READING_SOURCES、tools/source_lock.json；结果逐文件SHA在各run.json；全部交付文件校验见review/DELIVERY_FILES_SHA256.json。计时与dirty=true的真实文档状态见METHODS/CHECKPOINT_03，不改旧记录。

最终绑定/迁移/全姿态数值路径检查：

```bash
python tools/cooperative_influence_probe_20261028/verify_delivery.py --artifacts /home/ubuntu22/uwb-cooperative-influence-minimal-20261028-artifacts --output /home/ubuntu22/uwb-cooperative-influence-minimal-20261028-artifacts/delivery_verification.json
```
