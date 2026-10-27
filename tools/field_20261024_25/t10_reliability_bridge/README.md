# PR52可靠性策略接入PR53的T10条件性实包回放

只处理T10成功重试。输入、7组假设、初始化、R/Q、准入和方向全部继承PR53；9方法及policy全部继承PR52。没有改动这两套源码，没有读取留出包的定位输出，也没有读取T10人工终点或视频位置进行调参/评价。Car2的T09人工终点作为未验证起点的消费与PR53一致。

这是一个新冻结的、最多1800秒的T10任务，非PR52合成矩阵续跑。先提交全部代码/协议，在干净独立checkout执行。`bridge.py`直接使用PR52 Candidate，不运行其合成生成器/评价器；不通过B端严格来源入口。输出仍是工程假设下的响应，reference保持not_accepted，实际RMSE/ATE为空。时钟/杆臂敏感性步长不是误差界。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
"$PYTHON" -m unittest discover -s tools/field_20261024_25/t10_reliability_bridge -p 'test_*.py' -v
"$PYTHON" tools/field_20261024_25/t10_reliability_bridge/bridge.py --packet "$PACKET/T10_inputs" --output "$NEW_RESULTS"
"$PYTHON" tools/field_20261024_25/t10_reliability_bridge/audit.py --results "$NEW_RESULTS" --pr53-results "$PR53_RESULTS" --output "$NEW_AUDIT_JSON"
"$PYTHON" tools/field_20261024_25/t10_reliability_bridge/report.py --results "$NEW_RESULTS" --audit "$NEW_AUDIT_JSON" --output "$NEW_REPORT"
```

全部命令使用新目录，不覆盖旧证据。原PR53完整结果归档可按其校验值解压；audit会核验已登记的PR53 run SHA及所有输出，再逐行比较三个原基线。独立回读复算全部peer几何/Jacobian、门控、增益/Huber/Joseph/限幅、隔离保持、原始观测身份与源记录时间；不导入在线估计器或真值评价器。沿用PR52独立数学核验函数；不能把它说成第三方独立认证。

影子策略的非零保持修正不分配伪造的输出协方差，CSV保留空值及原因。固定门控未触发/限幅未触发也完整报告，不能由此宣称其有额外贡献。所有候选相对于independent的距离均为输出差异，非真实位置误差或收益。
