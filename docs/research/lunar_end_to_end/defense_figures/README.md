# Moon_1 中期答辩配图

正文按图 1、图 2 的顺序讲。图 1 建立场景与实验位置，图 2 给出一个可独立核算的几何证明。图 3 用于备用页，回答改变测距假设后的结果。数值与路线资产固定于提交 `c7d53da2bb989f73514a6ce540813c379d698897` ，场景介绍另用本地归档视频。数值来自已验收的 #151。PNG 为 3200 × 1800，PDF 保留文字与绘图线条。生成环境使用 Liberation Serif，脚本在有 Times New Roman 的环境中优先使用该字体。

在仓库根目录运行以下命令。依赖为 Python 3.10+、NumPy、Matplotlib 和 Pillow。三个入口都只读归档数据。

## 图 1 · 正文 · 场景、双车与四个历元

[高清 PNG](01_scene.png) · [PDF](01_scene.pdf)

**English caption.** Left, a frame at 7.00 s from the October 30 Isaac Lab demonstration video shows terrestrial rover tracks replayed on a LuSNAR-derived display mesh. The craters outside the cooperative area are decorative. Right, plan views drawn from the two evaluation segments show the antenna tracks and synthetic anchors in the local moon_map frame. Circles and diamonds identify indices 0 and 11 on each track. At a common scene time, Car 1 uses a source pose five seconds later than Car 2. Green encodes gridded terrain elevation at observed cells, salmon marks filled cells, and white lies outside the archived crop.

**中文讲解（约 30 秒）**　左图是后期 Isaac 演示视频第七秒。团队用 LuSNAR 数据生成月面网格，在上面回放地面双车实验；远处的环形山是展示素材。右边两幅地图给出本次实验的实际位置。蓝、橙两车取自同一条源轨迹，同一场景时刻，一号车取晚五秒的源位置。圆点和菱形是每段的第 0 和第 11 个索引；三角形是合成锚点，橙粉色网格是地形填补区。

左图直接读取[视频第 210 帧，零基索引](isaac_replay_7s.png)。原视频位于场景工作树的 `sim/isaac_lab/moon1/output/videos/moon_uwb_topright_en.mp4`（1920 × 1080，30 fps，SHA-256 `fe3010389bcd411c6303a5d290f5f3746ca881f985d0384ab72452a0982b53d8`）。取帧命令为 `ffmpeg -ss 7 -i moon_uwb_topright_en.mp4 -frames:v 1 isaac_replay_7s.png`。原场景的 `output/videos/presentation_provenance.json` 记录装饰性环形山与车载天线模型的来源。两幅地图分别读取主段的 [terrain.npz](../continuous/terrain.npz)、[ROUTE.json](../continuous/ROUTE.json) 和第二段的 [terrain.npz](../replication/terrain.npz)、[ROUTE.json](../replication/ROUTE.json)。可与[主段原图](../continuous/selected_route.png)、[第二段原图](../replication/routes.png) 对照。地图在 CPU 上按网格绘制。高度色标共用，两个地图保留各自的实际坐标。

```bash
python3 tools/lunar_end_to_end/defense_figures/render.py scene
```

## 图 2 · 正文 · 与圆心选择无关的下界

[高清 PNG](02_witness.png) · [PDF](02_witness.pdf) · [精确核验值](witness_check.json)

**English caption.** At the first main-segment epoch, two joint four-dimensional antenna positions satisfy the P4 threshold of 26 with known heights, zero peer bias and a 4 cm range standard deviation. The weighted sums of squared residuals have upper bounds of 19.961 and 21.975. The Car 1 projections are 31.04 cm apart (rounded). By the triangle inequality, every disk containing both has radius at least half their separation, exceeding 15.51 cm. The solid circle attains this bound for the pair. The dashed circle has radius 10 cm. Both are drawn about the pair midpoint.

**中文讲解（约 30 秒）**　看主段第一个时刻。A、B 各代表一组完整的双车位置，把它们分别代回九条测距，即使把车间偏差固定为零，两组统计量也都低于 26。只看一号车，这两种可能的位置就相隔 31.04 厘米。半径十厘米的圆，直径只有二十厘米。无论把圆心移到哪里，要同时覆盖两点，半径至少得有 15.51 厘米。

[见证原件](../round2_radius/witnesses/main_start_normal.json)、[零偏差输入](../round2_radius/inputs/zero/main_start_normal.json)与[四维叶盒证书](../radius_resolution/results/main_start_normal/fine_matched.json.gz)共同确定点对。脚本核对输入哈希及两个 INSIDE 叶盒的精确中点，加入已知高度，按八条锚距和一条车间斜距分别计算三维距离。整数平方根在有理网格上夹住每个根号，两端取最大残差平方并除以方差。逐项对照九个有理上界、总和及投影间距平方，最后严格比较半间距平方与 0.01 平方米。图中原点是投影中点。蓝圈仅覆盖这对见证，完整可行集可能要求更大的半径。

```bash
python3 tools/lunar_end_to_end/defense_figures/render.py witness
```

## 图 3 · 备用 · 测距假设对照

[高清 PNG](03_assumptions.png) · [PDF](03_assumptions.pdf)

**English caption.** Horizontal outer radii are measured about each vehicle’s published antenna position. The first two columns retain the original observations and 4 cm noise scale. Fixing peer bias to zero changes seven radii by zero at the displayed precision and reduces the eighth by 0.34 cm. Halving the assumed noise scale on the old observations yields two sub-10 cm radii for Car 2, but excludes the true joint position at both segment starts. With new observations generated at the matched 2 cm scale and new position fixes, the joint truth is feasible at all four epochs and the eight radii range from 10.68 to 16.43 cm. These four epochs measure state-time geometry only.

**中文讲解（约 30 秒）**　从左往右看，车间偏差即使完全已知，八个外半径几乎没有变化。把同一批观测的噪声假设收紧，二号车两次看起来进了十厘米，但这两个时刻连双车真值都被模型排除了。最后一列用更小的噪声重新生成观测，再重新定位，真值四次都相容，八个外半径仍都超过十厘米。这组数据回答的是四个时刻的空间范围，不能推算车辆实时可用率。

[attribution.csv](../round2_radius/attribution.csv) 的 `baseline_cm`、`zero_outer_cm`、`tight_outer_cm` 对应前三个半径列，`tight_truth` 给出联合真值相容性。[matched.csv](../round2_radius/matched.csv) 的 `outer_cm`、`true_feasible` 给出第四列及其相容性。按 `case,car` 对齐，p、s 分别表示一、二号车。匹配组沿用标准化噪声抽样。两种 2 cm 条件均为仿真假设，四个历元来自同一源序列。

```bash
python3 tools/lunar_end_to_end/defense_figures/render.py assumptions
```
