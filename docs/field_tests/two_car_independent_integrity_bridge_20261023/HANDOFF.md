# 双车数据上的独立单车因果定位与完好性监测衔接试验

实际仓库：`/home/ubuntu22/双车协同/uwb-coop-localization-ros1`；冻结基点：`5ced063043c264618d15ae6cd47b98d2487500b4`。
分支：`experiment/two-car-independent-integrity-bridge-20261023`。实际实验目录：`/home/ubuntu22/双车协同/uwb-coop-localization-ros1/docs/field_tests/two_car_independent_integrity_bridge_20261023`。
状态：{"completed": 6}；正式最多6条，不含单元测试夹具。

先读 README.md、protocol.json 和 results/CONCLUSION_ZH.md。原 PR38/39/40 产物不修改。
从实际仓库根目录恢复核对（只读，不重跑）：

```bash
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 tools/run_two_car_independent_integrity.py --experiment '/home/ubuntu22/双车协同/uwb-coop-localization-ros1/docs/field_tests/two_car_independent_integrity_bridge_20261023' --resume-only
```

若存在 planned 项且源码/配置/输入哈希仍匹配，使用同一路径的 `--run` 只运行尚未开始项。
running/failed/timeout 项保留部分产物并停止自动重试；不得覆盖或增加运行预算。
报告复现仅用归档更新记录，不启动估计器：`python3 tools/report_two_car_independent_integrity.py --experiment '/home/ubuntu22/双车协同/uwb-coop-localization-ros1/docs/field_tests/two_car_independent_integrity_bridge_20261023' --output <项目内尚不存在的新目录>`。
源码/配置不匹配必须另起版本；不得重新选阈值、拟合动态终点、加入peer因子或真实车控制。
6项完成后停止扩展，提交指导窗口审核；没有推送或合并授权。

## 本轮收尾

六条正式回放全部完成，508次发布、2032条独立排除记录及36766条原始header记录通过独立审核。11项适配测试与37项原单车测试通过；实际执行一次`--resume-only`，新启动估计器为0。总进程13.053秒，最大单条2.818秒，无正式超时/失败。一次标定浮点精确相等预检停止已保留；定位仍使用PR38原始完整精度标定值。

本阶段无剩余回放，不再扩大试验。另一窗口新三包N10专项报告尚未发现，待指导窗口对照；现有PR38/39对应表已完成，不猜测物理故障。先读`results/CONCLUSION_ZH.md`和`results/INTERPRETATION_ZH.md`。数据/配置/源码锁与最终产物哈希分别见`source_lock.json`、`final_source_hashes.json`和`ARTIFACT_SHA256SUMS.txt`。

独立审核命令（不启动估计器）：

```bash
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_two_car_independent_integrity.py --experiment '/home/ubuntu22/双车协同/uwb-coop-localization-ros1/docs/field_tests/two_car_independent_integrity_bridge_20261023'
```

本地交付提交号从仓库执行`git rev-parse HEAD`读取；冻结科学基点仍为上文PR40提交，不混为同一个版本。
