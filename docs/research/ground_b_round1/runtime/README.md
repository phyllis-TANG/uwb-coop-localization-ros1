# A 的开发输入

从仓库根目录读第一条传感器观测，仅依赖 Python 标准库。

```sh
python3 -c "import gzip; print(gzip.open('docs/research/ground_b_round1/runtime/events.jsonl.gz','rt').readline().strip())"
```

开发数据为 #143 的 101 正常场景。运行时只需复制本目录。按行顺序读取 events.jsonl.gz，使用 geometry.json 的已知几何及配置。传感器记录仅导出下表字段。每车、每通道 1,281 帧，状态时间 0–64 s（含端点）、20 Hz；全流共 5,124 帧，按接收时间排序。旧评价表止于 63.95 s。

|字段|含义|
|---|---|
|vehicle_id, kind, source_observation_id|车辆、odom 或 uwb、稳定帧 ID。如 car1:uwb:0；该帧内的链路由 node 键标识。|
|header_epoch_ns, receive_epoch_ns|仿真状态戳及车辆可读的接收戳，整数纳秒。先减 geometry.json 的 epoch_ns 再除以 1e9；回放仅释放接收戳已到的消息。|
|odom 的 value.pose|基座累计局部里程位姿 [x,y,yaw]，单位 m、m、rad。各车以自己的初始基座为局部原点、初始朝向为局部正 x。生成器把含噪的车体系步进按上一里程航向积分。本入口直接提取已生成的 odom 事件。若需增量，可对同车相邻里程位姿做 SE(2) 相对变换。|
|uwb 的 value|四条天线至锚点的三维原始斜距（m），以及本车发出的单向 peer 读数。Car1 的 node_0 指向 Car2，Car2 的 node_1 指向 Car1。旧区域输入使用前向一条，反向可独立识别。|
|geometry.json 的 models|地面房间坐标系下的锚点 XYZ、天线高度、车体系基座至天线 XY 杆臂（m）。start_antenna_xyz_m 的 XY 和 initial_heading_deg 是该次生成后带扰动的 1 s 初始先验，航向单位 deg。graph_parameters 是旧图配置。|
|噪声配置|raw_range_sigma_m 为单条原始测距标准差；odom_body_step_xy_sigma_m 和 odom_step_yaw_sigma_rad 为每步生成噪声。旧图窗口参数与传感器生成参数分列。|

样例：状态 0 s 的 Car1 里程为 [0,0,0]，接收于 0.010 s。同一状态的 Car1 UWB 接收于 0.015 s，其中 node_10 为 4.511266439875371 m，前向 peer 为 2.0837122062000426 m。
