# HANDOFF：双车gyro与残余bias

状态：实现及合成合同完成，40合成逻辑单元与8旧包条件开发单元有最终采用结果，T08/T10输入完整核验、8全局单元BLOCKED/NOT_RUN。详情从REPORT.md进入。允许继续读取证据；不重启已完成矩阵，不将本轮结果称独立验证或完整性保障，不自动合并。

工作树 `/home/ubuntu22/uwb-two-car-imu-fgo-20261028`；分支`feat/20261028-two-car-imu-fgo`；仅新增本目录与tools/two_car_imu_fgo。固定基础核main ca8fbac4dbdf678074be5fb80bf6aff472d258e6，未改PR67、公共geometry/manifest、旧报告或原始bag。原其他检出和已运行ROS/rosbag进程不操作。

## 版本与执行台账

|版本|完整执行源码提交|用途|
|---|---|---|
|synthetic-v1|0d3943d79569e5e8d3f7a1bbf4a1007a2932bc5f|40个原始合成主运行，含BUG01失败|
|old-matrix-v1|9a8ae25f8d6b8c89c3aa0e48478e3af8d9e018fc|8个旧包主运行，条件开发；含5个BUG01拒绝发布|
|repair-v2|dc30dad99e0e3dd79d6cd6c6a7a38e4de62b667b|仅2合成M2缺口+2旧包M2必要修复，非新条件|
|new-inputs-v1|0529b79cc5050358c5d4401f8ed3420790d7e0e7|T08/T10输入核验，不解算|

最终synthetic-selected-v2采用38原+2修复；old-selected-v2采用6原+2修复。RUN_INDEX同时保留原始、修复和最终选择；各完整plan/index/run.json/source snapshot在Git外归档。实际主执行42+10条；8条旧包31s prefix只是合同控制。两个seed已暴露，相关时刻不是独立样本。

## 文件与复取

- ARTIFACTS.json：Git外证据归档位置、大小、SHA与NAS可取方式；包内EVIDENCE_MANIFEST.json逐文件SHA。没有原视频或其他bag提取件。
- RUN_INDEX.json / SOURCE_VERSIONS.json / FIELD_INPUTS.json / configs：紧凑运行、源码与字段来源清单；RUN_COMMANDS.json与COMMANDS.md是真实执行记录。
- review、figures、SYNTHETIC_TABLES：全40表、完整分母、对照/传播压缩表、原字段读回及测试receipt；细逐时刻在归档timeline、原updates/published.csv。
- 源码接口README/MODEL：真实gyro事件、显式时钟、因果截止、8维prior、null bias语义。所有积分支持片段、窗口、因子身份、消元前后prior和候选解保存在updates；失败不改写为成功。

重新核证先核归档SHA，再运行evidence.py verify，可独立解压到新Git外目录。归档final-source中的evaluate.py/evaluate_field.py可从相对selected索引重新读回，无需优化器重跑；raw字段读回若再执行，需要按SHA取得四个原bag。所有新输出目录必须不存在。留出包不纳入复取/运行范围。

## 验证与剩余项

21项合同+27项冻结F0+43项冻结单车F3通过；48采用单元的完整accepted目标/积分/全部边缘化独立读回通过。8条旧包prefix跨消元不改过去发布；M0/M1精确冻结F0回归。原失败版本和tests-bug01-v2合同失败均留存，修复没有放宽容差。原F0失败候选没有全窗口状态，未声称独立验证其未接受cost。

缺失bias/null/CSV空值与真实零估计误差分别测试；同步图无伪造零线。estimate_valid表示工程可用语义，不是误差界；数值满秩不等于bias可观测。M2仍按联合帧事务处理子求解失败，不声称失败发布等同两个异步单车进程。

旧包严格物理几何/采样时钟仍BLOCKED；现有条件模型只作响应与停点诊断。T08/T10缺逐车odom原点杆臂、绑定初始yaw/位置、每流共同采样时钟，Car2旧bias与P1不跨日搬用。下一步必须先协调冻结这些具体数值/证据，然后另登记新主运行版本。未跑T09/T11/T13/T15/T12/T14，未作新参数搜索，未把未执行写成失败。

本轮无需要继续等待的计算进程；结束前提交推送及草稿PR状态以最终回报完整HEAD为准。后续接手先检查实际Git状态和进程，不假设本文件能代表将来的现场状态。

## 已核验交付归档

`two_car_imu_fgo_evidence_v1.tar.gz`，201199076字节，SHA256 `f47516cd04d6459a284afa84576370cf987245d8a8e28dd3e4e3d981cafa89b2`。NAS新目录`/home/ubuntu22/nas/data/uwb_coop_artifacts/two_car_imu_fgo_20261028_ca8fbac4_v1/`已写入并完整读回一致。归档源码/报告快照提交a9f72b70a1b7e5baef1333d4264779bdba296543；随后分支新增的ARTIFACTS/portable receipt/交付SHA清单为归档外封套，不伪造包含自身SHA。所有48条采用结果已从搬迁解压目录独立重验通过，没有重跑优化。
