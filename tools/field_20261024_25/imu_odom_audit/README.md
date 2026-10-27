# 两车IMU/Odom来源与数据审查

本任务对照20261024现场清单第一、第二优先项。只读核验已经登记的38MB现场归档和T08/T10两个开发包，不解码T09/T11/T13/T15，不执行ROS、串口、底盘、归档程序或定位器，不改变既有融合基线。

`audit.py`解析源码、话题身份和字段，对IMU范数、20Hz时间序列、固定协方差、与odom角速度/姿态变化的关系进行诊断。2ms最近header配对是离线数据检查，并非因果融合准入；5秒命令安静候选段不证明物理静止，不批准零偏/噪声标定；相关性或两个不同串口字段都不能证明测量独立。

```bash
"$PYTHON" -m unittest discover -s tools/field_20261024_25/imu_odom_audit -p 'test_*.py' -v
"$PYTHON" tools/field_20261024_25/imu_odom_audit/audit.py \
  --archive "$ARCHIVE/UWB_field_20261024_25_20261025_071212.tar.gz" --output "$NEW_EXTERNAL_RESULTS"
```

输入SHA必须匹配protocol.json，bag单独匹配公共manifest。只提取白名单的两个包及三份Car2源文件；源文件只读检查，不运行。依赖沿用隔离Python3+NumPy环境，不需要安装ROS或rosbags。

## 缺失源码的只读采集

`collect_car_sources.py`兼容Python2/3，运行在对应小车上。只打包当前实际底盘包的src/include/launch、构建描述，并记录源SHA、可读的活动底盘/EKF二进制SHA、架构及native long位宽。只写一个新指定证据文件，不启动ROS、不需要sudo、不操作串口或运动。可用`--package`指定已经观察到的实际目录；不存在就报错。

当前采集只说明当前机器状态；不能自动证明10月25日历史bag使用同一二进制/固件。若节点未运行，源码照常可收集，二进制绑定保留未知。无需为这个收集步骤启动底盘节点。

传回后比较两车源码及旧Car2归档，重点核对串口角速度字段来源、Quaternion_Solution及其采样周期、IMU轴/单位/去重力和上游EKF，不能把Car2源代码当成Car1实现。
