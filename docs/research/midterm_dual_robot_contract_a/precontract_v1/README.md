# 单时刻双车 P4 根域预收缩：A端证书

**结论：可以先缩域，但只能采用已证明包含原相容集的外端点。** 本交付实现“原问题 → 八方向安全外盒 → 原V2检查器核查盒内P4树”的复合证书；不靠求解器success、不把另一辆未知车当锚点。数学正确性不等于已有性能收益。

从PR131完整提交`50b592fbd672a1f19075147f53061a5861b3b892`建立独立分支`research/dual-robot-precontract-a`。所有新增均在本目录和对应tools/.../precontract_v1；旧PR、冻结接口、原检查器和历史结果保持逐字节不变。

入口：`tools/midterm_dual_robot_contract_a/precontract_v1/contract.py`。候选生成器：同目录`propose.py`，仅枚举二维有理线性组合，不执行定位搜索。实现支持两车全部八个方向、每方向独立回退；可以检查一般有理二阶锥方向乘子，但没有实现完整SOCP最优化器，也不声称最紧外盒。

最小可运行示例（仓库根目录，Python≥3.10，无第三方包）：

```sh
python tools/midterm_dual_robot_contract_a/precontract_v1/contract.py composite   docs/research/midterm_dual_robot_contract_a/precontract_v1/examples/normal.input.json   docs/research/midterm_dual_robot_contract_a/precontract_v1/examples/normal.composite.json
```

输出应逐字节等于`examples/normal.expected.json`（含最后换行）；状态`COMPOSITE_OUTER_CERTIFIED`，四坐标盒均为`[1/8,31/8]`。示例树只有手工UNDECIDED根盒，用于演示复合证书，不代表实际搜索收敛、达到分辨率或测得性能。

B接入看HANDOFF.md与FORMAT.md；推导看MATH.md；文献和本项目新增边界看LITERATURE_AND_SCOPE.md；测试和可读拒绝原因看VALIDATION_REPORT.md与TEST_RESULTS.json。READY.json固定完整实现SHA、格式、调用、依赖哈希和结果数，不需要用户转发或等待旧PR合并。
