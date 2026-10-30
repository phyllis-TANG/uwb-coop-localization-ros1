# LuSNAR Moon_1 × 双车协同：Isaac Lab 预演

这一目录把已有的 `Moon_1` 六帧融合 LiDAR 点云转换为 Isaac Lab 可加载的月面近似地形，使用同一段真值轨迹让两辆车先后经过，并生成可回放到仓库现有 ROS 1 UWB 话题的测距 CSV。

## 本地数据与转换

输入来自 [LuSNAR 数据集](https://github.com/zqyu9/LuSNAR-dataset)和本机 `LuSNAR-reproduction` 的结果。数据与派生网格不提交到 Git。准备脚本使用 Python 3、NumPy、SciPy、Matplotlib；本机已有隔离的 NumPy 1.26.4：

```bash
cd /home/ubuntu22/uwb-lusnar-moon1-simulation
PYTHONPATH=/home/ubuntu22/LuSNAR-reproduction/.deps python3 \
  sim/isaac_lab/moon1/prepare_moon1.py \
  --ply /home/ubuntu22/LuSNAR-reproduction/results/moon1_fused_lidar.ply \
  --gt /home/ubuntu22/LuSNAR-reproduction/sample/Moon_1/gt.txt \
  --output sim/isaac_lab/moon1/output
PYTHONPATH=/home/ubuntu22/LuSNAR-reproduction/.deps python3 \
  sim/isaac_lab/moon1/make_uwb_replay.py \
  --scene sim/isaac_lab/moon1/output/moon1_scene.npz \
  --output sim/isaac_lab/moon1/output/uwb_replay.csv
```

输出：`moon1_scene.npz`（网格、观测掩码、双车轨迹）、`moon1_preview.png`、`summary.json` 和 `uwb_replay.csv`。默认场景范围为 x = −5…55 m、y = −12…12 m，网格 0.4 m。`summary.json` 记录实际覆盖率。源数据使用 **x 向前、y 向右、z 向下**；转换到 Isaac/ROS 的 **x 向前、y 向左、z 向上**，即 `(x, -y, -z)`。

## Isaac Lab 3.0 / Isaac Sim 6.2（当前 RTX 5060 Ti 主机）

当前主机的 NVIDIA 驱动为 595.99.02；原来的 Isaac Sim 5.1 图形版会在 `librtx.scenedb.plugin.so` 初始化时崩溃。NVIDIA 的 [Isaac Sim 6.2 系统要求](https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html)给出 595 系列驱动，且 [Isaac Lab 3.0 与 Isaac Sim 6.2 兼容](https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/compatibility.html)。因此在独立 Python 3.12 环境运行新版，不修改旧环境或系统驱动。

```bash
uv venv --python 3.12 /home/ubuntu22/isaaclab-moon1-v3-env
uv pip install --python /home/ubuntu22/isaaclab-moon1-v3-env/bin/python \
  'isaaclab[isaacsim]==3.0.0' \
  --overrides https://raw.githubusercontent.com/isaac-sim/IsaacLab/v3.0.0/tools/wheel_builder/uv-overrides.txt \
  --extra-index-url https://pypi.nvidia.com --torch-backend cu130 \
  --index-strategy unsafe-best-match --prerelease allow
```

从仓库根目录启动图形版双车回放：

```bash
OMNI_KIT_ACCEPT_EULA=YES /home/ubuntu22/isaaclab-moon1-v3-env/bin/python \
  sim/isaac_lab/moon1/run_moon1_v3.py \
  --scene sim/isaac_lab/moon1/output/moon1_scene.npz \
  --replay sim/isaac_lab/moon1/output/uwb_replay.csv \
  --export-usd sim/isaac_lab/moon1/output/moon1_scene_v3_lunar.usda \
  --loop --follow-camera --viz kit --device cuda:0
```

`--loop` 持续回放，`--follow-camera` 把两车保持在视口中央。默认 `--terrain-style lunar` 以中性灰显示地形；`--terrain-style semantic` 可切回源点云的月壤/岩石语义颜色。两种模式使用相同的地形几何和轨迹。首次启动 RTX 着色器编译可能需要数分钟。屏幕截图见 `docs/simulation/moon1/`。

## Isaac Lab 2.3.2（旧版）

本脚本按 [Isaac Lab 2.3.2](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/setup/installation/isaaclab_pip_installation.html) 的独立 Python 脚本接口编写，配套 Isaac Sim 5.1 / Python 3.11。需满足 NVIDIA 驱动和 [Isaac Sim 系统要求](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html)。首次运行时按 NVIDIA 提示阅读并接受其许可协议。

旧版虚拟环境位于 `/home/ubuntu22/isaaclab-moon1-env`。当前主机的 595 驱动会使 5.1 图形版崩溃；以下命令仅供在兼容 5.1 的环境中复跑：

```bash
cd /home/ubuntu22/uwb-lusnar-moon1-simulation
OMNI_KIT_ACCEPT_EULA=YES /home/ubuntu22/isaaclab-moon1-env/bin/python \
  sim/isaac_lab/moon1/run_moon1.py \
  --scene sim/isaac_lab/moon1/output/moon1_scene.npz \
  --replay sim/isaac_lab/moon1/output/uwb_replay.csv \
  --export-usd sim/isaac_lab/moon1/output/moon1_scene.usda
```

脚本设置 1.62 m/s² 月球重力、静态地形碰撞、两辆程序化可视车和动态 UWB 连线。车辆按照真值轨迹**运动学回放**，当前不包含车轮接触、月壤滑移或真实无线传播模型。地形空洞采用邻近观测高度填补，`distance_to_observation` 可用于剔除推断区域。UWB 噪声、NLOS 偏置及丢帧由现有 `two_car_model.sample_range` 产生，均为可控假设。

## ROS 1 话题回放

在已有 ROS 1 / catkin 环境下编译仓库后：

```bash
roslaunch uwb_coop_localization replay_moon1_uwb.launch \
  replay_csv:=/home/ubuntu22/uwb-lusnar-moon1-simulation/sim/isaac_lab/moon1/output/uwb_replay.csv
```

回放发布 `/car1/odom`、`/car2/odom`、双向 `/car*/uwb/ranges` 和 `/simulation/inter_car_range_truth`，与原双车模拟器的接口一致。Isaac Lab 和 ROS 1 可分别运行，不依赖 ROS bridge 版本兼容。CSV 回放采用当前 ROS 时间戳，支持 `loop:=true` 和 `car2_time_offset_s`。

## 研究边界

- 当前点云来自六帧 LiDAR 拼接，只覆盖 `Moon_1` 路径的一段，不等于原始 Unreal 场景或全序列重建。
- 约束两车走同一条已观测轨迹，第二车延迟 5 秒。这个设置适合先验证相对测距、时间同步和协同定位接口。
- 待场景验证后，下一步可替换真实轮式机器人 USD、接入接触/滑移模型、增加遮挡几何和非理想 UWB 模型，并用独立场景评估泛化。
- 使用 LuSNAR 数据发表研究时应引用其论文；上游 README 同时提示商业用途需联系作者。
