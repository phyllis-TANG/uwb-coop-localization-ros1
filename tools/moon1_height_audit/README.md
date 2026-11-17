# Moon_1 height audit tools

纯CPU阶段一实现；[中文复建说明](../../docs/research/moon1_height_audit/README.md)。

- `run.py`：只接受新的Git外输出目录与干净checkout，验证公共生成器字节、预定固定高度、冻结输入，运行已有prepare/CSV，分析保存状态。
- `geometry.py`：严格新版CSV读取、距离与支持诊断；不导入优化器。
- `verify.py`：独立读回坐标、公式、分层、汇总和可访问文件哈希，不运行生成器。
- `test_geometry.py`：合成平地/坡面/重合/填补/边界/旧CSV夹具。

本入口的旧CSV拒绝不改变历史ROS脚本。不要绕过验证将旧CSV与新版GUI混用。
所有误差以实际三维距离减去候选模型距离定义；固定高度来源是冻结后端的0.17/0.20m，不是真值拟合。
