# 版本、来源与问题处理

2026-11-18：读取PR132固定场景审计与JSON候选表，未把不存在的WINDOW_CANDIDATES.md/SCENE_EXECUTION.md当作遗漏数据；对应文件是JSON。

- LuSNAR作者原始仓库：https://github.com/zqyu9/LuSNAR-dataset 。本轮使用同一Moon_1合成序列，参考轨迹来自gt.txt，第二车是错时5秒构造，非独立同步车辆记录。人工锚点来自冻结布局规则，非数据集设施。保留原来源清单及两新增点云的CRC/SHA256。
- OpenUSD变换缓存：https://openusd.org/release/api/class_usd_geom_xform_cache.html 。本机usd-core26.8；通过每个时间的XformCache读取层级组合后的世界天线位置，验证局部杆臂、米制和Z-up，不只读写入数组。
- NVIDIA独立Python入口：https://docs.isaacsim.omniverse.nvidia.com/latest/python_scripting/manual_standalone_python.html 。安装IsaacSim6.2.0.0/Lab3.0.0，torch2.11.0+cu130；先做GPU探测，支持时才初始化SimulationApp并导入omni模块。此主机nvidia-smi失败且CUDA设备0，GPU分支未执行也未验证。保留待GPU机器执行的入口，不声称已做Isaac运动或渲染。
- CPU环境沿用原独立venv：Python3.10.12、NumPy2.2.6、SciPy1.15.3。系统Python混有不兼容的旧SciPy，首次补取脚本导入场景模块触发ABI错误；将补取路径改为标准库＋原HTTP客户端，不修改系统环境。原远端目录含timestamp.txt，修正选择器只接受数字时间戳。两项发生在新输入冻结前，没有运行定位实验。

旧平移外参[1,0,-1.5]m仍为历史假设。C=diag(1,-1,-1)为正交旋转、det=+1。新增帧沿用最近GT、同外参、同0.4m中位数栅格和0.65格平滑规则。未把平滑结果算作直接观测，也未删除产生帧高差的点云以提高通过率。
