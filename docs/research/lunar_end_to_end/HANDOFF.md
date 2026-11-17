# 交接

仓库新工作树 `/home/ubuntu22/uwb-lunar-end-to-end-validation`，分支 `research/lunar-end-to-end-validation`；独立运行资产 `/home/ubuntu22/uwb-lunar-end-to-end-artifacts`。旧PR125/130源目录只读使用、旧结果未覆盖；A/B任务未等待或修改。

冻结SHA：`9f7fb56d68b0f45394e7443159f0270fccb75426`；源SHA和完整文件哈希见FREEZE.json。最终交付HEAD由PR及提交记录确定，不在提交内自引用自己的SHA。不要在最终交付HEAD直接重启runner：它严格要求冻结HEAD且拒绝已存在attempt。

无需优化器的读回：在仓库根目录执行

```bash
python tools/lunar_end_to_end/checker.py docs/research/lunar_end_to_end/portable_results.tar.gz --output /tmp/lunar-readback.json
```

只需Python与numpy；本机隔离环境为 `/home/ubuntu22/uwb-lunar-end-to-end-artifacts/venv/bin/python`。归档包括观测、reference、结果、阶段端点、attempt、冻结输入清单、地形数组、报告、图表和USD；实际解包并核验的收据见INDEPENDENT_CHECK。SHA256SUMS独立覆盖交付目录（自身除外）。

完成：来源链、10帧地形、固定窗口、观测失配与小规模敏感性、开发校验、冻结、2160正式方法、全分母评价、独立读回、CPU场景导出、中期摘要、A/B接口。未完成且明确保留：GPU/Isaac实际回放、真实轮地/月壤动力学、实物时间/外参/噪声标定、第二独立序列；不妨碍已完成的CPU研究链，但不能宣称完整物理仿真已验证。

结果主入口REPORT.md；汇报复用TECHNICAL_SUMMARY.md；下一步优先项见DECISION_MEMO.md。普通PR不自动合并。
