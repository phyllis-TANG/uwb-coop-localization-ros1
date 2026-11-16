# 给A端的冻结版本交接

分支research/midterm-s2-validation-ready，从PR101固定5e4e7ef6e2592cae5b4a4fc6462cbdbaeefb32da独立建立；PR以research/midterm-s2-numerics-v2为base。未合并任何PR。PR100固定2e28d99e8b6fa74384b795f8847ab72d5fa6e551仅只读参考。

本轮formal_runs=0，formal_observations_generated=0。50种子已登记并查重，未用于生成或定位。固定P1和36条件协议均已写入单一CONFIG。故障处理覆盖P0/P1异常、非有限、预算耗尽、未驻点及B0失效的配对缺失。没有因数值失败选优重跑，也未追加新性能研究。

A先在最终回执的完整冻结提交上执行README的accept.py命令。它校验manifest、配置、依赖和完整提交，枚举计划身份（不生成观测），然后只跑人工fixture及已暴露输入回归。检查结果存到新Git外目录，ACCEPTANCE.json记录完整冻结HEAD及formal_runs=0。

A验收重点：

1. 检查CHECKS和TARGETED_CHECKS归档中的真实缺失与分母；B0失败时D空、B2−B1可用，P0无有效终点时P1确实没有优化调用。
2. 确认恢复只补不存在的阶段，失败也视为完成；源/配置/依赖/阶段哈希不一致时拒绝恢复，不手动删除失败记录。
3. 核对CONFIG、SEED_REGISTRY和VALIDATION_PROTOCOL中的36条件、50seed、输入共享、独立初值/中心/权重及bootstrap缺失规则。
4. 检查已暴露旧输入数学目标与P0/P1终点完全一致；不将本轮测试当成性能确认。

验收通过并决定进入正式验证后，再按README运行pipeline.py run --mode formal --frozen-commit <完整冻结SHA>。该参数写入RUN.json；输出目录必须不存在。中断使用resume；汇总及只读复核命令均见README。正式运行不是本交付已经执行的动作。

冻结清单不嵌入自身提交SHA或自身文件哈希；执行前从确切checkout记录完整HEAD，避免自引用。最终交付HEAD、草稿PR链接由提交后回执给出。若A发现实质bug，保留该版本与结果，另版本修复；不得为了全通过调整阈值或筛掉条件。

Git外检查目录：/home/ubuntu22/uwb-validation-ready-artifacts/check3；完整人工输入/状态已压缩入新文档目录。建议6GB磁盘、4GB内存、2小时规划预算；实际正式资源消耗待执行记录。所有结论仅适用于六时刻简化模型，不是实车性能、罕见风险或保护级保证。
