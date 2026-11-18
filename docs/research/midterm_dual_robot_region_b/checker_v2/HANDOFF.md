# B V2交接与无需搜索的复核

工作树 `/home/ubuntu22/uwb-dual-robot-region-b`，继续原分支 `research/dual-robot-region-b`，更新同一PR133。输出根 `/home/ubuntu22/uwb-dual-robot-region-b-artifacts/checker_v2_20261118`；旧输出不改。

冻结B：12894b821bf620587e5a4e154d83e23828e6cf4e。
A实现：b7b1d99903fa6adcfb6765c0adab57ab3660ae40。
A发布：50b592fbd672a1f19075147f53061a5861b3b892。
最终交付HEAD由PR及Git记录给出，避免提交内容自引用自身SHA。

便携复核仅需Python3.10+标准库，自动解包证据、按内容哈希重定位A源码，无需原机器绝对路径，不调用搜索：

```sh
python3 tools/midterm_dual_robot_region_b/checker_v2/portable_readback_v2.py   --evidence docs/research/midterm_dual_robot_region_b/checker_v2/evidence   --output /tmp/dual-b-v2-portable-readback.json
sha256sum -c docs/research/midterm_dual_robot_region_b/checker_v2/SHA256SUMS
```

读回绑定原始case/settings/identity、结果/证书/receipt哈希，使用旧B精确算术、投影与A格式转换重建，确保A证书属于同一B树；再运行锁定A V2。重算评价、分母、P4/N4中位数及门槛。计时来自原始账本，静态证明不能重新证明真实物理耗时。

正式搜索已完成，不要重复运行execute_v2。它拒绝未知attempt或不同冻结身份；已有完成记录仅跳过。随机门槛FAIL，禁止用N4单独通过或微基准速度绕过P4门槛。后续仅提出NEXT_PERFORMANCE_EXPERIMENT中的14项认证预收缩对照，本轮未执行；不启动两时刻。

原83文件与冻结文件哈希保护结果见PROTECTION_CHECK。A V2测试与交接快照见A_READY_SNAPSHOT；本轮44对拍、5种B破坏测试、3个开发worker分别见A_COMPARISON/B_COMPARISON/DEVELOPMENT。完整便携复核收据见PORTABLE_SEMANTIC_READBACK。
