# 检查器 V2 接入合同

V2 仅提速独立验收，不修改输入、统计事件、阈值、域、树、队列或求解算法。原 core.py、check.py、53项测试、CONTRACT_READY.json及其23个冻结文件全部保留。原模型仍DUAL-A-V1，本次检查器实现标识DUAL-A-CHECKER-V2。

## B 可直接调用的入口

先从PR131读取包含CHECKER_V2_READY.json的固定完整Git SHA，checkout/extract该SHA的A工具目录，核对标记中的文件SHA256。不要只读一个可移动分支名后长期复用；最终完整SHA在PR正文报告。必须同时保留同目录的冻结core.py。

CLI接受原冻结输入数组或单个输入对象，以及A格式证书：

```sh
python tools/midterm_dual_robot_contract_a/checker_v2.py \
  docs/research/midterm_dual_robot_contract_a/inputs/deterministic.json \
  normal_b0_zero /path/to/certificates/normal_b0_zero_J5.json
```

B现有a_bridge可只替换加载的A文件名为checker_v2.py，保留make_certificate产生的原A证书结构，再调用`module.check(case['a_input'], cert)`。返回字典与V1完全一致，错误仍抛ValueError子类；不得捕获异常后填成功。V2按绝对兄弟文件路径加载A的core.py，避免与B搜索core.py重名。既不导入B定位器，也不修改全局sys.path或猴子补丁。原certificate_a.checker_sha256应明确记录V2入口哈希，另记其冻结core依赖哈希与固定Git SHA；不要继续标为V1。

每次check新建PreparedInput，缓存只活于这一调用。B不得跨输入复用PreparedInput，不得将评价真值加入输入。正常接入只使用check函数；内部类暴露仅便于测试。重复调用check会冷建缓存，不保留跨证书状态。

## 提速与不变量

固定锚点、观测闭区间、方差、域和阈值仅解析一次。有理数字符串解析缓存也仅属于当前输入。锚点缓存键=(车辆编号, 精确二维子盒Fraction端点)，条目包含四个距离上下界及对应四行残差平方和上下界。即使两车位置子盒相同，其观测/方差可能不同，因此车辆编号不可省略。新输入必须新缓存；不能用字符串格式的近似值、浮点舍入或空间网格当键。

每条peer距离仍按完整(p,s)盒计算；5D保留盒内bias，4D消去全局bias闭区间，N4没有peer。分组求和使用精确有理数，结合次序不引入舍入误差。平方根仍使用原10^30整数平方根外界；所有判定仍OUTSIDE严格下界>τ、INSIDE上界≤τ。

树遍历/根域/父子覆盖/去重/完整叶/队列/观测及阈值身份/成本计数的控制逻辑从冻结V1保持原样，只替换解析与界计算调用。逐车投影、半径、面积上界、偏差恢复仍逐项精确复算，未信任保存的lower/upper/success。保留盒不会因缓存而跳过验证。没有用真值或镜像方向决定缓存/剪枝。

缓存测试覆盖：同盒不同车辆、不同观测/方差输入、重复命中、等值有理数字符串、调用者随后修改原输入，以及B的同名core模块。原53项在V1及V2下都运行；V2总计54项。

## 更新后的分母口径（用户指令优先）

确定性正式44=J5 16+P4 16+N4主矩阵12。旧归档48中的4个特殊N4仍留在证据中，单列OUTSIDE_USER_AUTHORIZED_PLAN；不补跑、不计失败。条件随机为120输入配对P4/N4，共240次，A不运行。该明确修订覆盖早期冻结HANDOFF/check.py archive的48/360计划口径；不静默修改旧函数。单证书check接口无需迁移。

B在PR133的条件随机阶段因成本门槛失败未运行。V2验收提速不能抹去旧成本或将原门槛失败改成通过；B应另记接入版本与后续阶段记录。A发布本标记后可收尾，无需等待随机结果，不启动两时刻搜索。

## 可复现实验（零搜索）

```sh
python tools/midterm_dual_robot_contract_a/lock_evidence_v2.py --repo . --out /tmp/dual-a-evidence
python tools/midterm_dual_robot_contract_a/benchmark_v2.py batch --kernel v1 --evidence /tmp/dual-a-evidence --out /tmp/dual-a-bench
python tools/midterm_dual_robot_contract_a/benchmark_v2.py batch --kernel v2 --evidence /tmp/dual-a-evidence --out /tmp/dual-a-bench
python tools/midterm_dual_robot_contract_a/summarize_benchmark_v2.py --directory /tmp/dual-a-bench --out /tmp/dual-a-benchmark.json
python tools/midterm_dual_robot_contract_a/audit_delivery_v2.py --evidence /tmp/dual-a-evidence --evaluation docs/research/midterm_dual_robot_contract_a/evaluation_only.json --out /tmp/dual-a-raw-audit.json
```

锁定脚本只读Git对象，逐压缩包与成员验证SHA256，再安全展开；不执行B脚本。benchmark不覆盖已有样本，每份证书一个全新解释器、固定同一CPU、顺序执行；先V1后V2。不清除OS页缓存，因此“冷启动”指冷进程和空应用缓存，不能称冷磁盘。每版本只测一轮，保留所有样本，不选最快值。
