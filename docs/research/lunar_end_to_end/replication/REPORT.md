# Moon_1 跨路段复验

第二路段仅有车间测距渐变时，M3 相对 M2 将 Car1、Car2 的平均 RMSE 分别降低 5.63、4.92 mm，分别有 10/10、9/10 个配对种子改善。两种异常同时出现时分别降低 5.75、3.98 mm，改善数仍为 10/10、9/10。真实偏差为零时仍估出虚假斜率，正常条件平均绝对值为 0.00488 m/s。

主段复用 PR132 的已保存结果。备用段重新按 12 帧点云的相同栅格、每 0.02 s 每车 63 个车体采样点、相同支持和高度门槛检查。Car2 源时间 109.66–114.00 s 全段通过，Car1 为 114.66–119.00 s。向前延至 109.00 s 时，Car2 在 109.00–109.64 s 的直接观测比例不足。两个路段的车间距离范围依次为 10.81–11.79 m 和 10.75–12.55 m。两车净运动方向由主段的 8.93°、5.97° 变为 4.62°、4.49°（世界 +x 向 +y）。[逐车起点至各锚点方位和锚点坐标](GEOMETRY.csv)记录按相同规则得到的两组不同布局。多个几何量同时改变，不能单独归因于其中一项。

原 10 个种子按测距、运动和先验分别生成共享随机扰动。主段 24 时刻，备用段按同一采样规则得到 23 时刻，所以跨段共享种子和对应创新，绝对时刻不同。主段和备用段的 0.30 m 全段渐变分别为 0.067873 和 0.069124 m/s。Car2 运动异常为中段一次沿当时航向的 0.15 m 增量扰动。

下表每格按 Car1 / Car2 排列。净协同收益见 [SUMMARY.csv](SUMMARY.csv) 中以 M0 为基准的两组配对。该表同时列出原始 RMSE、两方法最坏峰值及峰值配对差。[逐种子配对](PAIRS.csv)保留每次峰值、两方法状态及收益符号。

|路段|条件|全部有限的 M2→M3 平均改善 mm|改善数/分母|双方接受的平均改善 mm|改善数/分母|M0 平均 RMSE mm|M3 最坏峰值 mm|
|---|---|---:|---|---:|---|---:|---:|
|main|normal|+0.073 / +0.014|5/10 / 6/10|+0.073 / +0.014|5/10 / 6/10|24.57 / 26.52|61.24 / 95.25|
|main|ramp_only|+6.070 / +5.107|10/10 / 9/10|+6.070 / +5.107|10/10 / 9/10|24.57 / 26.52|61.24 / 95.25|
|main|motion_only|+0.070 / +0.003|6/10 / 6/10|+0.070 / +0.003|6/10 / 6/10|24.57 / 30.26|60.98 / 94.85|
|main|both|+6.180 / +4.217|10/10 / 9/10|+5.433 / +4.523|9/9 / 8/9|24.57 / 30.26|60.98 / 94.85|
|second|normal|+0.170 / -0.100|6/10 / 5/10|+0.170 / -0.100|6/10 / 5/10|24.59 / 26.44|60.56 / 98.88|
|second|ramp_only|+5.631 / +4.918|10/10 / 9/10|+5.631 / +4.918|10/10 / 9/10|24.59 / 26.44|60.56 / 98.88|
|second|motion_only|+0.163 / -0.105|5/10 / 5/10|+0.176 / -0.126|4/9 / 4/9|24.59 / 30.31|60.19 / 98.32|
|second|both|+5.747 / +3.983|10/10 / 9/10|+5.747 / +3.983|10/10 / 9/10|24.59 / 30.31|60.19 / 98.32|

正常和仅运动异常时，Car2 的平均收益从主段的 +0.014、+0.003 mm 反转为备用段的 −0.100、−0.105 mm。备用段正常与仅运动异常时的平均绝对虚假斜率分别为 0.00488、0.00506 m/s，主段为 0.00307、0.00304 m/s。运动异常使有符号斜率平均移动 +0.000973 m/s，主段为 +0.000901 m/s。[零偏差逐种子数据](ZERO_BIAS.csv)。两个路段来自同一合成序列，样本为配对描述。

**图 1**　两段 LuSNAR 合成点云地形支持。绿色为直接观测节点，浅橙色为填补节点，白色为裁剪网格外。箭头表示同一轨迹错时 5 s 构造的双车运动方向，三角形为人工锚点。短时异常沿 Car2 航向向一次中段运动观测注入 0.15 m，图中的参考路线保持原样。

**Figure 1.** Terrain support from LuSNAR synthetic point clouds. Green and orange denote observed and filled nodes. Arrows show two vehicles constructed from one trajectory with a five-second offset. Triangles mark artificial anchors. The short anomaly adds 0.15 m along Car2’s heading to one mid-route motion observation.

[矢量图](routes.pdf) · [地形 CSV](FIGURE_GRID.csv) · [轨迹 CSV](FIGURE_TRACKS.csv) · [锚点 CSV](GEOMETRY.csv)

**图 2**　两车在两段上的逐种子 RMSE 改善，正值表示 M3 较 M2 误差小。黑线为全部有限配对均值，叉号为未通过数值接受的配对。使用 LuSNAR 合成点云、同轨迹错时双车及人工锚点，短时异常向 Car2 的一次运动增量沿航向加入 0.15 m。

**Figure 2.** Paired RMSE reduction by vehicle and segment. Positive values favor M3. Points show seeds, black bars show all-finite means, and crosses mark pairs failing numerical acceptance. The setup uses LuSNAR synthetic point clouds, a time-shifted pair from one trajectory, and artificial anchors. The motion anomaly adds 0.15 m along Car2’s heading to one increment.

[矢量图](paired.pdf) · [种子点 CSV](PAIRS.csv)

执行冻结 `b877952ac7eb6de669e57d6e43f5a16f74ca1e57`。新增 120 次、240 次优化调用，119 次接受。备用段 motion_only_2026111809_M3 未驻点，旧主段 both_2026111807_M2 未驻点。独立残差和梯度检查读回全部备用端点。OpenUSD 26.8 重开 USD 后通过 435 次时间查询及 436 个车体姿态检查，天线位置与车间距离最大读回差为 0。IsaacSim 6.2.0.0、Lab 3.0.0 探测 CUDA 设备数为 0，GPU 回放未执行。[CPU 日志](CPU_REPLAY.json) · [姿态核验](READBACK.log) · [GPU 探测](isaac/STATUS.json) · [USD](continuous_route.usda)

复核时从仓库根目录使用 PR132 的 CPU 环境执行 `OPENBLAS_NUM_THREADS=1 python tools/lunar_end_to_end/replication/compare.py`，该入口读取两个路段的已保存端点及指标，检查备用段残差、梯度与姿态并生成 CSV 和两张图。点云变换沿用原 LuSNAR 至 moon_map 的 C=diag(1,-1,-1) 和原 LiDAR 外参假设。车体姿态为直立航向模型。
