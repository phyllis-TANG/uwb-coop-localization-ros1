# LinkTrack P 现场测试交接记录

> 更新日期：2026-09-19  
> 用途：跨聊天窗口、云端开发环境与现场厂家虚拟机持续交接。每完成一个阶段，都应更新本文件；不能只依赖聊天记录。

## 1. 环境边界与记录口径

- **云端仓库**：本次检查的是 Codex 云端工作副本
  `/workspace/uwb-coop-localization-ros1`，不是现场电脑上的仓库。
- **现场仓库（用户报告）**：`/home/wheeltec-client/uwb-coop-localization-ros1`。
- **目标现场环境（用户报告）**：VMware 虚拟机、Ubuntu 18.04、ROS
  Melodic、Python 2.7。
- 云端不能访问现场的 `/home/wheeltec-client` 或 `/tmp`。凡涉及这些路径的状态，除非用户返回检查结果，否则不得写成云端已验证事实。

本文使用以下标记：

- **已验证**：有仓库内容、保存的命令结果或可复核采集统计支持。
- **用户报告**：由现场用户提供，云端尚未直接复核。
- **待核实推测**：仅是工作假设，不得据此实现协议或更改设备。
- **尚未完成**：仍需后续操作或证据。

## 2. 软件与仓库状态

### 2.1 云端本次已验证

- 2026-09-19 开始记录前，云端检出的分支为 `work`，提交为
  `47e6d2a`（`Merge pull request #10 from
  phyllis-TANG/feat/add-rviz-visualization`），工作区干净。
- 云端 Git 副本没有配置 remote，也没有本地或远端跟踪形式的
  `docs/add-field-test-readiness` 分支。因此该分支名是现场历史信息，不能视为本次开始时的云端状态。
- 仓库中原有交接性质文档只有 `README.md`、`TASKS.md`、
  `docs/environment_setup.md` 和 `docs/workspace_setup.md`；未发现现成的硬件现场交接文档，因此新增本文件，避免分散重复记录。
- 仓库内未发现 `AGENTS.md`；同时检查了仓库父目录以及文件系统根目录两层内的同名文件，均未发现适用于本仓库的额外指令。

### 2.2 已完成的软件基线（仓库与用户报告一致）

ROS 1 包名为 `uwb_coop_localization`。已经完成：

1. ROS 1 catkin 工作空间；
2. `UwbRange` 和 `UwbRangeArray` 消息；
3. 配置驱动的模拟 Anchor 地图；
4. `uwb_simulator.py`；
5. `uwb_logger.py`；
6. 简单二维最小二乘定位器 `uwb_localizer.py`；
7. RViz 的 Marker、Pose 和 Path 可视化。

用户报告模拟链路已在 ROS Melodic/Python 2.7 下验证：约 10 Hz 发布
`/uwb/tag1/ranges`，输出四个理想距离，计算并发布
`/uwb/tag1/pose`，且 RViz 能显示 Anchor、真值、估计点和轨迹。

**重要限制**：真实 UWB 串口驱动尚未实现；`anchors.yaml` 中是模拟坐标，
不是实验室墙上节点的实测坐标；不得把模拟数据当作真实串口数据。

## 3. 硬件清单与安全约束

### 3.1 设备和接口（用户报告）

- 型号：Nooploop LinkTrack P-A、LinkTrack P-B。
- 左侧为 USB，右侧为 UART；当前所有测试只使用 USB，不使用 UART。
- 不连接来源不明的红黑散线。
- 墙上有多台 P-A/P-B，大致交替安装，但目前没有统一上电；原集中电源或转接线束不明确。
- 在电压、极性和接线图确认前，**禁止**给墙上红黑线通电。
- 墙上节点通常预计只需供电，电脑或小车只连接一个数据输出节点；这是系统结构认知，恢复墙上系统前仍需官方资料或现场接线资料确认。

### 3.2 识别信息（用户报告）

| 设备 | USB serial | VID:PID | 驱动 | 已观察设备路径/稳定路径 |
| --- | --- | --- | --- | --- |
| 随机墙上 P-A | `58EA042239` | `1a86:55d4` | `cdc_acm` | `/dev/ttyACM0` |
| 随机墙上 P-B | `5787005935` | `1a86:55d4` | `cdc_acm` | `/dev/ttyACM0` |
| 手持 P-A | `5725005414` | 未单独记录 | `cdc_acm` | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5725005414-if00` |
| 手持 P-B | `5B2E110223` | 未单独记录 | `cdc_acm` | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B2E110223-if00` |

随机测试的一台墙上 P-A 和一台墙上 P-B 均能 USB 枚举，所以不能断言墙上设备全部损坏。手持两台均能被 Linux 识别、创建
`/dev/ttyACM0`、通过串口读写权限检查；用户属于 `dialout`，无程序占用时
`fuser` 无输出。

`/dev/ttyACM0` 编号会变化。后续真实驱动必须支持配置串口，并优先使用
`/dev/serial/by-id` 稳定路径，不得写死 `/dev/ttyACM0`。

### 3.3 不可违反的安全规则

在取得官方协议并备份原始配置之前：

- 不刷固件、不升级 bootloader、不恢复出厂；
- 不写 Network ID、Channel、Node ID 或其他设备配置；
- 不向串口发送未知命令；串口探测优先采用只读方式；
- 不修改墙上节点，不给不明红黑线通电；
- 不仅凭 LED 状态判断测距成功；
- 不在官方协议未确认时猜测二进制字段。

若 NAssistant 只能由 Windows 宿主机使用，应先停止 Ubuntu 的所有串口读取，
再让 VMware 断开 USB 并由 Windows 接管。只允许使用
Read/Refresh/读取配置，逐页截图；不得点击 Write、Save to Device、Reset 或
Firmware Update。分别记录两台手持设备的 Model、Firmware Version、Device
Role、Node ID、Network ID、Channel、Baud Rate、Output Mode、Ranging Mode
和 Update Rate。任何变更之前先保存全部原始配置，且优先只研究手持 P-A
`5725005414` 与手持 P-B `5B2E110223`。

## 4. 已有串口采集结果

以下均为用户提供的现场采集及其统计，云端本轮没有访问原始文件。

### 4.1 P-A

连接方式为 P-A 经 USB 数据线连接电脑，P-B 经 USB 连接充电宝。P-B 持续闪烁，充电宝未立即关闭。

- `115200`：10 秒 1,343 字节，无稳定帧结构，判断为错误波特率。
- `921600`：10 秒 11,022 字节，501 个有效帧，每帧 22 字节，约
  50.1 Hz；501 帧校验全部通过。
- 帧头为 `55 05 16`；末字节等于此前各字节之和的低 8 位。
- 示例：
  `55 05 16 00 00 00 4c 78 0f 00 58 78 0f 00 00 00 00 00 3d 13 00 72`。

距离对照中，曾被误认为“距离”的候选值在约 1 米时均值为
`4930.128`，约 3 米时均值为 `4926.296`，实际移动约 2 米却几乎不变。
因此该字段**不是距离**。

现场已用 `pdftotext` 复核官方 `NLink V1.4`：
`NLink_LinkTrack_Node_Frame3` 表格从 PDF 顺序页 1 底部开始并延续到顺序页
2。字段表明确规定从零开始的字节 18～19 是 `uint16` 电压字段（数值为
`voltage * 1000`），字节 20 是 `valid_node_quantity`。上述 P-A 示例的有效
节点数为 0，电压为约 4.925 V。每个有效节点 Block 为 7 字节：`role(1) +
id(1) + dis(3) + fp_rssi(1) + rx_rssi(1)`；距离原始值为有符号 `int24`，
比例为 `dis * 1000`。这些是用户在现场 PDF 上得到的可复核结果；PDF 本体
仍未加入云端仓库。

### 4.2 P-B

交换连接后，P-B 经 USB 数据线连接电脑、P-A 由充电宝供电；P-B 闪烁，
P-A 常亮。灯态可能反映不同角色，但不能据此确认测距。

- `921600` 下 10 秒得到 8,960 字节，`strings` 无可打印文本，数据为二进制。
- `ff 02` 同步出现 300 次；间隔统计为 `{27: 290, 113: 9}`。
- 因此基础记录主要为 27 字节、约 30 Hz；大约每秒插入额外状态数据。
  早先的“28 字节固定帧”假设已被否定。
- 基础记录负载均为零，形式类似 `ff 02 00 ... 00 ff`。
- 有 9 个完整的 86 字节附加区段；86 字节可能由多个记录组成，尚未证明它是一个单帧。

**待核实推测**：附加区段中的某些 3 字节量约每秒增加 1,000，可能为毫秒运行时间；某些 2 字节量约 4,947～4,952，可能为 USB 电压毫伏值。
这些解释未经官方协议确认，不得写入驱动。P-B 的 `ff 02` 协议仍未确认。

### 4.3 P-A 开关对照

保持 P-B 连接电脑：

- P-A 由充电宝供电并开机时：5 秒 4,480 字节，145 个 `ff02` 记录，
  非零负载记录为 0，负载非零字节总数为 0。
- 拔掉 P-A 并关闭时：统计完全相同。

**当时验证到的采集现象（基于用户统计）**：P-A 开关没有改变 P-B 的输出
速率或全零测量负载。当时这对手持设备尚未建立可观察的 UWB 测距链路。

后续 NAssistant 回读已经确认直接原因：P-A 为 `DR_MODE0 / NODE / N0`，
P-B 为 `LP_MODE6 / ANCHOR / A0`，两台设备 Mode 不一致。按官方手册只修改
P-B 后，真实测距链路已经建立，详见 4.4。

### 4.4 首次真实双节点测距成功（用户现场验证）

两台设备均由 NAssistant V4.3.0.7 识别为硬件 `1.19`、固件
`4.0.2.162`。P-A 原始配置为 System ID 0、System CH 3、Tx Gain 33.5 dB、
`DR_MODE0`、`NODE`、ID 0、`Node_Frame3`、Capacity 20、921600、50 Hz、
LED ON。P-B 原始配置为 System ID 0、System CH 3、Tx Gain 33.5 dB、
`LP_MODE6`、`ANCHOR`、ID 0、`Anchor_Frame0`、921600、100 Hz、LED ON。

在保存 P-A/P-B 原始配置与 P-B 回退计划后，只将手持 P-B 改为：

- `DR_MODE0`、`NODE`、ID 1；
- `Node_Frame3`、Capacity 20、921600、50 Hz；
- System ID 0、System CH 3、Tx Gain 33.5 dB、LED ON 保持不变。

写入后使用“读取参数”逐项回读，全部与计划值一致。未刷固件、未恢复出厂、
未升级 bootloader、未修改 P-A 或任何墙上节点。

P-B 单机时 `Node_Frame3` 帧长为 22 字节且有效节点数为 0；P-A 由充电宝
上电后，P-B 立即发现 `N0`，有效节点数变为 1。两个不同位置的界面读数为：

| 位置 | 距离 | fpRssi | rxRssi |
| --- | ---: | ---: | ---: |
| A | 1.503 m | -81.5 dB | -79 dB |
| B | 4.272 m | -87 dB | -79 dB |

这两个位置没有卷尺真值，不能作为精度标定；但移动后距离明显变化，足以证明
非零真实测距链路已建立。随后在 P-A 保持供电时，从 P-B 只读采集 10 秒，
得到 14,544 字节的 `linktrack_pb_dr_mode0_peer_n0.bin`，SHA-256 为
`353d1f8fe0a734a7385250bb464f990b124f47412b10d80b20d93e0d8f967421`。
该文件尚需离线逐帧解析与统计。

## 5. 官方资料与工具状态

### 5.1 用户报告已下载

现场目录：`/home/wheeltec-client/Nooploop_LinkTrack_downloads_QfZyCf8K/`

```text
LinkTrack_Datasheet_V2.3_zh.pdf
LinkTrack_User_Manual_V2.3_zh.pdf
NLink_V1.4.pdf
nassistant_ubuntu_64bit.zip
```

现场已用 `file`、`pdfinfo` 和 SHA-256 核验这些文件；云端无法访问该现场
目录，且 PDF/ZIP 目前不在仓库中，因此以下仍属于用户返回的现场结果：

| 文件 | 大小（字节） | SHA-256 |
| --- | ---: | --- |
| `LinkTrack_Datasheet_V2.3_zh.pdf` | 4,484,756 | `1ae16c35b899360cd63fb0e050496470d15c0d00fcc347403e6c475d99397e74` |
| `LinkTrack_User_Manual_V2.3_zh.pdf` | 3,106,453 | `5eed4d84fde41eda93d27f7b03fb48dd5f9f282dd25907023ac82c229e1c1e2b` |
| `NLink_V1.4.pdf` | 152,138 | `f4588128a1de8a7e285a8edfaabe9d8567fda733a4a6c44fdd459235f41fbb05` |
| `nassistant_ubuntu_64bit.zip` | 12,014,230 | `589f62351a36b2ca02cdd81a48e269636f5941024bee4d4905841d602ea83456` |

本阶段需要的下载项就是：LinkTrack 数据手册、LinkTrack 用户手册、NLink
串口/二次开发协议和适用平台的 NAssistant。仍需在资料中定位 LinkTrack
P-A/P-B 配对/网络说明及 LED 状态说明；若它们已包含在用户手册中，无需重复下载未知第三方“插件”。

官方入口（需继续以厂商页面为准）：

- <https://support.nooploop.com/linktrack>
- <https://www.nooploop.com/cn/download/>

### 5.2 NAssistant（用户报告）

- NAssistant V4.3.0.7 已成功启动。
- 实际安装位置已核实为 `/home/wheeltec-client/Nooploop/NAssistant`。
- 安装日志显示两个提示来自同一失败链：无法写入
  `/usr/share/applications/NAssistant.desktop`，随后无法把不存在的该文件复制
  到用户桌面。主体、Qt 依赖和维护工具均完成安装；这两个错误只影响桌面快捷方式。
- 启动后检查更新失败，但界面能打开。
- 界面波特率为 `921600`；测试期间保持自动连接串口和自动识别设备关闭。
- 通用 `cdc_acm` 创建的 `/dev/ttyACM0` 不出现在 NAssistant V4.3.0.7 的
  端口列表。根据用户手册 PDF 顺序页 66～67 的 FAQ，现场下载、审查并仅临时
  加载 WCH 官方 `ch343` 驱动后，生成 `/dev/ttyCH343USB0`，NAssistant 成功
  枚举并识别设备。
- 官方驱动仓库为 <https://github.com/WCHSoftGroup/ch343ser_linux>，现场浅克隆
  提交为 `b5515b9`。源码明确包含 `1a86:55d4`，针对内核
  `5.4.0-150-generic` 编译的 `ch343.ko` SHA-256 为
  `5bd2b27dce95090c1c9b9af0d529a9d9e498293981a24fe836e84c10284e3a92`。
  模块仅用 `insmod` 临时加载；没有执行 `make install`，没有复制 udev 规则，
  没有配置开机加载。重启后需重新评估驱动状态。

## 6. 原始数据与证据保存状态

用户报告现场曾生成：

```text
/tmp/linktrack_pa_115200.bin
/tmp/linktrack_pa_921600.bin
/tmp/linktrack_pa_1m.bin
/tmp/linktrack_pa_3m.bin
/tmp/linktrack_pb_921600.bin
/tmp/linktrack_pb_pa_on.bin
/tmp/linktrack_pb_pa_off.bin
```

现场持久化会话目录已由用户核实为：

```text
/home/wheeltec-client/uwb_experiments/20260919_000658_EXP_001_hardware_recon
```

上述 7 个 `/tmp` 文件仍存在，并已复制到该目录的 `raw_serial/`。用户逐个
执行 SHA-256 和 `cmp`，7 组全部一致，因此原始数据备份已确认。关键哈希：

| 文件 | SHA-256 |
| --- | --- |
| `linktrack_pa_115200.bin` | `a44fcf751075a584e103a05fad2269b465ac067c90132d49a767475c9130b6d8` |
| `linktrack_pa_921600.bin` | `c11e7e18aa9c0758b84cf7b48333c16dac9b5d2c6077374efc3087e6763872bd` |
| `linktrack_pa_1m.bin` | `96d00ebcae48e1637c67316ada330e49b9645f5d5773ddc62848b587978f2b87` |
| `linktrack_pa_3m.bin` | `4b5eb6de5420cb28d6246c0ca8b24f12772ad5e22aaf5964358469d9b8d61aac` |
| `linktrack_pb_921600.bin` | `13df28a31070b8ae102b8e86b1db52c990c597cb485dffe374dd25f6e8f7e689` |
| `linktrack_pb_pa_on.bin` | `b365382bf6ddd6772c01a4409b01bd9c2c4053812327e5dc1ae75dad38aedc1b` |
| `linktrack_pb_pa_off.bin` | `14e65044adddc2e35f233e13d34b3ac0c2032c39599afc1105d51c6c3b3c9663` |

配置证据保存在会话目录的 `config_backups/`。P-A 原始配置文字记录 SHA-256
为 `1294ff3eb208c7116d1b17be5cd8654659f2546664786aae39225ea6b5e25e25`；
P-B 原始配置记录为
`cd7694f8531624a26c52203b2e6f52ac3401201b6cb29e216706d742da8c6b96`；
P-B 变更计划为
`5f6ff2a45ab934eb61ba8cc0f20ec7eefbd9f363bbde6adfc27ead29a7c88e64`；
写入后回读记录为
`d4c983cc1229a97906d6fde9e94ec0105b97c03eedcf64411b735dd42762af08`。
这些文件位于现场而非云端仓库，云端没有直接读取它们。

## 7. 尚未完成事项与下一步顺序

1. 将新的 14,544 字节真实测距采集文件复制或上传到云端可访问位置，离线
   验证帧同步、29 字节长度、校验、`int24` 距离、节点 ID 和 RSSI 编码。
2. 用卷尺测量至少两个已知距离并采集独立原始文件，统计均值、标准差、丢帧
   和异常值；目前 1.503 m/4.272 m 只证明响应变化，不是精度标定。
3. 设计真实驱动时处理串口稳定标识问题：官方 `ch343` 驱动当前未生成
   `/dev/serial/by-id`；不得重新写死某个编号。优先补充最小 udev 规则或支持
   可配置端口，并保存设备序列号映射。
4. 为 ROS 包实现独立、可单元测试的 `Node_Frame3` 流解析器，然后接入只读
   串口节点；保持 Python 2.7/ROS Melodic 兼容。
5. 完成离线和单设备回放测试后，再在现场验证 ROS 发布距离。不要在驱动中
   混入模拟数据或使用模拟 Anchor 坐标。
6. 暂不修改 P-A 和墙上节点；P-B 如需回退，严格按已保存的原始配置记录执行。
7. 最后才考虑恢复墙上系统供电、测量真实 Anchor 坐标；必须先确认供电电压、
   极性和接线图。

## 8. 本阶段明确不做

- 本次现场阶段尚未修改 ROS 驱动代码；
- WCH `ch343` 仅临时加载，未永久安装、未配置 udev 规则；
- P-B 只按已备份方案修改一次并成功回读；P-A 与墙上节点未修改；
- 不恢复墙上系统供电；
- 不把尚未取得的现场文件或官方 PDF 描述为云端已核验。
