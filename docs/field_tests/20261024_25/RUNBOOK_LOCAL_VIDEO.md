# B端：本地视频、参考精度与同步任务书

先读[统一入口](README.md)、[数据清单](manifest.json)、[几何记录](geometry.json)、[实验表](EXPERIMENTS.md)、[验收结果](QC_REPORT.md)和[输出契约](RESULT_CONTRACT.md)。本端负责**从原片建立可检验的独立参考**，不负责按定位算法效果调整参考。

## 工作环境与文件范围

使用有足够磁盘空间的离线电脑，原始视频和输出均在Git树外。Python3.8及以上（建议3.10及以上），独立虚拟环境；`ffprobe`负责媒体信息，`ffmpeg`负责完整解码。OpenCV及其他视觉依赖属于本端后续实现，需记录版本、参数和源码哈希。

本端任务分支建议`analysis/field-video-20261026-<标识>`。允许新增本端视觉工具、测试及紧凑报告；不改公共几何、bag采集脚本、他端估计器或旧实验结果。配置修正须附测量/图像证据交协调端处理。

## B1：Linux/WSL准备与原片复核

完成入口页固定`HANDOFF_COMMIT`后，在仓库根目录运行：

```bash
git switch -c "analysis/field-video-20261026-$(date +%H%M%S)"
python3 -m venv "$HOME/.venvs/uwb-field-offline-video"
PYTHON="$HOME/.venvs/uwb-field-offline-video/bin/python"
"$PYTHON" -m pip install -r tools/field_20261024_25/requirements.txt
command -v ffprobe
command -v ffmpeg
DATA_ROOT="$HOME/uwb-field-data/20261024_25"
OUTPUT_ROOT="$HOME/uwb-field-results/video/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_ROOT"
git rev-parse HEAD > "$OUTPUT_ROOT/code_commit.txt"
git status --porcelain=v1 > "$OUTPUT_ROOT/worktree_at_start.txt"
sha256sum docs/field_tests/20261024_25/manifest.json docs/field_tests/20261024_25/geometry.json > "$OUTPUT_ROOT/config_sha256.txt"
"$PYTHON" -m pip freeze > "$OUTPUT_ROOT/python_packages.txt"
"$PYTHON" tools/field_20261024_25/prepare.py --data-root "$DATA_ROOT" --assets camera_reference T08_video T09_video T10_video --extract
"$PYTHON" tools/field_20261024_25/audit_videos.py --data-root "$DATA_ROOT" --assets camera_reference T08_video T09_video T10_video --output "$OUTPUT_ROOT/media_qc" --full-decode
```

可以先只准备`camera_reference`，同样把媒体检查的`--assets`缩小；已存在完整附件时可给prepare加`--offline`，无需重传相同视频。`audit_videos.py`输出`media_qc/video_qc.json`，不会提取轨迹，也不证明空间精度。

T11/T12/T13视频ZIP现已在Release，但还没有通过本轮内容验收。完成前一组后，对新增三包运行：

```bash
"$PYTHON" tools/field_20261024_25/prepare.py --data-root "$DATA_ROOT" --assets T11_video T12_video T13_video --extract
"$PYTHON" tools/field_20261024_25/audit_videos.py --data-root "$DATA_ROOT" --assets T11_video T12_video T13_video --output "$OUTPUT_ROOT/media_qc_T11_T13" --full-decode
```

新增三包的原MOV名、时长、解码和实验对应以实际输出为准，不能沿用T08–T10的结果。T14/T15视频仍待上传。

## Windows PowerShell替代准备命令

不要在PowerShell逐字执行Bash的`$HOME/...`和反斜线续行。先按入口页完成新检出和固定提交，然后在仓库根目录运行下面命令；本地Python启动器、ffmpeg须已可用：

```powershell
git status --short --branch
git log -1 --format="%H %s"
git switch -c ("analysis/field-video-20261026-" + (Get-Date -Format HHmmss))
$VENV_PATH = Join-Path $env:USERPROFILE "uwb-field-venvs\video"
py -3 -m venv $VENV_PATH
$PYTHON = Join-Path $VENV_PATH "Scripts\python.exe"
& $PYTHON -m pip install -r tools/field_20261024_25/requirements.txt
Get-Command ffprobe, ffmpeg
$DATA_ROOT = Join-Path $env:USERPROFILE "uwb-field-data\20261024_25"
$OUTPUT_ROOT = Join-Path $env:USERPROFILE ("uwb-field-results\video\" + (Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Force $OUTPUT_ROOT | Out-Null
git rev-parse HEAD | Set-Content (Join-Path $OUTPUT_ROOT "code_commit.txt")
Get-FileHash docs/field_tests/20261024_25/manifest.json, docs/field_tests/20261024_25/geometry.json -Algorithm SHA256 | Format-List | Out-File (Join-Path $OUTPUT_ROOT "config_sha256.txt")
& $PYTHON -m pip freeze | Set-Content (Join-Path $OUTPUT_ROOT "python_packages.txt")
& $PYTHON tools/field_20261024_25/prepare.py --data-root $DATA_ROOT --assets camera_reference T08_video T09_video T10_video --extract
& $PYTHON tools/field_20261024_25/audit_videos.py --data-root $DATA_ROOT --assets camera_reference T08_video T09_video T10_video --output (Join-Path $OUTPUT_ROOT "media_qc") --full-decode
```

如`py`、Python版本、`ffprobe`或`ffmpeg`不满足，报告具体缺项；不要因此在车端安装软件或修改ROS。可选择已有WSL/Linux分析环境，不要求用户立即重装本机系统。

## B2：建立视频清单与观察证据

以下需新增实现并测试，现有媒体QC程序没有替你完成：

1. 保存每片原始SHA256、视频/实验对应、实际帧PTS、旋转元数据、编码与显示坐标变换、镜头/倍率/设置的已知或未知项。平均帧率不一定精确30，不能机械使用`frame_index/30`。
2. 对参考片先出接触表、清晰度和可见性统计，原图保留；不把检测失败帧隐藏。仅保留与本任务相关媒体字段，不导出GPS等无关元数据。
3. 为每段正式运动片核实实际运动是否被覆盖，不能因视频/bag时长不同就认定错片，也不能默认两边起点同步。

参考片当前对应关系只是按画面和顺序初判：IMG_7364为P1–P4；IMG_7365/7366/7367为Car2三个检查位置；IMG_7369/7370/7371为Car1三个位置；IMG_7373为Car1转向补片。Q点实际摆位/方向及文件逐一对应仍需协调端核对。不得用文件名推定精密坐标。

正式视频：T08=IMG_7341.MOV、T09=IMG_7343.MOV、T10=IMG_7347.MOV，归档身份已核对，但同步、动作覆盖、空间精度尚未通过。

## B3：解决标记提取与平面假设

- 视觉字典`DICT_4X4_50`，Car1视觉ID0/UWB node_1；Car2视觉ID1/UWB node_0，不能对调。
- 实际黑框边长144mm，不使用PDF/文件名标称150mm。
- Car1参考抽样16/16识别ID0，仅证明所取帧可识别。Car2参考抽样12帧及每片一个4K诊断帧未识别ID1，板边可见弯曲迹象；不能直接称为文件损坏或只有“整体轻微倾斜”。
- 先诊断候选轮廓、边框/白边、真实图案、像素采样与板面形状，优先从既有4K原片恢复观测。可以研究人工初始化/轮廓/跟踪等替代提取，但必须保留质量标志、独立验证与失败情况；模板能跟踪不等于几何中心已准确。
- 如果板形变导致平面PnP假设失效，需要说明模型适用范围和不确定性；不能调参数直到输出“看起来正确”就当真值，也不立即要求全部现场重录。

## B4：标定、安装转换与空间验收

棋盘实际为10×7格、9×6内角点，两方向格距用192/10mm及134/7mm。IMG_7336/7337已存在原片身份与初步分析；这两份尚不在当前Release资产清单内，若本端无原件先报告缺项，由协调端提供同一哈希来源，不拿社交软件压缩副本替代。

IMG_7337含竖幅显示旋转信息。必须统一编码/显示坐标和内参变换，不能将竖片拉伸成横片后拟合。历史试算K/D仅为探索值，参数稳定性尚未通过；不可把它复制成正式已批准内参。

每段录像内部固定、片间相机角度可能变化。对每片分别建立相机至房间关系，可以用共同未移动背景辅助，但不能把当前P点参考片的单个外参直接套到全部旧运动片。地面单应不能无高度修正地用于车上抬高标记。

在车体方向对齐坐标（x向车前、y向车左、z向上）中，黑框中心指向天线的人工偏移为：Car1 `[+0.07,-0.13,-0.20]m`，Car2 `[-0.17,+0.025,-0.03]m`。它们不是已经旋转到ArUco自身坐标中的外参；需结合图案相对车头姿态。Car1板水平为操作员报告，Car2倾角未测且存在弯曲疑问，均须保留测量不确定性。

P点用于建立房间参考时，不再把同一P点的小拟合残差当独立精度。Q1/Q2/Q3为独立检查，实际点位/高度确认前不能冒充精密真值。**不得把全部Q点拿来拟合，再声称在同点验证通过**；若需要另选拟合子集，提前与协调端冻结划分并保留真正未参与拟合的验证点。

交付`reference_validation.json`及报告：分别列每车、点位、朝向的实际误差、有效率、未知高度/偏移/形变影响、支持的评价范围与判定依据。容差由协调端在看测试误差前确定，不能事后依结果放宽。

## B5：时间映射及最终参考输出

保留视频PTS、ROS header、bag接收时间、UWB设备时间各自时钟域。按可观察的运动起止、转弯或实际同步事件估计每片映射，报告拟合窗口、残差、漂移/偏移不确定性与对误差评价的影响。不能用NTP显示已同步、录制文件名或理论`sleep`时长代替实际验证。

产物建议位于`OUTPUT_ROOT/reference/`：`video_inventory.csv`、`marker_observations.csv`、`frame_transforms.json`、`time_mapping.json`、`reference_validation.json`、`antenna_reference.csv`。字段按[统一契约](RESULT_CONTRACT.md)。如果空间/时间质量只能支持停点，就交付`checkpoints.csv`和适用范围，不强行输出连续“真值”。

B端不能根据UWB/Odom融合结果反调相机轨迹使其一致。完成后向协调端依次交：原片身份/PTS → 标记提取诊断 → 空间/独立检查结果 → 时间映射/覆盖 → 带质量标志的参考及限制。先等参考验收，再供A端作定位误差评价。保留失败和弱可见片，未经批准不重新现场采集。
