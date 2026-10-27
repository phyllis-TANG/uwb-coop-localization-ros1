# 单车20秒固定窗口FGO：逐链路UWB质量控制 v1

[中文结论和全部负结果](REPORT.md) · [完整验收/恢复/unknown分母](ACCEPTANCE_v1_1.md) · [一页交接](HANDOFF.md) · [实现和复现](METHODS.md) · [原生B接口](INTERFACE.md) · [B绑定](A_BINDING.json) · [结果归档与SHA](ARTIFACTS.json)

正式一次运行完成96/96、5664状态；120测试、96/96独立公式回读和v1.1完整矩阵验收通过。冻结执行12a1d94379b58c5a759b1698425fb90d48587609，交付新增验收单独版本，不改变原算法/协议/阈值。草稿[PR61](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/61)，未合并。

小型公开审阅文件在review；全量输入/图/账本/源码/失败日志只放Git外约294MB归档。NAS访问需LAN/VPN及授权挂载，不冒称公共下载；全部状态误差和质量时序压缩CSV可直接从本PR读取。all_truth_evaluation.csv.gz有5664数据行，factor_timeline.csv.gz有22656行；metrics.csv有96数据行，另1表头，开发32行独立保留在归档，不混入正式表。

```python
import gzip, csv
with gzip.open('review/all_truth_evaluation.csv.gz','rt') as f:
    states = list(csv.DictReader(f))
assert len(states) == 5664
```

主要结论：正常不降权但增加延迟；单链偏差可识别并缓解；共同测距故障可能漏检、健康链可能误降权，gyro/Odom问题与弱信息不因本策略自动改善。报告不把Huber既有作用算新增贡献，也不把工程分数称NIS、保护级或完好性保证。
