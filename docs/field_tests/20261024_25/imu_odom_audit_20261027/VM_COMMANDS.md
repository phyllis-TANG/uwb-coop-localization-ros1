# 虚拟机：以后可选的两车来源补证

**用户当前不在实验室，本步骤暂缓；它不是当前离线IMU原型的前置条件。**

这一步取回当前底盘源码和可读的活动二进制身份。不启动ROS、底盘或运动，不改设备参数，不需要sudo。车辆只需开机可SSH；没有节点运行也可取源码。每车会写一个新的证据压缩包；同名存在会拒绝覆盖。当前取回资料不能自动证明历史运行版本。

下面整段粘贴到**虚拟机 wheeltec-client@ubuntu**终端，不在小车SSH终端执行。需两车仍在tas506、地址仍为.10/.24；SSH失败就停止并保留报错，不需要重新扫描网络或重录路线。脚本默认包目录来自已观察过的实际路径；找不到会报错，届时再指定实际目录。

```bash
AUDIT_STAMP="$(date +%Y%m%d_%H%M%S)"
AUDIT_DIR="$HOME/imu_odom_sources_$AUDIT_STAMP"
mkdir -p "$AUDIT_DIR"
if curl -fL 'https://raw.githubusercontent.com/phyllis-TANG/uwb-coop-localization-ros1/d3439ebefc36eeee184131038b2f209838431cc4/tools/field_20261024_25/imu_odom_audit/collect_car_sources.py' -o "$AUDIT_DIR/collect_car_sources.py" &&
printf '%s  %s\n' 'd5dad52ca8bad95953a175a1c545de5cc30268b04e393cde30fb5a2c4ad6b889' "$AUDIT_DIR/collect_car_sources.py" | sha256sum -c -; then

for CAR in car1 car2; do
  if [ "$CAR" = car1 ]; then CAR_IP=192.168.31.10; CAR_PY=python; else CAR_IP=192.168.31.24; CAR_PY=python3; fi
  REMOTE_FILE="/home/wheeltec/${CAR}_imu_sources_${AUDIT_STAMP}.tar.gz"
  ssh "wheeltec@$CAR_IP" "$CAR_PY - --car $CAR --output $REMOTE_FILE" < "$AUDIT_DIR/collect_car_sources.py" || break
  scp "wheeltec@$CAR_IP:$REMOTE_FILE" "$AUDIT_DIR/" || break
  gzip -t "$AUDIT_DIR/${CAR}_imu_sources_${AUDIT_STAMP}.tar.gz" || break
done
else
  printf '下载或校验失败，未连接小车。\n' >&2
fi
ls -lh "$AUDIT_DIR"
```

先确认curl成功及SHA显示OK再运行for循环；不要忽略下载或校验失败。若已有运行节点，采集器读取/proc中匹配的底盘/EKF可执行文件并计算SHA，不发送任何ROS请求或控制命令。只采集源/构建描述及有限进程元数据，不导出完整环境或凭据。

把生成的两个car*_imu_sources_*.tar.gz提供给分析窗口即可；缺哪个先回传哪个，另一车已有历史归档可继续对照。不要为本步骤重新摆车、开启定位节点或做运动。
