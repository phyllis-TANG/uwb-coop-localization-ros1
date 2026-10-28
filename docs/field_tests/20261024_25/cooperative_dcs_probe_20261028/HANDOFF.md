# 交接：最小DCS对照已完成

工作树`/home/ubuntu22/uwb-peer-dcs-minimal-20261028`，独立分支`analysis/20261028-peer-dcs-minimal`。本轮仅新增tools/cooperative_dcs_probe_20261028及本docs目录。原检出仍为experiment/two-car-independent-integrity-bridge-20261023 / 115b17deb2f848e596d1638a0b45cf360deae947且干净，未切换；其他任务/已有ROS进程未操作。开始与收尾实查远端main均ca8fbac4dbdf678074be5fb80bf6aff472d258e6。仅本地提交，没有push/PR/merge，未触碰PR67，没有重新启动双车IMU。

## 已完成

完整阅读任务附件与作者PDF；公式与Phi=1预登记→13新合同+27原合同→源码提交冻结→27旧单元严格复用+9新D3一次执行→36单元独立回读→全seed图表→Git外归档与NAS SHA/迁移回读。没有未运行/阻塞单元，没有失败单元后择优覆盖，未扩大场景/幅度/seed/阈值。执行源码完整SHA为19f1bbaa42d6631cc3c2d8660953d13a17ae76de；归档交付源码为0e9b2fb461655a9cfa5ddce8d61623fcf402cc8e，之后只加交接/校验文件。最终本地HEAD请用`git rev-parse HEAD`，不把交付提交冒充执行提交。

优先读[一页结论](REPORT.md)、[公式对应](FORMULA_MAP.md)、[方法与边界](METHODS.md)、[全部逐车表](TABLES.md)。[运行索引](RUN_INDEX.json)列36完整成员和逐输入/配置/run SHA；RUN_PLAN是结果前版本，FROZEN_DCS_CONFIG为Phi与目标。results含全部精度、两种配对差分、成本、内部权重、prior历史。figures的三张场景同期图均包含三个seed，paired_tradeoffs严格区分两个参考条件。

结论：直接peer偏差DCS有效；Car1共同墙偏差时DCS故障窗所有内部peer权均1，仍有Car1收益/Car2代价且恢复窗持续；D2在该故障窗也没有误拒绝健康peer。小残差不是实际精度保证。保留完整联合prior但没有独立干预量化prior误差贡献，不将20秒移窗称消除历史。未检验其他Phi或真实包，不推断极低概率完整性风险，不据性能预设新算法必须存在。

## 证据取回与独立复核

完整归档32,616,390字节，SHA256 `482b6aaeb9841fa6147853abad02a8e1bcf421939b58f1c9e984045049c2e23c`。本地`/home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/archives-v1/`；NAS`/home/ubuntu22/nas/data/uwb_coop_artifacts/cooperative_dcs_probe_20261028_ca8fbac4_v1/`，需现有LAN/VPN挂载，非公开HTTP。原PR68归档保持原路径/原SHA，本任务只复制已核对的所需27单元，不删除旧证据。

ARTIFACTS.json给精确路径/命令与MANIFEST SHA。取回先sha256sum，再解包新目录。349个成员逐SHA验证；从NAS重新解包到本任务relocated-v1后，用归档自身的独立reader全部回读通过，六个CSV/JSON输出字节一致，timeline解压内容一致。追加verify_delivery核对36组run声明、输入、config实际字节绑定。review提供全部回执；这些过程0估计器重跑。

完整原始测距/聚合/状态/权重/每次线性化与trial/完整prior在归档，不只保留汇总。原在线源码、独立reader、固定SciPy相关源码均有快照。共享范围：独立reader复用旧独立audit的标量非peer公式与FD工具，不导入在线solver/Jacobian；详见METHODS。不应再次运行run_matrix“补结果”，所有结果已齐。

## 限制与后续

所有seed已暴露，只有开发诊断；无新可靠性算法或完整性保障。现有结论足以将“协同收益与健康同伴代价”作为后续研究问题，但本轮不批准新路线/新参数搜索。下一轮若另获授权，先重新登记问题与比较对象；本轮不抢跑任何留出包。

若需取回，按ARTIFACTS命令即可；无需重新下载paper/bag/视频、重复解压原始数据或运行实车。原窗口与公共文件未改。当前任务已结束，无本任务矩阵在后台运行；本地剩余约20GB。早于三小时预算结束。
