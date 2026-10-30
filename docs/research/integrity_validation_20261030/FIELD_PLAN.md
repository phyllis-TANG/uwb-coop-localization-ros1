# T02运行前输入/假设
只读取PR77 stats-v1/T02_ranges.jsonl.gz及RUN_MANIFEST，不解码十包。用原bag首receive为相对时间原点；固定窗口5–35/45–75/85–155/165–195/205–238.7543，按1秒receive桶median展示同一four_anchor函数的工程sigma=.2/alpha=.01。此离线receive桶不等同于已验证的在线header/receive时钟模型。使用现有geometry锚点、Car1 .17/Car2 .20m高度，零bias（不迁移P1），nuisance XY自解，无车辆初值输入。几何不确定度未知，响应仅条件诊断。
B2尚缺：与该窗绑定的双车Odom输入及可信初始房间XY/yaw、base→天线外参确认、采样/接收时钟映射；range缓存本身不提供这些。不能伪造初值。T10旧末点(1.48,2.97)m、1.52m间距仍无同次未移动停车窗绑定及量具误差，无新证据不改accepted。PR80参考结论已从实际main只读核对；不改旧参考。
