# B端：真正双车联合区域与计算效率

状态以PROGRESS.json为准。共同起点3ad69c8137183c1986012e354857b73527978c48；当前开发与正式运行分开。仅单时刻、两车XY未知、4已知锚点、9条测距、peer单偏差、已知正定对角R。

J5搜索五维原集合；P4解析消去peer偏差后搜索四位置坐标；N4使用原八条锚点行与A定义的q8。公式见MATH，预算和门槛见PROTOCOL。每车投影、成本及失败分母都保留。

开发检查：

```bash
/path/to/venv/bin/python tools/midterm_dual_robot_region_b/tests.py
```

核心仅需Python3.10标准库。没有A的远端READY与锁定来源，不运行正式输入，不把开发q值或自己生成的夹具冒充A合同。
