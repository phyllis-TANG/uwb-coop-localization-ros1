# 双车静止形变与测距可信度试验（2026-10-23）

基于已合并 PR #38 的 `21d3d48476579837caa6aee4e1027cf57b9d18e3`，只新增可选协方差策略及本轮试验，不修改原模型、旧结果、原始 bag 或默认参数。

本轮结论：近零运动时加强已有相对 Odom 约束能减少静止车轨迹形变；固定的静态测距可信度在三个历史包上有得有失，尚不能替代原模型或证明稳定协同收益。**轨迹缩短不等于绝对位置准确。**

完整结果、正面与负面案例见 [results/REPORT.md](results/REPORT.md)。协议在新动态求解前冻结，SHA256 为 `524656b6662e24727248fffa8668d08c81dc2aabee87021293a544057ff0524b`。

## 改动定义

- 用截至每条相对边结束时刻的两秒原始 Odom 位姿/速度窗口检测近零运动候选，要求完整覆盖、无超过 0.2 秒的间隙。阈值及启动规则见 [protocol.json](protocol.json)。候选只改变已有相对增量协方差，均值包括微小非零运动保持不变；不用实验中的静止车标签或人工终点。
- 墙测距偏置保持 PR38 不变，车间仍无偏置修正。013206、013951、015009 的静态参考偏差用于保守尺度，020151 只作验证。仍采用原 signed pseudo-Huber 损失，没有拟合位置修正函数。
- 四组主消融分别为两项均关闭、仅近零约束、仅可信度、同时启用；再保留同时启用时分别移除 Car1/Car2 全部墙测距的合成缺测对照。
- 各自融合与联合融合使用相同输入、先验、初始化、协方差和求解器，仅联合方法增加每关键帧至多一个聚合车间测距因子。

## 复现

依赖使用 `tools/requirements-single-car-replay.txt`。需按父协议数据清单准备七个未修改的 bag；脚本校验 SHA256。以下命令从仓库根目录执行，结果目录必须不存在：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest discover -s tools -p 'test_two_car*.py' -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run_two_car_stationary_confidence.py --output /tmp/two_car_stationary_confidence_results
python tools/plot_two_car_stationary_confidence.py /tmp/two_car_stationary_confidence_results
python tools/analyze_two_car_stationary_confidence.py /tmp/two_car_stationary_confidence_results
```

已有独立 rosbags 安装目录时，可给 runner 传入 `--dependency-path`；它先加载运行环境的 NumPy/SciPy，再追加 bag 读取依赖。该参数不影响测量、图模型或结果。

## 验证与边界

22 项相关测试通过，包括八种开关/两方法组合的解析 Jacobian、关闭策略逐值复现、未来样本扰动不影响过去候选、非零运动均值保留、掉帧/速度冲突拒绝及求解失败不接受。36 次实际求解全部成功，最多 10 次函数评估；CSV 的 6,168 行轨迹重算指标与 JSON 差为 0；PR38 基线逐点差为 0。实际运行环境、源码/数据哈希、成本账本分别见结果目录的清单和验证 JSON。

所有包均为已知开发数据，没有连续真值。训练 015009 与 L 起点共享几何，验证 020151 与 L 终点共享摆位，不能称独立盲测。Odom 位姿和速度来自同一消息，不是两份独立静止证据；推车、打滑、极低速与驱动死区仍需实验验证。

双车模型仍是全包离线平滑；双车在线顺序回放、联合固定窗口及独立 IMU 因子尚未在本轮实现。
