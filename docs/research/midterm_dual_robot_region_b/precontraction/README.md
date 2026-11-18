# B 端单时刻认证预收缩

[七例正式结果、逐例配对表和全流程成本图](REPORT.md) · [完整运行账本](LEDGER.csv) · [独立复核记录](runs/pilot/decision.json)

A 发布提交为 27883c420b969dbf2354736a4d04221522228198，实现为 d3dc0dc8a028de569fa84941cb09ab801c8e5ed8。已核对 READY 全部文件哈希，最小 CLI 样例与期望输出逐字节一致。B 冻结提交为 a86d143b83617bb360402ff3bd0745231545a001，首对发布提交为 fbbe5dabf9d6325e551a27e3fe655fb23d8a7543，全部证据提交为 52a92f92a83eb19c638260f70f73199d7f8e700d。

A 端可从本 PR 根目录执行以下零搜索复核。需要本地 Git 对象库包含上述 A 实现提交及 B 冻结提交。

```sh
export PILOT_A_SOURCE=$(mktemp -d)
git archive d3dc0dc8a028de569fa84941cb09ab801c8e5ed8 tools/midterm_dual_robot_contract_a docs/research/midterm_dual_robot_contract_a | tar -x -C "$PILOT_A_SOURCE"
python3 tools/midterm_dual_robot_region_b/precontraction/replay_delivery.py
```

每例目录中的 proof.json.gz 保存原输入、派生输入、完整证书、逐车区域、评价与 A 判定。收缩组的 certificate 可直接传给 A 的 check_composite(original, certificate)。严格空集有显式空证明与空搜索证书。其余运行另存 tree.json.gz。worker.json 保存分项计时，wall.json 为父进程实测总耗时。PLAN.json 沿用 #134 原输入、顺序、CPU 和预算。
