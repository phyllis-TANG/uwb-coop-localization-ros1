# 现场与运行计划检查点

2026-10-27 16:34:27 UTC开始，最迟22:34:27 UTC结束（6小时上限），完成可提前结束。

原检出`/home/ubuntu22/双车协同/uwb-coop-localization-ros1`：分支`experiment/two-car-independent-integrity-bridge-20261023`，HEAD `115b17deb2f848e596d1638a0b45cf360deae947`，工作区干净，未切换/修改。已检查祖先和相关检出AGENTS.md，未发现适用文件。

远端main实查`7b67c66f2470d23f6c876f45b6543f72fab66391`（本地main ref较旧，未切换它）。新检出`/home/ubuntu22/uwb-peer-gate-probe-20261028`，独立分支`analysis/20261028-peer-gate-probe`，初始HEAD为上述远端main，status干净。算法/参数/全部19个冻结依赖只从`74fa210e7cf6aa322eaebce19530510edb605d22`提取到本任务Git外frozen-source，绝不随新main变化。

内存31GiB，可用约19GiB；根盘剩余约24GiB。可见已有ROS/rosbag等长期进程（如PID59092 roslaunch、59721 rosmaster、61095 rosbag），不停止、不重复启动、不触碰配置。未发现本任务回放。Linux输出根`/home/ubuntu22/uwb-peer-gate-probe-20261028-artifacts`，不使用Windows C盘，不读取视频、原bag或实车数据。

已逐文件阅读用户指定6份工具源码/配置、SPEC/REPORT/VALIDATION/RUN_MATRIX及质量诊断REPORT；长输出拆分读取。确认D1原本已经是signed pseudo-Huber，peer sigma=.2m、窗口20s、联合状态6维、1s等待、原方向与聚合不变。原24组结果可取得，全部19个执行源码SHA与固定读取基准一致；仍需逐run/input/config/output核验后才记复用。

计划：原样包装G0/G1，G2以独立纯G0辅助图先求同state/cutoff的两车天线三维间距，仅决定本次新peer是否入图。先做等价/单位准入/全拒绝/缺测/辅助隔离跨边缘化/前缀/真实目标函数/联合prior检查；失败保留并另存版本。通过后冻结源码、15份输入及完整45条预定索引。先完成seed101 nominal、peer_bias共6条检查点，再按原索引完成其余39条，最多45个比较单元。原24组如全SHA匹配则复用，另执行15个G2和新增场景6个G0/G1，共21次新比较回放。

这里只做暴露seed成熟基线与开发诊断，无新算法/正式独立验证/概率完好性声明。环境检查沿用cloud-environment-runtime；本会话environment_status不可用，network-policy文件缺失，不从其缺失推断网络就绪。
