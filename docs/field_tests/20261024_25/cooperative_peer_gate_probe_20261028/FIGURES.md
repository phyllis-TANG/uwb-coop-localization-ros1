# 全部seed同期图

每图含101/211/307，统一state/header时轴，截止为state+1s；红色为原始故障[24,38)，灰虚线为38+20s。q缺失不填0；unknown/missing在分类轴另列。真值只用于离线误差，三方法不作轨迹对齐。

- [正常](review/figures/nominal_all_seeds.png)
- [直接peer偏差](review/figures/peer_bias_all_seeds.png)
- [Car1单墙偏差](review/figures/wall_bias_all_seeds.png)
- [peer缺测](review/figures/peer_gap_all_seeds.png)
- [Car1四墙共同偏差](review/figures/car1_common_wall_bias_all_seeds.png)
- [直接peer偏差的当前窗与prior来源](review/figures/peer_bias_history.png)
- [四墙共同偏差的当前窗与prior来源](review/figures/car1_common_wall_bias_history.png)
- [Car2故障/恢复期相对同期nominal增量](review/figures/car2_propagation_paired.png)

完整base/antenna XY、两车yaw、相对位置、3D间距及逐时刻门控/来源见review/timeline.csv.gz、metrics.csv；实际factor ID、每次消元完整矩阵/affine/constant及辅助私有snapshot在Git外45个updates.jsonl.gz。来源祖先计数不等于误差因果贡献。
