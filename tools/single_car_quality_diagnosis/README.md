# 冻结v1失效归因工具

只读旧日志；新增产物必须放在Git外新目录。不要执行旧run_matrix.py。本目录没有线上质量策略或内核修复。

- `verify_evidence.py`：校验原归档全部成员、复用validation文件、96运行源码/配置。
- `analyze_logs.py`：从raw/ledger/graphs/publications/availability重建8事件、成对nominal、分段误差和prior链。
- `intervene.py`：只执行预登记D1/D2，导入原归档验证过的冻结源码，6个主图日志重建和28个目标函数快照求解，不运行正式矩阵/影子回放。
- `mechanics.py`：独立算UWB曲率、yaw–bias增量关系及恢复层次。
- `make_delivery.py`：生成8个逐事件和2个全seed同期图及紧凑数据。
- `validate.py`：不导入在线规则，独立校验FSM、sqrt(g)、原指标、事件时长及干预控制。
- `package_evidence.py`：新证据打包、每成员实读核验、可选复制到独立NAS目录。

真实执行命令、先后顺序、已知schema边界见诊断文档COMMANDS.md、REPORT.md。所有诊断使用已暴露seed，仅支持归因，不调v1参数、不报告为独立验证。F0没有bias状态；periods表该指标为空，timeline/history中的0仅为兼容绘图占位，不能解释为bias估计。14个快照中2个Q2影子的bias列同为不适用。

复用原venv（NumPy/SciPy/Matplotlib等版本见原run.json）；设置`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`，避免写入冻结源码的pycache。诊断用的truth、labels只在离线评价中使用。
