# A/B安全区域研究接口（非认证输出）

不等待、不改动A/B任务。提供moon_map米/秒、C矩阵、窗口绝对源时刻、相对时刻、input_id与唯一measurement_id；r0..3=Car1锚距，r4..7=Car2锚距，r8=单向peer。观测字段定义见OBSERVATION_CONTRACT；参数身份见MODEL_AND_PARAMETERS。缺测由peer_mask表示，不以零值替代。reference/故障标签仅评价，不能进入在线估计/认证接口。

可用假设：基线独立Gaussian测距.04m、运动.02m、初位置.5m；扩展刻意违反白化/几何假设，发生概率未知；AR1理论协方差可用于未来模型研究。输出局部条件GN对角仅诊断，不是保护界或区域安全证据。真实PR130无连续真值，尚缺噪声/时钟/杆臂/朝向验证；本轮优化结果不能直接当认证区域。
