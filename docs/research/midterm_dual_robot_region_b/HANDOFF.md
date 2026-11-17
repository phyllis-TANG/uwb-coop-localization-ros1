# 交接与零搜索验收

基准：3ad69c8137183c1986012e354857b73527978c48。
A锁定：e45ca6d5940ff9f28233f03fb3502d5ed7004817。
运行冻结：e112b900a97dc92acb08c950e5f65e6e8e515ac8。
B分支：research/dual-robot-region-b；工作区/home/ubuntu22/uwb-dual-robot-region-b。
Git外原始结果：/home/ubuntu22/uwb-dual-robot-region-b-artifacts/results。
交付HEAD通过PR读取，避免文档自引用。

正式确定性授权44，完成44，全量读回PASS。条件随机门槛FAIL；门槛失败时240授权运行全部NOT_RUN。不自动合并、不扩两时刻。

SOURCE_LOCK.json逐项固定A源码/合同。外部复核先从该完整SHA提取其两个目录到只读来源根，然后设置DUAL_A_SOURCE_ROOT。源码原始路径仍列在SOURCE_LOCK，但可通过该环境变量重定位，全部哈希仍必须一致。

```bash
export PY=/path/to/venv/bin/python
export DUAL_A_SOURCE_ROOT=/path/to/read-only-A-source
$PY tools/midterm_dual_robot_region_b/unpack_delivery.py --evidence docs/research/midterm_dual_robot_region_b/evidence --ready docs/research/midterm_dual_robot_region_b/RESULTS_READY.json --out /tmp/dual-portable
$PY tools/midterm_dual_robot_region_b/readback.py --results /tmp/dual-portable/raw --freeze e112b900a97dc92acb08c950e5f65e6e8e515ac8 --out /tmp/dual-readback.json
sha256sum -c docs/research/midterm_dual_robot_region_b/SHA256SUMS
```

便携包的certificates/是A的原输出格式，raw/含完整B结果、attempt/receipt和分项计时。A可在解包后用自己的check.py archive验证；expected_sha应取RESULTS_READY.source_commit。该值是payload完整提交，发布READY的元数据提交可在其后；归档哈希固定全部payload字节，源码执行身份另外由run_frozen_sha固定。

A兼容归档48条包含4个不在用户计划的特殊N4，故A archive_check会返回INCOMPLETE并列明这4条NOT_RUN；授权44条逐证书均另核验。见USER_PROTOCOL_PRECEDENCE，不能隐藏兼容分母，也不增跑4例凑数。

原核心运行计时和正式结果不可覆写。若遇到attempt无完整receipt，先运行inventory.py清点；未知身份不自动重试。所有后加分析/绘图/归档脚本均为零搜索交付工具，不在正式执行依赖中，未更改冻结清单。
