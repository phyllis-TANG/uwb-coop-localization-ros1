# 冻结执行后的验收修订 v1.1

正式执行及原始协议固定在12a1d94379b58c5a759b1698425fb90d48587609；本目录仅回读已有结果，不是新估计器或新阈值版本。v1执行的sources()只列根目录*.py/*.json，不包含本版本子目录；acceptance.json另行记录本目录Python的SHA。原始执行源码、协议、日志和原读器结果保持不变。

原check_matrix.py可检查已有子集但不足以单独证明完整矩阵。本修订严格检查预登记笛卡尔积、96个唯一运行、输入目录、状态网格、5664个发布、checkpoint DONE、指标/独立读器全集及原执行来源。明确记录existing_reader_subset_pass和complete_matrix_pass，空集合不得通过完整验收。生成全部文件哈希清单。

补充逐事件恢复试用起点、首次normal的回溯恢复起点、第三条连续normal实际可用时刻（在线确认），删失/未检出不填0。补充逐链可监测降权与unknown持有旧降权的分子/分母，不把分段当独立故障事件。实际发布时间误差补充参考覆盖/缺失、截止后总延迟及跨下一截止的积压数；不虚构纯排队/计算分离。

```bash
PYTHONDONTWRITEBYTECODE=1 python tools/single_car_quality_fgo/audit_v1_1/test_acceptance.py
PYTHONDONTWRITEBYTECODE=1 python tools/single_car_quality_fgo/audit_v1_1/acceptance.py --experiment /absolute/validation-v1 --readback /absolute/validation-readback-v1 --output /absolute/new-acceptance-v1_1
```

10项针对性测试覆盖完整、空/缺失子集、重复替代缺失、非零返回/失败、checkpoint未结束、额外运行、恢复起点≠确认、确认不足删失和unknown保持的独立分母。正式数据实际执行结果见报告与acceptance.json，不需要重跑估计器。
