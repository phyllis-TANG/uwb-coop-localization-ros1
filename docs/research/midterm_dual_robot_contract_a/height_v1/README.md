# 月面固定高度单历元定位验收

支持已知高度、原始斜距的原域 P4/N4。根域从联合噪声事件与八条锚距推导。15 项测试通过。月球端锁定 READY 实现 da852740689113529b38815e1eb81f949ff5a8c6，在仓库根目录运行 `python3 tools/midterm_dual_robot_contract_a/height_v1/checker.py docs/research/midterm_dual_robot_contract_a/height_v1/input.json docs/research/midterm_dual_robot_contract_a/height_v1/certificate.json`。

输入、兼容集、树证书及空域格式见 MODEL.md。第三方依赖为零；省略证书参数可单独计算共用根盒。月球端求解器独立输出证书，A 端只核验。
