# 本轮完成：只读帮助—代价及容差来源

分支analysis/20261029-cooperation-cost-criteria；工作树/home/ubuntu22/uwb-cooperation-cost-criteria-20261029；main基准81fb509ba2d2a1b2e1f1151d53a7e73807820bd4（已含PR78）。原PR78工作树未修改。未发现仓库及上级适用AGENTS。既有rosmaster/rosbag保留、不操作。约14GB空间，既有Python3.10/numpy/matplotlib环境，无安装/原件下载/NAS访问。

唯一文件归属：tools/cooperation_cost_criteria_20261029/、docs/research/cooperation_cost_criteria_20261029/。输入只是PR78 Git内紧凑导出；未回读原始测距或重新计算真值误差，未加载求解器。本轮从逐时刻已导出误差重算864个分阶段RMSE，与原METRICS核对；不是仅抄汇总，也不把它包装成新的估计器验证。

入口REPORT.md；CRITERIA.md解释判据；TOLERANCE_SOURCES CSV/JSON共16项；METHOD_SCOPE标明公平性边界。PER_CAR/TRADEOFF_POINTS含全部两口径、全部阶段；PAIRWISE_RELATIONS与GLOBAL_RELATIONS只表算术关系；DIAGNOSTICS_ONLY图不得混入在线基线排名。未知容差JSON null/CSV空，不用0补值。

执行：在此工作树使用
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python -m unittest discover -s tools/cooperation_cost_criteria_20261029 -p 'test_*.py' -v`
以及同前缀 `.../python tools/cooperation_cost_criteria_20261029/analyze.py`。
重读时使用 `--output /全新目录`；CSV独占创建防止覆盖。日志在/home/ubuntu22/uwb-cooperation-cost-criteria-20261029-artifacts；所有紧凑研究结果均入Git，无新增大证据。原PR78归档/输入/源码身份在源RUN_INDEX与SHA清单，本轮RUN_MANIFEST绑定读取路径。

结论：阶段支配会反转，加入yaw也可改变XY单指标结论；全阶段无主方法算术支配，实际优势/可接受损害仍未判定。近期仅论文离线研究，用户未提供闭环容差。2cm/5mm/1/3是例子，4cm是开发预算，均未被批准为通过线。

停止：没有新实验在运行。后续不自动扫描参数或新增种子，也不实施同四墙线索门控限幅。若要继续，先处理用途/研究效应尺度和配对参考能力；办公室旧记录无法恢复就缩小主张。允许本轮推送独立草稿PR供审阅，不自动合并。
