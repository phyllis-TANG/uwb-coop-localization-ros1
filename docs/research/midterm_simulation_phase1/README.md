# 中期第一批实验补充
先读REPORT.md、GAPS.md、HANDOFF.md。代码在tools/midterm_simulation_phase1。所有路径相对仓库根；原数据及旧结果只读。

环境：Python3.10.12、numpy2.2.6、scipy1.15.3、matplotlib3.10.9，复用已有venv。设OPENBLAS_NUM_THREADS=1、OMP_NUM_THREADS=1、PYTHONDONTWRITEBYTECODE=1；TEMP/TMP/TMPDIR及MPLCONFIGDIR设为本目录tmp。没有安装仿真器或调用实车。

实际执行顺序：
```
UWB_PY=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python
$UWB_PY tools/midterm_simulation_phase1/identifiability.py
$UWB_PY tools/midterm_simulation_phase1/propagation.py baseline
$UWB_PY tools/midterm_simulation_phase1/propagation.py development
# FROZEN.json提交cb3cde7303eedcc58353040cbe370308968ffda9后
$UWB_PY tools/midterm_simulation_phase1/propagation.py confirmation
python3 tools/midterm_simulation_phase1/field_analysis.py
$UWB_PY tools/midterm_simulation_phase1/report.py
$UWB_PY tools/midterm_simulation_phase1/checks.py
$UWB_PY tools/midterm_simulation_phase1/supplement.py
```
输出均拒绝已有文件/单元目录；本次已完成，复核优先读CSV/JSON，不重复运行矩阵。重新执行须独立输出位置并登记新运行身份，不覆盖本目录。脚本当前以本任务目录为固定输出入口，若复跑应在新checkout将输出根参数化后先提交该版本。

输入：PR88 development_static_moving.json、PR91 PROTOCOL、冻结dependency/source锁；静态/动态数据用paper_evidence_completion_20261103包。sources逐SHA核验，单元RUN.json记录配置/事件/truth/generation SHA及执行提交。开发16101/16102，确认17101–17150；50个独立seed、3配对场景、两方法，不是300个独立重复。高频时帧不作统计样本。

开发全扫描两布局×两链×0/.1/.3/.5m；G2仅Car2平移(+1.49,+2.01)，故轨迹形状/噪声/初始化协议配对。Car1 node_2或Car1→Car2单链故障[6,20)。采用已有名义range_bias固定校正，未按新故障再拟合。模拟truth仅评价。

实测：原验证器首先因Git LF与登记CRLF不符失败，见FIELD_IDENTITY_CHECK；恢复到新tmp副本时仍有两历史说明不匹配，见field-attempt1.log。最终只对139个匹配源作严格身份核验，并独立重算全部数值，明确排除两份不被数值分析读取的历史说明；field_readback/REPORT的PASS仅对应139个核对源和数值，整体身份状态以FIELD_RECONSTRUCTION的PARTIAL为准。

没有保留原始事件全副本；代表开发轨迹为估计，不是真值。主表D为M3−M2 MSE；负值收益。t区间仅生成模型描述、不作风险保证。S1_INFORMATION含状态缩放后完整奇异值和最弱方向，先验贡献分列。
