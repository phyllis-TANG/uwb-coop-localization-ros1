# 实包参数与时钟准备：一页中文交接

本轮从已合并PR46的 `a82ec421f5e93e9a4432f508f54a037cccc8f0a1` 建立独立分支 `analysis/20261026-parameter-clock-prep`。仅修改本目录及自有baseline的必要兼容代码，未运行新的实包定位，未修改视频/可靠性工具、公共geometry/manifest或原始数据，也未操作其他端进程。

**已消除一个冗余门槛**：平面yaw模型只需天线绝对高度，不需要base高度、杆臂Z分别已知。新增`antenna_body_xy_m`＋`antenna_height_m`兼容接口，直接保留人工C1约0.17m、C2约0.20m及未知不确定度；没有反造base高度/lever-Z、填零或借用合成参数。旧XYZ＋base配置及47项原baseline测试保持通过。新旧配置矛盾会报错，推导保留工程/合成来源而不升级成实测；初始化可绑定精确源记录，时间映射只能在明确有效区间使用。

**仍真正缺少三组输入**：每车水平base→天线杆臂；每个开发包实际初始天线XY/body yaw及源记录绑定（或直接已建立的base位姿）；各主机/话题的采样时间模型及来源/有效区间。T12实际起点未知单列，未由终点或T13补齐。视频独立精度验收仅阻塞精度结论，不阻塞代码准备。

| 交付 | 内容 |
|---|---|
| [参数证据表](PARAMETER_EVIDENCE.md) | 区分人工记录、可推导、工程假设、未知，以及执行/评价用途；起点指导不冒充逐包实测 |
| [时钟证据表](CLOCK_EVIDENCE.md) | 归档源码/行号/哈希与标准化数据共同审计；采样、打戳、发布、VM接收分别说明，不能确定的关系pending |
| [四包就绪矩阵](READY_MATRIX.md) | T08/T10/T12/T14当前能力、缺失项、初始化绑定与未来参数提供方清单 |
| [配置接口](interface_contract.json) / [编译器](interface.py) | 四包模板、来源/单位/坐标/clock/PTS字段，pending不会自动变成provided；编译可操作但不代替标定 |
| [合成敏感性检查](SENSITIVITY.md) | 原5种子、同一观测、单叶改变时钟±20ms/水平杆臂X±5cm/yaw±5°，有限35条件；步长不是实际误差范围 |

源码关键结论：现场Car1 UWB驱动在串口解析后取主机ROS时间，wrapper复用header；Car2归档底盘在读取/积分后分别给odom/IMU取发布时间；bridge复制上游header。Car1底盘及实际nlink打戳代码未取得，Car2源码与运行二进制对应也未建立。NTP“已同步”只是10/24服务快照，不能推出10/25动态时的偏差上界。数据中的60,100组raw/bridge相同header和微秒级odom/IMU相邻header，都不证明硬件采样或跨机毫秒同步；没有把receive−header中位数填作时钟修正。

**验证**：17项新增接口/模板测试及47项原baseline测试通过；35个单因素合成条件完成，观测SHA、单叶变更和车辆隔离检查通过。四包模板实际编译返回预期的BLOCKED，已提供高度后剩余真实未知项仍在。没有未解决的执行失败；没有留出定位评价或现场精度结论。[测试/来源/矩阵证据](results/source_versions.json)。

完整执行argv见[COMMANDS.json](results/COMMANDS.json)，绝对路径仅为本机来源记录，不是共享数据协议。实际执行命令（同一隔离venv；所有输出为新的Git外目录）：

```bash
"$PYTHON" -m unittest discover -s tools/field_20261024_25/parameter_clock_prep -p 'test_*.py' -v
"$PYTHON" -m unittest discover -s tools/field_20261024_25/causal_baselines -p 'test_*.py' -v
"$PYTHON" tools/field_20261024_25/parameter_clock_prep/audit.py --normalized "$NORMALIZED_ROOT" --data-root "$DATA_ROOT" --output "$NEW_OUTPUT/audit"
"$PYTHON" tools/field_20261024_25/parameter_clock_prep/sensitivity.py --output "$NEW_OUTPUT/sensitivity"
# 对四包分别编译；未知输入时退出2并保存配置/阻塞表，不运行定位：
"$PYTHON" tools/field_20261024_25/parameter_clock_prep/interface.py --template "$NEW_OUTPUT/audit/T08_input_template.json" --output "$NEW_OUTPUT/compiled/T08"
```

原PR45标准化输出已按登记产物哈希验证后只读使用；现场原归档SHA也实际重算，并只读提取源码/时钟文本。未重建标准化/QC或重跑PR46实包回放。审计/敏感性正式运行提交为 `510bcfae781623c2596a694a9c905eee7104764b`；后续编译CLI/可选时钟group与测试来源见[阶段哈希](results/source_versions.json)。之后的提交完善接口校验和报告，未改变已运行条件、观测或参数。

本次工作树 `/workspace/work/uwb-parameter-clock-prep-20261026`；日志与完整结果 `/workspace/work/uwb-parameter-clock-prep-20261026-run/`，其中`results/audit`、`results/sensitivity`、`results/compiled`保留run.json、源码/配置/输入/输出SHA及各条件诊断。[归档身份](artifact_manifest.json)与SHA清单放其`package/`，仅描述当前环境，不是跨窗口共享地址；紧凑证据/四包模板已纳入本目录，另一端可以直接从PR取得接口并在自身已有数据上复现。原有各端结果及旧锁均保留，不自动合并PR。收尾时main另合入可靠性PR47（367c053），只读[merge-tree检查](results/INTEGRATION_CHECK.json)无冲突，未修改其路径或实际merge/rebase。总预算2小时，完成可提前结束。
