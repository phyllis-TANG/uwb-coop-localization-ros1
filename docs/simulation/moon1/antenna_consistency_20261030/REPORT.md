# PR82 天线坐标一致性修复
从固定ef387a82f8c33d8f4c176568034ad2e89e328fec独立建立。CSV生成共享纯函数：原LuSNAR GT保持NPZ leader/follower身份，按网格贴地得到body，再加1.16m生成antenna。CSV原car*_xyz明确改为天线坐标，新增body_z和gt_z；XY不变。GUI车体取body_z、显示连接取天线xyz，不再次贴地。ROS Odometry child frame改为uwb_antenna，表示CSV天线而非base_link。旧CSV缺body_z必须重新生成，不能与新GUI混用。
零噪声合成平地，横向1m且原GT高度差1m：原算法sqrt(2)，修复后CSV/显示位置三维间距均1m。斜坡测试验证实际贴地高度差进入三维距离。2项纯函数/CLI测试通过。
prepare、CSV生成及USD导出均写来源路径/SHA/参数/可取得状态manifest。未提供原PLY/GT或未生成USD时SHA=null，不能用合成fixture冒充真实数据。保留真实源与派生NPZ身份，不覆盖原GT。没有下载LuSNAR，没有安装Isaac/GPU，GUI和ROS运行未复跑；不称定位、轮地接触、月球物理或RF验证。
实际测试：PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python sim/isaac_lab/moon1/test_antenna_geometry.py
