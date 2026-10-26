# 双车因果回放与三种固定基线：中文交接

更新：参数准备阶段增加了向后兼容的`antenna_body_xy_m`＋`antenna_height_m`接口。
在当前平面yaw模型中不再要求base高度与lever-Z分别已知；旧接口仍可用。
实际人工来源、未知项和四包最小输入见[参数与时钟交接](../parameter_clock_prep/README.md)。
下文实包表与来源哈希保留PR46当时的运行状态，本轮未重跑它们。

本轮从 `4a379da4044a5fd6d36cb8c3e2c53f4a7d120d5b` 独立实现可读取PR45标准化表的三种固定基线。47项测试和10次带噪声合成运行通过；四个开发包已执行source odom frame的Odom-only回放。Room下的独立UWB/Odom及固定peer联合实包运行仍受初始化、天线外参、测量时钟模型未知的条件阻塞，逐项列出并保留空值状态。**独立视觉参考缺失不阻止代码与已具备条件的探索性运行，但不能报告现场定位精度或提升幅度。**

## 分支、复用与实际产物

- 分支 `analysis/20261026-field-causal-baselines`，从指定基准建立新worktree。原检出保持 `work/f14f8bd7c2a33c96f759919b50dff9cc00580014` 且干净，旧PR45分支/工作树也保持不动。
- 仅新增本目录的工具、配置、测试和交接证据；未修改原标准化/QC、`comparison_adapter.py`、视觉文件或公共几何/manifest。未启动车辆、ROS、串口；不改原始数据或Release，不合并PR。
- 本环境确实找到PR45输出，并按仓库登记的run.json SHA及全部9个输出文件SHA验证；[复用凭据](results_summary/reuse_receipt.json)。没有重建标准化或重跑基础QC。本轮使用已有隔离venv，Python3.12.14、NumPy2.2.6；完整pip freeze随结果保存。
- 当前工作树 `/workspace/work/uwb-field-baselines-20261026`；日志/结果根 `/workspace/work/uwb-baselines-20261026-run/`。这些路径只描述本次执行环境，**不是跨窗口共享数据位置**；其他环境应取得并验证原输出，或按PR45现有命令重建一次。程序不硬编码上述旧输出路径。
- 带噪声正式验证版本 `f78764e5a116f60e4896a14b2fb8bd74f69a9196`；实包回放及独立回读版本为其后 `3475f0b`（只增加独立验收工具与留出入口门槛，数学内核相同）。[逐阶段完整提交与来源哈希](results_summary/source_versions.json)。之后只整理本目录交接/归档登记。

## 三种基线与状态定义

| method_id | 实现 | 已知条件 |
|---|---|---|
| `odom_only` | 里程计SE(2)相对增量；room模式从显式初始base位姿出发。`source_odometry`模式原样回放各车odom frame中的base pose | Room模式要求初始位姿及odom时钟映射；source模式只要求合法frame/姿态，不需要room初始化或天线外参 |
| `independent` | 两车各自的UWB/Odom EKF；peer全部排除，车辆间协方差为零 | 各车单独检查初始化、时钟、base高度、天线lever-arm及墙锚条件；一车未知不阻止另一车代码运行 |
| `joint` | 六维状态与完整交叉协方差；固定方差的单向peer更新 | 两车条件均满足才运行；peer固定选择Car1→Car2，反向保留审计且不更新 |

Room状态为每车 `[x_base,y_base,yaw]`，参考点是`base_footprint`，右手系、yaw逆时针、长度m/角rad。Z不估计，`estimate.csv`的`z_m`留空；测距模型中的base高度和三维天线外参必须独立提供。Car2 odom.z不输入高度。marker中心到天线的人工平移不是base到天线外参，代码不会拿它补缺。

里程计使用 `R(-yaw_odom_prev)*(p_odom_now-p_odom_prev)` 求body相对增量，再按当前估计yaw旋转并传播；增量yaw以atan2(sin,cos)跨界处理。每次测距计算 `p_antenna(t)=p_base_anchor + R(yaw_anchor)*[constant_twist_displacement(dt)+R(omega*dt)*lever_xy]`，Z为固定base高度加lever.z，然后取真实三维欧氏斜距。解析Jacobian经过数值差分核对。IMU未作为独立因子。

固定参数见 [field_config.json](field_config.json)：墙距离σ=0.20m、peer σ=0.25m、odom位置过程σ=0.04m/√s、yaw过程σ=0.025rad/√s；初始协方差对角为0.04²、0.04²、0.03²，只有初始位姿已提供时才使用。这些是预先声明、未独立标定的工程基线方差，未按实包/留出误差拟合。测量R固定，过程方差按dt增长，Kalman增益正常随协方差变化；没有按残差自适应调权、终点因子、偏差校准或NLOS剔除。

[synthetic_config.json](synthetic_config.json) 的初始位姿、几何和时钟均明确标记synthetic，真实回放CLI拒绝该配置及带synthetic来源的field配置。[field_config.json](field_config.json)保留未知值null，不继承合成几何或合成初值。

## 到达因果性、异步与相关性

1. 只按bag接收整数ns、原record_index、link_index排序；每次发布只把`receive<=publication`的事件交给滤波器。不按header全局重排，不读未来odom插值。整包留出在CLI和库入口均拒绝。
2. Room测量时间由每车/话题单独提供的整数、围绕原点的仿射header→master映射确定；保存源/目标clock ID、rate有理数、时间原点、来源及不确定性。设备local/system毫秒原值保留审计，但未擅自展开/重释或与ROS时间相减。未套固定网络延迟。
3. 状态锚点为各车最近一次已接收且已接受odom的测量时刻。每条距离按自己的测量时刻，使用各车已到达的odom twist，在最多60ms范围内分别投影到该时刻。旧于任一必要锚点、支持过旧、测量落在未来或到达时延超过200ms的观测明确拒绝，不回写历史、不改时间凑同步。Twist投影是确定性、有界近似，未把其误差或时钟/锚点不确定性完整传播入R，属于基线限制。
4. Raw/bridge保留输入追溯；仅raw primary可更新，bridge、配对歧义/不一致明确排除。同一trace只处理一次，同有向链路重复/倒退测量时间拒绝。每条有向链路固定最小200ms间隔（最多5Hz），所有方法使用相同墙链路规则，降低相关连续帧重复累计信息的影响，但不声称已消除全部时间相关性。
5. 双向peer保留源/目标、原header、映射测量ns、接收ns、device时间、raw/bridge ID。固定Car1→Car2作联合更新，Car2→Car1记录为`excluded_correlated_reverse_direction`；没有把不同时刻两向距离平均成同步观测，也不把两向当独立重复加倍权重。每次peer更新记录两车各自支持年龄、预测斜距、创新及固定方差。
6. 每100ms发布一次，包尾补一次。发布时**保持每车最近odom锚点的后验**，不把它伪称为当前物理时刻的同步姿态；`publish_receive_epoch_ns`和`state_epoch_ns`分列。Room模式同时检查物理测量年龄和接收年龄；source模式源header时钟未映射，`state_epoch_ns`为空，只能按到达记录新鲜度解释。超过200ms显示`stale_odometry_hold/valid=0`，初始化前留空，数值失败保留旧状态并标失败。`valid=1`不是独立位置精度通过。

## 已执行验证与实包状态

[47项测试日志](results_summary/TESTS.log)覆盖：非零初始朝向、yaw双向跨界、倒车、旋转lever-arm/3D斜距、精确仿射纳秒时钟、乱序/晚到/重复、源/桥接去重、无未来数据/未来附加不改过去输出、跨车/peer隔离、断链、collinear退化几何、无解/陈旧/数值失败状态、未知参数门槛及PR45 CSV驱动三方法。

固定种子7/19/43/91/137，普通噪声与延迟/重复/断链两类场景，各12s，共10次正式运行，三个方法所有已初始化状态/协方差均有限；[全量合成摘要](results_summary/synthetic_summary.json)。只用生成真值在各自明确的`state_epoch_ns`评价，不在保持状态的publication时刻伪造误差。这是数值验证而非现场性能：例如普通场景seed91中joint RMSE约0.034324m、independent约0.034154m，保留该略差结果，不筛选种子或宣称joint必然改善。

| 开发包 | 原始frame Odom-only | 有效source状态行/全部Odom-only行 | room独立 / 联合 | 单列说明 |
|---|---|---:|---|---|
| T08 | DONE | 4,849 / 4,856 | BLOCKED / BLOCKED | room起点只有名义指导，base位姿未建立 |
| T10 | DONE | 1,140 / 1,142 | BLOCKED / BLOCKED | 起始间距沿用T09末值，不能代替本次base初值 |
| T12 | DONE | 2,693 / 2,704 | BLOCKED / BLOCKED | 实际初始XY未知；未由终点反求或抄T13 |
| T14 | DONE | 3,270 / 3,278 | BLOCKED / BLOCKED | 遮挡材料/时段未知，未贴NLOS标签 |

每包room阻塞逐车列出：`initial_room_pose`、`odom_clock`、`antenna_body_xyz_m`、`base_height_m`、`range_clock`未知。视觉参考状态另列为“精度评价阻塞”，未列入算法执行门槛。四包共35,940行：11,980行source Odom-only（其中8行尚未初始化、20行陈旧保持），23,960行融合阻塞空值。所有失败/回退时段保留，不只导出成功轨迹。[实包完整状态计数](results_summary/field_summary.json)。

独立回读逐行验证：35,940行总数、23,960行阻塞空值、11,972行已有source pose（含陈旧保持）的record索引、精确header/receive ns、发布前最新可用关系、XY/yaw和原frame全部一致；11,952行source状态满足接收新鲜度。[验收证据](results_summary/field_verification.json)。这验证的是回放与条件门槛，不是定位误差。

T09/T11/T13/T15未进入回放或误差评价。没有现场ATE/RMSE、提升幅度或候选算法成功结论。没有未解决的执行失败；field CLI的退出2表示已保存局部结果但有BLOCKED条件，不是把未运行的融合报成功。

## 输出、检查点与命令

每次运行新建独立Git外目录，已有目录/锁不改写，不支持自动resume混用指纹。输出：`estimate.csv`、`tick_diagnostics.jsonl`（逐发布状态/协方差/退化/回退及累计计数）、`observations.jsonl`（逐事件身份/时间/处理原因）、`diagnostics.json`（逐方法/车辆覆盖率和状态）、`readiness.json`、已解析`config.json`、`run.json`与依赖冻结。配置/源码/输入/输出都有SHA；每100次发布保存检查点，失败也保留来源与已有产物；单次默认600s、最大6h，外层本轮累计预算不重置。

先按PR45入口取得并校验`NORMALIZED_ROOT`。数据路径是自行指定的外部目录，不使用聊天里某台旧机器的绝对路径作为共享协议。若原输出确实无法取得，调用已有`prepare.py`与`normalize.py`重建一次即可，不重复开发或为了运行本工具重跑全部基础QC。

```bash
PYTHON="$VENV/bin/python"
"$PYTHON" -m pip install -r tools/field_20261024_25/requirements.txt
"$PYTHON" -m unittest discover -s tools/field_20261024_25/causal_baselines -p 'test_*.py' -v
"$PYTHON" tools/field_20261024_25/causal_baselines/synthetic_validation.py --output "$RESULT_ROOT/synthetic"
# 四包分别执行；每条必须使用不存在的新输出路径。
"$PYTHON" tools/field_20261024_25/causal_baselines/replay.py   --normalized "$NORMALIZED_ROOT"   --config tools/field_20261024_25/causal_baselines/field_config.json   --experiment T08 --output "$RESULT_ROOT/field/T08" --max-seconds 600
# T10/T12/T14同样执行后：
"$PYTHON" tools/field_20261024_25/causal_baselines/verify_outputs.py   --normalized "$NORMALIZED_ROOT" --results "$RESULT_ROOT/field"   --output "$RESULT_ROOT/field_verification"
```

退出码：0=该执行入口完成；field replay的2=有BLOCKED条件且结果已保存；1=执行/输入失败。Shell串行四包时应接受预期的2并继续独立包，不要用`set -e`误停，也不能把2当三种room定位都通过。

本次完整结果：`/workspace/work/uwb-baselines-20261026-run/results/{synthetic_release,field_release,field_verification}`；stdout/stderr在父目录。完整结果包与SHA清单位于同根的`package/`，仅属当前环境本地归档，不含原始bag/视频、旧标准化大表或venv。归档身份已在[artifact_manifest.json](artifact_manifest.json)登记；另一环境若拿不到该归档，按前述CLI在其已验证输入上复现。

后续实际运行room基线，需要提供**base参考点**的初始XY/yaw与对应第一条odom时刻定义、base高度和body表达的天线三维lever-arm，以及每车odom/UWB header到共同master的时间映射/有效范围/不确定性；视觉marker偏移不能替代这些参数。新信息必须以独立新配置及来源版本登记；不要为让程序跑起来填0或复制合成值。通过独立参考后再另行固定评价规则，当前CLI没有现场误差评价功能。
