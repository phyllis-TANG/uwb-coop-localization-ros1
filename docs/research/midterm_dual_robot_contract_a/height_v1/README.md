# 月面固定高度单历元定位验收

支持已知高度、原始斜距的原域 P4/N4。根域从联合噪声事件与八条锚距推导。15 项测试通过。月球端锁定 READY 实现 da852740689113529b38815e1eb81f949ff5a8c6，在仓库根目录运行 `python3 tools/midterm_dual_robot_contract_a/height_v1/checker.py docs/research/midterm_dual_robot_contract_a/height_v1/input.json docs/research/midterm_dual_robot_contract_a/height_v1/certificate.json`。

输入、兼容集、树证书及空域格式见 MODEL.md。第三方依赖为零；省略证书参数可单独计算共用根盒。月球端求解器独立输出证书，A 端只核验。

批验收从仓库内执行 `python3 tools/midterm_dual_robot_contract_a/height_v1/batch.py PLAN_SHA plan.json EVIDENCE_SHA ledger.json`。两个 SHA 均为完整 Git 提交；路径相对于各自提交根目录。plan.json 为 12 行对象数组，每行字段为 segment ("1"/"2")、epoch ("start"/"middle"/"end")、condition ("normal"/"ramp")、input (JSON 路径)、input_hash。每输入固定九个原始读数，两种方法读同一输入。ledger.json 是对象数组，行含 case_id、mode ("4d"/"no_peer")、input_hash、status。DELIVERED 需 certificate (JSON 或 .json.gz 路径) 和 sha256（文件原字节）；NOT_RUN、FAILED 需 reason。缺行计 MISSING，错误证书计 REJECT，BUDGET_OUTER 单列，表内保存完整队列、投影摘要及分辨率检查。归档时间与 RSS 为运行端自报。

月面原件锁定于 3b68bcf0df9de496cf7353f3cd506a06e5a6f40c。import_lunar.py 验证十二个原件的字节哈希，按月面冻结适配器的十进制时间标签取 s，p=s+5，并在计划中另存原始两车源时间。几何、方差和斜距保留原文件的精确有理值。执行设置为 50000 节点、30 秒和 0.05 m。真实 CSV 入口支持月面结果目录和 receipt.json；N4 从同一冻结输入取前八行并重算方法输入哈希。

正式复核见 lunar_receipt.json。当前证据提交 1880aab1b55f9064c50b0398a0fead3ec1693c20 有 24 个计划身份，其中 main_start_normal 的 P4 已交付并通过，节点 11485，队列为空，达到目标分辨率；23 项尚未运行。预算停止有效外包 0 项。验收从冻结输入重算根、树、区域和队列，再读取独立评价数据核查事件和联合/逐车命中。墙钟沿用月面当次账本。请在仓库根目录复核：

```bash
git fetch origin research/moon-slant-region
d=docs/research/midterm_dual_robot_contract_a/height_v1
python3 tools/midterm_dual_robot_contract_a/height_v1/batch.py 1642ed15a68c50ec5db7dc8711426a479dc01660 "$d/lunar/plan.json" 1880aab1b55f9064c50b0398a0fead3ec1693c20 docs/research/lunar_end_to_end/slant/LEDGER.csv
```
