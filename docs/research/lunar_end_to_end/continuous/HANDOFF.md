# 复核入口

仓库分支research/lunar-end-to-end-validation，更新原PR132，不另开PR，不合并。原2160次研究和旧交付文件保持原样；本轮入口为本目录README/REPORT。

运行冻结SHA：4d9003de7a9320d25374948f9093557b3364c3a3。FREEZE.json固定20个代码/输入/场景文件，后续报告和打包不改正式输入。主120次＋额外30次=150新方法运行/300优化器调用；开发另4次/8调用。扩展比较的40条记录复用主矩阵10条，不重复执行。主阶段1.78336s、扩展0.46564s，独立便携读回另约5.20s。

## 不运行优化器的便携复核

CPU环境需要Python3.10及requirements-cpu.txt列出的依赖。本机已用原独立venv；在另一台机器可创建新的venv安装相同版本，不覆盖系统Python。

```bash
PY=/home/ubuntu22/uwb-lunar-end-to-end-artifacts/venv/bin/python
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "$PY" tools/lunar_end_to_end/continuous/verify_portable.py \
  --archive docs/research/lunar_end_to_end/continuous/EVIDENCE.tar.gz \
  --manifest docs/research/lunar_end_to_end/continuous/EVIDENCE_MANIFEST.json \
  --out /tmp/moon1-continuous-verify \
  --report /tmp/moon1-continuous-readback.json
sha256sum -c docs/research/lunar_end_to_end/continuous/SHA256SUMS
```

out须为不存在的目录，避免覆盖任何旧结果。归档含487个文件：50份共享输入（每份分开observation/reference）、150个结果及attempt/checkpoint、冻结源码副本、路线/地形/USD、两个新增原始点云、111472个带源帧索引的裁剪支持点。核验全部150端点的独立循环残差、complex-step导数、梯度、秩、状态、逐车指标和计数，并再次读取USD的443个时间查询；不会调用优化器。保存的149接受/1未驻点必须被原样复核，不把“读回PASS”误解成150项均接受。

CLOUD_SUPPORT.npz中world_xyz_m为float64变换后的直接观测点，source_frame_index对应CONTINUOUS_SOURCES.json的[1:]条目；裁剪外保留1.6m余量。点云裁剪是便携来源证据，不替换FREEZE中的场景输入。重建完整大范围场景仍需要清单中的原始LuSNAR资产，CPU回放和结果复核不依赖这些本机原路径。

## 已执行的CPU回放

continuous_route.usda可在OpenUSD中打开；timeCodesPerSecond=50、timeCode=0..221、Z-up、米制。CPU_REPLAY.csv保存所有关键帧与半帧位置/距离；POSES.csv保存每车逐时刻车体、天线和姿态。cpu_keyframe_*.png与cpu_replay.gif为从实际重新打开USD取得的天线变换的CPU视图，不是Isaac渲染。体积、杆臂和世界upright姿态规则见ROUTE，未模拟接触。

只重做CPU读回（会在checkout更新同名展示文件；要保留原计时请在另一个副本运行）：

```bash
"$PY" tools/lunar_end_to_end/continuous/replay.py --check-only
```

## Isaac GPU阻塞与可复现入口

```bash
/home/ubuntu22/isaaclab-moon1-v3-env/bin/python tools/lunar_end_to_end/continuous/isaac_replay.py \
  --scene docs/research/lunar_end_to_end/continuous/continuous_route.usda \
  --route docs/research/lunar_end_to_end/continuous/ROUTE.json \
  --out /tmp/moon1-isaac-replay
```

本机实际执行入口后返回2：nvidia-smi无法连接驱动、torch CUDA可用=False、设备数0。完整状态在isaac/STATUS.json和driver.log。未启动SimulationApp、未渲染、未执行动力学；GPU恢复后脚本分支会加载同一USD、推动时间轴、核对5个关键时刻世界天线位置与距离并写PNG。该GPU分支尚未在可用GPU上验跑，不保证跨版本即开即用。未安装或更改系统驱动；当前安装IsaacSim6.2.0.0/Lab3.0.0已记录。

## 结果解释

4.42s上ramp总0.30m，斜率0.067873303m/s。给定地形高度、人工锚点和各向同性仿真噪声下，M3能吸收所设线性peer ramp；这不是与真实传感器趋势的可辨识性证明。真实bias=0时仍有约0.003m/s平均绝对估计趋势，运动异常平均使趋势平移约0.000901m/s。AR1匹配对位置约2mm改善，对虚假趋势只微小改善；白噪声失配约1mm位置恶化。不要把仿真rho视为标定参数。

完整5–14s尚未通过；覆盖和帧高度差断点在GAP_SEGMENTS。后续延长路线应先核查这些帧的高度一致性和历史外参，而不是放宽阈值、增加平滑或从定位效果挑路线。轮地接触和月壤真实动力学留作独立实验。
