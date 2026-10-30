2026-10-31 实验室采集包：UWB 双车协同 + IMU 相对航向验证

目标
保持 UWB 联合定位为主题。采集足够证据验证 IMU 能否辅助相对航向；暂不使用雷达。
本文件夹是待执行计划，不代表已完成安装标定或获得可靠航向。

随身带走
本文件夹、两车实际驱动/启动配置的读取权限、角度标记或量角器、卷尺、
可固定拍摄的手机/相机。已知角度参考应独立于车载里程计。

文件导航
  01_protocol.txt          现场顺序、记录内容与验证条件
  mounting_template.json  每车安装、驱动与坐标系记录，未知项保留 null
  events_template.csv     静止/转向事件及外部角度参考（填写实际发生时间）
  anchors_template.csv    当天实际基站坐标，不直接照搬旧坐标
  record_session.sh       ROS1 录包；只录制，不发车辆运动指令
  inspect_bag.py          离线逐 topic 检查 IMU、时间戳和已确认静止区间
  requirements.txt        离线检查依赖
  .gitignore              避免把本地原始 bag 和生成报告误提交

现场快速开始（先按真实 topic 调整脚本配置）
  rostopic list
  rostopic info /car1/imu
  rostopic info /car2/imu
  rosrun tf tf_echo base_link gyro_link
最后一条仅是单车 frame 名示例。两车 frame 应核实各自名称/命名空间；两车
都叫 gyro_link 不证明它们共享正确 TF，也不证明传感器轴与车体对齐。

  bash record_session.sh car1_static_off /绝对路径/20261031_data
建议每个试验单独一个 bag；按 Ctrl-C 正常结束录制并等待文件写完。
若两车使用独立 ROS master，分别录制并记录两台时钟同步方法；不能仅凭
时间数字接近就当成双车硬件同步。脚本默认要求两车话题，单车录制可通过
REQUIRED_TOPICS 环境变量指定真实的单车必需话题，详见脚本顶部。
复制 mounting_template.json 为当天记录；记录照片、配置和独立视频路径。

回到电脑检查（在本文件夹运行）
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
  .venv/bin/python inspect_bag.py /绝对路径/试验.bag --output audit.json
若已用现场记录确认 bag 收到消息后的第 5~65 秒车辆完全静止：
  .venv/bin/python inspect_bag.py /绝对路径/试验.bag --topic /car1/imu --static-start 5 --static-end 65 --output static_audit.json
静止选项应用于所选 IMU topic；单车静止时必须加 --topic /car1/imu 或真实 topic，
不得把运动小车也按静止解释。工具不会自动标定，也不会自动判断“合格”。

回传材料
原始 .bag、sha256、rosbag info、每车安装记录、事件表、外部参考视频、当天
实际使用的驱动/launch/URDF/TF/参数和版本。先保留原始数据，不覆盖清洗。
原始大文件存入现有数据归档渠道；GitHub 先放文档、校验值和去敏后的摘要。

现有数据提醒
2026-10-18 L bag 中“标记静止”的 Car1 前后 5 秒航向中位数差约 12.9 度，
gyro_z 均值约 0.143 deg/s；必须确认是否真的静止再解释。两车不应共用零偏。
原 bag 约 20 Hz；已见最长约 0.45 秒接收间隔。这些是历史筛查，不是新数据阈值。
姿态 covariance 很小不等于真实误差很小；四元数需先检查有效性并归一化。

收齐材料后能开始：安装/轴向核查 → 零偏和时间检查 → 独立转向验证 → 可选
相对航向回放。通过验证后再评估融合；数据齐全不自动意味着标定通过。
当前展示小窗是离线联合 XY 轨迹回放 + 静态 LuSNAR 点云，不是在线定位。

依据
https://reps.openrobotics.org/rep-0145/
../20261024_SINGLE_CAR_CHECKLIST.md（仓库已有安装与驱动核查项）
