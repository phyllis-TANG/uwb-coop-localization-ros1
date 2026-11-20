# 中文结论页

以 Car1 的手算输入为例，状态时刻 0 s 实际发布天线位置 (0,0) m。认证矩形为 [1/8,31/8]²，旧圆心是 (2,2) m；发布点到最远角的距离为 31√2/8 ≈ 5.48008 m。1 s 完成判定，恰好满足时限。AL=5 m，故该车在 1 s 产生超限告警、不可用。把本应 2 s 才就绪的结果交给 1 s 的查询，同一位置输出 NOT_READY；到 2 s 查询时输出 LATE。两次均不计入及时告警。

|独立复核内容|结果|
|---|---|
|手算及接口测试|13 项全部通过，包括两块分离区域、远角恰在保护圆上、向上舍入、PL=AL、偏离中心、空域、迟到与过期、启动缺输出、损坏、有效预算外包与丢队列、评价字段隔离。|
|#141 的正式证书|12 个冻结案例 × P4/N4，共 24/24 通过独立树检查。48 个车/方法记录中均有认证投影。完整分母与每条来源哈希见 READBACK_141.json。|
|可还原的实际发布决策|0/48。归档缺同历元实际发布点、发布时间、运行时实际判定就绪时间、AL 与失效策略。回执中的墙钟是运行耗时，图中十字是事后参考。未给这些记录赋予可用或不可用的历史事实。|
|可供接入的数据|发布端补 case、seed、car、输入哈希与方法、统一时基的状态/发布时间、同框架天线 XY、就绪时刻。任务方给 AL、截止时刻、有效期。查询给 as_of；程序输出每车 reason。|

#141 已证明模型事件下的有限区域包含。以每车实际发布点重算候选保护级后，才可对该车执行 AL 比较。即使包含成立，时效和发布身份仍是可用性条件。没有同历元发布记录的历史归档不进入可用率、误警率或漏警率的分母。原方案 HCPL 的风险分配与全任务 HMI 指标仍缺原文依据。

复现（仓库根目录）：

```sh
git fetch origin refs/pull/139/head
git fetch origin refs/pull/141/head
t=tools/midterm_dual_robot_contract_a/integrity_v1
python3 "$t/test_decision.py"
python3 "$t/read141.py" > /tmp/readback-141.json
diff /tmp/readback-141.json docs/research/midterm_dual_robot_contract_a/integrity_v1/READBACK_141.json
```

起点 main 8acffa9f4061e4740c18c7d0f1e09d28cf7f3155。原工作区 /home/ubuntu22/height-a 为 clean，独立工作区 /home/ubuntu22/integrity-pl-a；祖先及仓库内未发现适用 AGENTS.md。#139 HEAD ce33e7f09bf9f9abdf8336ab15191d83037c0873，发布检查器 da852740689113529b38815e1eb81f949ff5a8c6。#141 HEAD af844589dc41d38f50b329b6baee3efb25eca208，全量证据提交 944f44aecac84042fe181ff3aca9a3e6a5844d59。复核读取 #141 最终树的求解输入、证书与收据，无定位搜索。
