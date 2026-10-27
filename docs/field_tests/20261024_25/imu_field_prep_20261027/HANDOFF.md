# IMU B端安全检查点：已转向FGO

用户更正覆盖原EKF主线。本分支从d079c26建立，保存未完成的输入/核验工具草稿；不删除旧工作，不再启动EKF实验批次。

实际完成：独立工作树/venv、读取共同合同与旧审查、找到PR45/51已登记资料、只读检查T10的rosbags索引和一条IMU消息。新增Python文件compileall通过。行为测试0、正式输入包0、新模型实包实验0，不能把工具草稿写成已验收数据包或回放。

可复用：T08/T10允许列表与原SHA、保留CSV原值的JSONL导出草稿、独立rosbags运动字段回读、覆盖/2ms离线关系诊断、因果使用与输出身份检查草稿。代码均未作正式验证，后续复用须测试，不修改原EKF、公共geometry/manifest或旧结果。

结果/依赖/日志：/workspace/work/uwb-b-imu-field-20261027-run/；详见CHECKPOINT.json。该路径只代表本云端，不是共享缓存。原PR45标准化表和38MB归档仍只读保留。

下一步：完整读取固定提交112586ceb9ce674a083fb43f7d8afb7768a15aaf的FGO_REDIRECT.md，在新分支/checkout优先准备004023、005135并复现旧20秒固定窗口因子图；A冻结后做F0–F3。
