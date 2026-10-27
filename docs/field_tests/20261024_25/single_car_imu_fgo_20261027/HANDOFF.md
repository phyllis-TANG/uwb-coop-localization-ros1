# A端单车IMU因子图交接

**完成的是现有20秒固定窗口图的实现与合成验证；现场精度尚未验收。** 独立分支`analysis/20261027-single-car-imu-fgo`，工作树`/home/ubuntu22/uwb-single-car-imu-fgo-20261027`，起点112586ceb9ce674a083fb43f7d8afb7768a15aaf。冻结执行提交 **e3a20fe04a6d53973696ec055dbc71eb135e0f77** 已推送；后续提交只添加审阅报告，不改变正式代码/协议。PR57已合并，草稿PR目标main，不自动合并。

协议源码SHA **b377df4988b6307d8edb31f6291c79237324de962a2f41d8397836353e260520**；配置schema SHA `44f8c1b37f047f57fe2f3b929cd936f81b7176114bf5fe24fd9688f55d05de60`。完整接口/字段/来源规则见[INTERFACE](INTERFACE.md)。正式归档中的规范化协议副本字节SHA不同、JSON内容相同，两种身份在[VALIDATION](VALIDATION.md)明确区分；没有覆盖旧证据。

实际完成：新43+旧37=**80项测试通过**；开发smoke两版各8CLI及8回读通过；唯一正式矩阵24输入×F0–F3=**96CLI、4704发布、0运行失败/超时、0/4512求解失败、0次F2/F3 Odom角回退**；96独立数值回读与96误差重算通过。F3最大21帧84变量、瞬时22帧88变量；含bias交叉/offset的QR先验及不双算验证通过。没有启动新的EKF试次，未读取实包/留出/视频/车辆。

探索性发现：恒偏gyro下F3相对固定0的F2有帮助，但仍差于该生成器的未故障Odom基线；24组中17组F3位置RMSE劣于F0，13组劣于F2。正常与偏测距亦有退化；静止零杆臂未可靠识别bias。全量有限输出均计入；正常有效47/49，缺口F2/F3为43/49，共同有效时段另报。不要把数值满秩/小prior、帧数或0失败当精度/风险保证。[一页结论](REPORT.md)、[96条数据的指标表](review/metrics.csv)、[运行索引](review/RUN_INDEX.csv)、[输入SHA](review/INPUT_INDEX.csv)含全部负结果。

失败保留：首轮38测试有1项失败（直接构造图未读取迭代预算），修正前后日志保留；global Python生成配置首次因依赖冲突失败，独立venv成功；旧EKF归档首版命令有缺文件错误，二版成功。正式源码e3a20fe没有为改善结果改参数。历史包复现和F0–F3现场条件性对照由B独立执行；本A未执行，不能计入96次合成。现场精度结论需合格参考/安装与时钟证据，未齐时由B逐项标BLOCKED，不代填参数。

Git外结果`/home/ubuntu22/uwb-single-car-imu-fgo-20261027-artifacts`：formal-v1保存全部输入/config/命令/源码SHA/逐时刻结果，formal-readback-v1为独立读取，figures-v1为图表，checkpoints为阶段检查点，ENVIRONMENT.json含实际依赖与线程设置。取包路径、完整SHA与实际检索验证见同目录[ARCHIVE.json](review/ARCHIVE.json)；NAS仅限已有授权LAN/VPN SMB，不是公开HTTP，也未声称B云端已取到。

```bash
# 取确切A执行代码，在独立组合checkout接入B输入：
git fetch origin analysis/20261027-single-car-imu-fgo
git worktree add --detach /outside/imu-fgo-exec e3a20fe04a6d53973696ec055dbc71eb135e0f77
# 在该checkout，依赖/精确schema见INTERFACE与ENVIRONMENT.json：
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /outside/venv/bin/python \
  tools/single_car_imu_fgo/replay.py --events-jsonl /outside/events.jsonl.gz \
  --config /outside/F3.json --output /outside/new-output --max-seconds 120
```

正式矩阵已完成，不需重跑。若真正中断，只在同源码/协议及全部完成输入/输出SHA匹配、无未索引partial时使用`batch.py --output /outside/formal-v1 --resume`；独立审核用`check_matrix.py --experiment /outside/formal-v1 --output /outside/new-readback`。不能恢复已停止的EKF矩阵。

旧EKF独立保存提交310c815dcf95e69368c7787b8303c3ddaca646cf，origin/analysis/20261027-imu-core；37DONE+1部分输出、44测试保留，[归档](review/EKF_PAUSED_ARCHIVE.json) SHA `a4b19d5bc236cff3bec71e40d40076ddc862a8378606261b6c9b78259e5591b2`。只复用时间/数值核验方法，没有用EKF冒充FGO。

下一步三项：①B整理004023/005135真实gyro/原SHA并复现F0；②取本确切提交，在相同平移/UWB/参数下跑F0–F3并独立核验、同时报覆盖和共同有效结果；③补齐轴/符号/时钟及上游依赖和独立参考证据后，另起冻结版本决定缺口/bias模型，不用人工终点挑参数。累计时间自09:04:29 UTC，09:50转向；归档校验完成于10:34:34 UTC，距原任务开始约90.1分钟（含旧路线保存与转向），低于5小时上限；PR收尾另计入最后检查点。
