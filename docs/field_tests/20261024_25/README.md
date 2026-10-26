# 2026-10-24–25 双车数据：多端作业入口

本目录是本轮现场数据和后续离线工作的统一入口。**先读本页，再按所属端进入任务书**；不要把旧聊天窗口或历史启动记录当成最新作业指令。

## 当前可以确定的事

- T01–T07静态项目已经完成采集和此前原包检查；故障包、恢复包、试运行各自保留。
- T08–T15八个正式动态bag已经完整解码，共311,144条消息，哈希与现场记录一致。原始UWB与桥接ranges配对检查通过，控制/odom记录的动作序列完整。
- PR49已完成18段原MOV的完整性检查及全片解码，共41,381帧，含T08–T15八段运动视频、八段房间/静态参考视频和两段棋盘原片。T11–T15的ZIP摘要/CRC、MOV身份及解码结果已回填清单；本次协调只复核并采用已有证据，未重复下载或解码。棋盘IMG_7336/IMG_7337已供视频端读取，仍未进入Release附件。
- **视觉位置参考仍为`not_accepted`**：PR49已保存标记提取、逐片空间关系与时间候选；这些候选尚未通过独立空间/同步验收。Car2在T10/T11视角可识别，但三个Q参考片缺可靠自动识别，不能把像素提取或媒体完整性通过当成连续/停点真值合格。
- 文件可读取不等于测距准确、遮挡有效或连续轨迹真值合格。不能据此直接报告定位RMSE或算法改进。
- PR44–49已合并；本轮共同算法基准为`7128abc769121f1f39c3959ce195ac545656c86c`。PR46/48保留三种因果基线及最小参数接口：新实包原odom frame回放有效，room融合仍有参数/时钟缺项。PR47可靠性机制仅在独立合成估计器中验证，尚未移植到同一实包EKF。

**本轮夜间作业优先阅读[统一回放集成与T10闭环任务书](NIGHTLY_INTEGRATION_20261027.md)**；该任务书明确两端所有权和交付门槛。下列早期三端/批处理任务书保留作背景和工具参考，不重复执行已通过的媒体QC。

详见[验收结论](QC_REPORT.md)、[可复现bag检查结果](results/BAG_QC_REPORT.md)及[工具实际验证](results/TOOL_VALIDATION.md)。
交接工具的最终试跑14个作业、132项测试均通过；恢复检查未重复执行已经通过的作业。
这验证有限执行流程，不代表已完成整夜开发或新数据的定位精度评价。

## 文件读取顺序

| 顺序 | 文件 | 用途 |
| --- | --- | --- |
| 1 | 本页 | 当前状态、工作端入口、代码与数据准备 |
| 2 | [manifest.json](manifest.json) | Release数据入口、精确文件名/字节数/SHA256、正式包及留出划分 |
| 3 | [geometry.json](geometry.json) | 坐标、实测打印尺寸、视觉/UWB ID、安装偏移及未确定项 |
| 4 | [EXPERIMENTS.md](EXPERIMENTS.md) | 各实验条件、人工读数及修正，不混用起终点 |
| 5 | [QC_REPORT.md](QC_REPORT.md) | 已通过什么、尚未通过什么 |
| 6 | 本端任务书 | 只执行本端任务和允许修改范围 |
| 7 | [RESULT_CONTRACT.md](RESULT_CONTRACT.md) | 统一输出、时间/坐标/来源和质量字段 |
| 历史 | [SESSION_LOG_ARCHIVE.md](SESSION_LOG_ARCHIVE.md) | 完整现场过程留档；较晚修正覆盖较早状态，不能整段当运行脚本 |

现场原始归档来自[GitHub Release field-data-20261025](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/releases/tag/field-data-20261025)。大bag和视频不提交到Git代码历史；配置、脚本、紧凑结果和报告走各自PR。

## 三端职责

| 工作端 | 任务书 | 当前可并行开展 | 暂不能越过的依赖 |
| --- | --- | --- | --- |
| A：Codex沙盒端 | [RUNBOOK_SANDBOX.md](RUNBOOK_SANDBOX.md) | 复核bag、标准化观测、时间诊断、基线接口与单元验证 | 未有合格独立参考，不调定位误差阈值、不报告全轨迹精度 |
| B：本地视频端 | [RUNBOOK_LOCAL_VIDEO.md](RUNBOOK_LOCAL_VIDEO.md) | 原视频备份/媒体检查、标记提取、相机/板外参与同步、独立检查点验证 | 不用Q点反拟合参考再把同点当独立验证；不默认Car2板平整 |
| C：当前协调端 | [RUNBOOK_COORDINATOR.md](RUNBOOK_COORDINATOR.md) | 维护唯一清单、澄清人工记录、验收A/B产物、冻结对照规则并合并PR | 不擅自把未知量填成实测值，不按测试误差挑选样本 |

[PROMPTS.md](PROMPTS.md)提供可复制给不同窗口的完整任务提示词。希望离线连续运行时，使用[夜间批处理任务书](NIGHTLY_SANDBOX.md)；其范围、预算和恢复规则以该页为准。

## 第一步：固定共同代码基准

PR44–49均已合并，本轮共同算法基准为完整提交`7128abc769121f1f39c3959ce195ac545656c86c`；各自创建独立分支/工作目录并记录任务开始HEAD。也可以从包含本页和新任务书的后续文档提交开始，先确认算法工具与该基准无差异，不必等待文档PR合并。原交接建立于`f14f8bd7c2a33c96f759919b50dff9cc00580014`，它仅是历史基线，不能再当成包含新工具的作业版本。以后若更换算法基准，协调端需另行明确宣布。

所有已有检出先只读检查：

```bash
pwd
git status --short --branch
git branch --show-current
git log -5 --oneline
git remote -v
```

存在未提交/未跟踪内容或本地分叉时，不执行`reset`、`clean`、强制检出或替别人stash。推荐为本轮建新目录，避免影响正在工作的历史仓库：

```bash
mkdir -p "$HOME/uwb-field-work"
WORK_DIR="$HOME/uwb-field-work/bag-$(date +%Y%m%d_%H%M%S)"
git clone --depth 1 https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git "$WORK_DIR"
cd "$WORK_DIR"
git status --short --branch
git log -1 --format='%H %s'
```

以下用于在新的、已确认干净的检出中复现共同算法基准；新任务若已固定只含文档协调的后续提交，不必切回去丢失任务书：

```bash
HANDOFF_COMMIT='7128abc769121f1f39c3959ce195ac545656c86c'
git fetch --depth 1 origin "$HANDOFF_COMMIT"
git switch --detach "$HANDOFF_COMMIT"
```

若坚持复用旧检出，只有在**刚刚确认工作区干净、当前为main、远端正确**后才执行`git pull --ff-only origin main`；失败时保留现状并报告，不自动处理分叉。各端创建自己的任务分支，见任务书。

## 环境边界

本目录的工具运行于现代离线Python环境（Python3.8及以上，建议Python3.10及以上），**不需要ROS**。Ubuntu18厂商VM里的Python3.6不是本轮离线工具的目标环境；已有Melodic/Python2车端节点不改、不升级。不要在已source ROS的系统环境中全局安装依赖。

以下命令为Linux/WSL的Bash写法。Windows本地视频端另有PowerShell示例；若系统、Python或ffmpeg不可用，先报告实际版本，选择合适的离线机器，不为这些分析命令改动车端系统。

```bash
python3 --version
mkdir -p "$HOME/.venvs"
python3 -m venv "$HOME/.venvs/uwb-field-offline-bag"
PYTHON="$HOME/.venvs/uwb-field-offline-bag/bin/python"
"$PYTHON" -m pip install -r tools/field_20261024_25/requirements.txt
```

视频端另需系统可用的`ffprobe`，全片解码需`ffmpeg`。OpenCV属于后续视觉实现依赖，不是下载bag的前提；具体版本与结果一同锁定，不使用未记录版本的自动升级。

## 数据与输出目录

```bash
DATA_ROOT="$HOME/uwb-field-data/20261024_25"
OUTPUT_ROOT="$HOME/uwb-field-results/bag/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_ROOT"
git rev-parse HEAD > "$OUTPUT_ROOT/code_commit.txt"
git status --porcelain=v1 > "$OUTPUT_ROOT/worktree_at_start.txt"
sha256sum docs/field_tests/20261024_25/manifest.json docs/field_tests/20261024_25/geometry.json > "$OUTPUT_ROOT/config_sha256.txt"
"$PYTHON" --version > "$OUTPUT_ROOT/python_version.txt"
"$PYTHON" -m pip freeze > "$OUTPUT_ROOT/python_packages.txt"
```

`DATA_ROOT`必须在Git工作树之外，下载器会拒绝Git树内目录。数据布局固定：

| 路径 | 内容 |
| --- | --- |
| `DATA_ROOT/downloads/<原附件名>` | 校验过的完整Release附件 |
| `DATA_ROOT/extracted/bags/uwb_field_20261025/bags/...` | 正式bag输入 |
| `DATA_ROOT/extracted/camera_reference/...` | 八段参考MOV |
| `DATA_ROOT/extracted/T08_video/...` | T08原MOV；T09/T10同理 |
| `OUTPUT_ROOT/...` | 本次结果；不要覆盖已完成运行 |

数据准备工具仅下载、核对哈希和安全解压，不执行归档内的Python/启动脚本：

```bash
"$PYTHON" tools/field_20261024_25/prepare.py --data-root "$DATA_ROOT" --assets bags --extract
```

已下载并放到`downloads`的相同原文件可以用同样命令加`--offline`验证复用。哈希不匹配就停止并保留文件，不靠改名或删掉校验值继续。已验证的缓存不需每个端反复下载；跨机器仍需独立确认SHA256。

同一台电脑多个端共用`DATA_ROOT`时，**数据准备步骤串行执行一次**，完成后各端并行读取。prepare的锁用于防止同时写同一缓存；遇到已有锁不要直接删除或启动另一次写入。只有确认没有准备进程仍在运行，才按工具报错说明处理遗留锁；也不要绕过prepare手工解压后声称已生成其验证凭据。

## 阶段门槛

1. **资料门槛**：输入哈希、格式、解码通过；未知/待上传单独列出。
2. **参考门槛**：相机参数稳定性、每片空间关系、板到天线关系、独立检查点误差和时间映射得到验证。可能只够支持停点，不强行升级成连续真值。
3. **解算门槛**：先冻结Odom-only、单车UWB/Odom、固定车间因子联合解的输入/参数/评价规则；再依据诊断确定候选机制及消融。
4. **留出门槛**：T09/T11/T13/T15始终按整包留出。可以检查健康状态，但不按其定位误差反调参数，不随机拆帧制造“独立样本”。
5. **交付门槛**：结果包含来源哈希、代码和配置版本、单位/坐标/时间定义、失败项与复现命令；协调端审阅后才合并，不自动合并PR。

本轮只处理离线资料与代码。不开车、不启动ROS节点、不访问串口、不更改固件/UWB配置；无需为离线分析重新启动现场设备。
