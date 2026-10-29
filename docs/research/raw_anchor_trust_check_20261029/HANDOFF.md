# 交接：原始四锚可信依据检查

已完成四项核心成果：TRUST_BASIS、98行DATA_USE_MATRIX、FIELD_MINIMUM、NEXT_GATE。判定为收缩当前图内硬约束的额外机制主张；保留有限相对影响合同。不把全部研究阻塞在绝对可信认证上。当前必须新增动态为0，具体补证先恢复旧记录。本轮没有实现定位器、改变原参数或运行整段估计器。

## 现场与固定身份

- 开始2026-10-29 04:03 UTC；当前工作树`/home/ubuntu22/uwb-raw-anchor-trust-check-20261029`，独立分支`research/20261029-raw-anchor-trust-check`。从实际远端main `3d3c0703c00f369e8828f499c543f2be7aa4193a`创建。
- 用户读取锚点`ae8ee37841ade972be3875968c6eb1b557c3ffdb`仍作为公共元数据读取SHA；实际main新增PR70/74范围，未回退。70份使用来源与实际main内容全部一致，固定PR71/72/73/74/75 HEAD逐项在SOURCE_INDEX中登记。结束时再读远端仍为3d3c0703。
- 原工作树`/home/ubuntu22/uwb-cooperative-a-evidence-20261029`保持clean、HEAD `709c4127c8835f82c137e604d4c53bb541f52a59`；原中文路径检出未切换或修改。适用路径没有AGENTS.md。已有ROS/rosbag进程未操作，未发现另一本任务矩阵。
- 开始约17GB空闲，收尾约16GB；未下载/复制bag或视频，未装依赖。复用已有Python/NumPy环境，全部新外部输出在`/home/ubuntu22/uwb-raw-anchor-trust-check-20261029-artifacts`。
- 预登记提交`982c7552b7f98a35124bf82b6d4da6f7212dbb35`早于四点计算。所有新文件只在指定tools/docs两个目录。最终完整提交号由Git与PR记录确定；DELIVERY_SHA256不自含、不假称自身提交SHA。

## 实际做过与没有做过

**重算**：Car1的23/24/37/54秒，从已保存I状态和原墙输入重建天线三维距离；按原bin及接收截止核对量测、原固定校正、支持身份、peer-free prior来源。计算H0/H1四身份/H2/H3/未知高度的矩阵和一次切空间残差投影。真值只在最后附离线误差列，不进入点位选择、矩阵或信任判断。10项小测试检查解析导数、H1局部条件/H3零空间、未知高度、支持前缀和元数据语义；不是重新验证FGO求解器或定位精度。

**只核对元数据/原记录**：76历史＋22新bag，各自SHA、完整性记录、动作完成状态、用途/禁止用途/缺项/来源及实际暴露；本轮raw SHA重算、逐消息解码、视频读取均为false。旧`this_run_verification`属于旧归档任务，未冒充本轮验证。catalog的`simulation`统一导出为`simulated`（2行），不是实车实验。

**引用原报告**：PR72/75约束相对裁剪的误差、状态连续性、成本和历史尾部；本轮没有重新比较轨迹。PR74一维反例仅适用于其构造，不推广到四锚所有模型。**新建议**：FIELD_MINIMUM及NEXT_GATE重新进入条件，未执行现场动作。

## 原证据取得与可复现命令

本轮复用已有Task A目录，无新NAS访问：

`/home/ubuntu22/uwb-cooperative-a-evidence-20261029-artifacts/evidence-v1/`

其中归档`cooperative_influence_probe_20261028_v1.tar.gz`大小54,249,275字节，SHA256 `50c671e3687c3342b8abe99986ecd6a6488de23e24fe112b16b44d9f8fb3f320`，本轮再次全文件核验；原NAS位置`//10.22.5.135/data/uwb_coop_artifacts/cooperative_influence_probe_20261028_v1/`，已有授权/挂载才可取。展开成员位于`unpacked/cooperative_influence_probe_20261028/evidence-v1/`。完整取得和原成员说明见固定PR75的ARTIFACTS及PR72 ARTIFACTS；无授权不要绕过或反复请求凭据。元数据/数学测试无需归档，原四点重新提取才需要。

真实执行（工作目录为本工作树；输出目录必须不存在；同名运行会拒绝覆盖）：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python tools/raw_anchor_trust_check_20261029/raw_check.py --output /home/ubuntu22/uwb-raw-anchor-trust-check-20261029-artifacts/static-v1
PYTHONDONTWRITEBYTECODE=1 python3 tools/raw_anchor_trust_check_20261029/inventory.py --output /home/ubuntu22/uwb-raw-anchor-trust-check-20261029-artifacts/inventory-v4
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python tools/raw_anchor_trust_check_20261029/test_contract.py
```

重新执行请将输出末尾改成新的目录名；外部原证据位置不同时传`raw_check.py --evidence /你的证据根目录`，目录结构同上。源代码精确SHA见DELIVERY_SHA256和运行receipt，配置/输入/保存解SHA见results/run.json；旧执行源码`312180ef51c6ea4ba394bc85618674ec36ff786d`。新测试只导入本目录斜距公式，用独立标量距离中心差分对照；未导入在线求解器/Jacobian冒充独立验收。

## 修订、检查与剩余项

RUN_INDEX保留全部尝试：inventory-v1因遗漏目录日期后缀失败；v2在审阅中发现按关键词给参考等级会误读“无独立卷尺”，改为逐来源显式名单；v3测试发现simulation枚举误配，v4规范化修正。tests-v1保留一次失败及资源关闭warning，修正后tests-v2为10/10通过。旧输出及失败源码Git外保留；没有因这些导出修订重跑静态点或估计器。

必要验证：98行唯一文件/有效摘要格式、76/22分组、2模拟条目、四留出保护、T10 retry/abort分离、004023异常完成、T14/T15已存在与遮挡未知并列、原证据hash/截止支持、4点导数/秩/零空间、只新增归属目录及git diff --check。测试通过仅说明实现/导出口径，不说明真实定位精度。

剩余：真实H1/H2适用性、几何/高度/噪声有效误差范围、独立物理连续性标准未建立；98包没有本轮新原始QC。没有搜索所有外部历史，因此留出暴露结论限于已查仓库记录。不新增完整定位器，不消费整包留出，不自动合并。本次草稿PR只含自己的增量，不重复加入PR72/75全部文件。
