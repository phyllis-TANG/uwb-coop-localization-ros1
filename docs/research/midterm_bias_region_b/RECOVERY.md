# 后续运行器的保守恢复组件

入口 `tools/midterm_bias_region_b/recovery.py`，不依赖优化器。调用方用 `identity(unit,method,stage,input_value,config,source_files)`对实际输入、解析配置、所有执行代码文件计算身份，再将该身份与零参数调用函数交给 `execute(root, identity, solver)`。P0/P1须有不同stage；P1的input_value必须包含其实际初始状态或P0结果哈希。依赖版本也应放进解析配置。不能只传文件路径而不计算实际内容。

阶段目录按(unit,method,stage)寻址，内容身份另外核验，避免输入改变悄悄产生另一重试。阶段级fcntl锁在检查、调用、结果保存和完成标记全程持有。同一阶段两个合作进程中只有一个能进入，另一方得到ConcurrentExecution。

顺序：持久化唯一UUID ATTEMPT（文件fsync、原子排他link、父目录fsync）→调用→原子持久化RESULT（身份、attempt ID、payload校验和）→DONE（绑定结果校验和）。已有文件永不覆盖。普通调用异常保存为EXCEPTION失败结果，成功返回但数值失败也按原样保存；二者恢复均不重新调用。中断/进程退出等BaseException不被伪装成普通失败。

恢复状态：
- 无attempt且无结果：允许首次调用。测试“before_attempt”在持久化前中断、调用计数仍为0，因此后续首次执行安全。
- attempt存在、结果不存在：持久化UNCERTAIN，抛UncertainExecution，**拒绝自动重跑**。即使实际上尚未调用，也宁可保守停止；日志不可能证明外部计算一定未发生。
- 结果存在但DONE缺失：验证完整身份、attempt ID与payload哈希，补DONE并返回RESTORED，绝不调用求解器。
- 完整DONE：只读验证恢复；已有失败同样完成。
- 孤立结果、JSON损坏、身份/哈希不匹配：拒绝，不用新结果替换。

本组件只承诺在遵守锁/目录约定的本地POSIX持久化语义下保守防重复；不保证任意分布式文件系统、磁盘损坏或外部副作用的恰好一次执行。不提供清除UNCERTAIN后自动重试的命令；后续必须人工审计并单独登记处理决定，不能把不确定阶段视为未运行。

## 与PR111的关系

旧run.py有整次运行锁和排他结果文件，但恢复只看阶段结果是否存在。其STAGE_START没有作为拒绝重试的依据，故“已调用而未落盘”可能重复执行。旧批次已执行记录与旧冻结代码不改写；本轮不声称修复历史执行语义。后续新运行应显式接入本组件，不能继续声称旧入口具有同等中断保证。

RECOVERY_TESTS.json含12项边界检查：attempt前/后中断、调用后未落盘、结果已落盘缺完成、完整恢复、返回失败、抛异常、输入/配置/代码身份不一致、结果阶段身份篡改、真实双进程冲突。全部只用可计数假求解器、临时目录；真实优化器调用0。
