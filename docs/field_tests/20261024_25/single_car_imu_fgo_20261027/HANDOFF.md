# A端FGO阶段交接（实现中）

用户更正已执行，基于112586ceb9ce674a083fb43f7d8afb7768a15aaf建立/home/ubuntu22/uwb-single-car-imu-fgo-20261027，分支analysis/20261027-single-car-imu-fgo；无AGENTS.md。Python3.10.12，独立venv及Git外结果/home/ubuntu22/uwb-single-car-imu-fgo-20261027-artifacts。PR57确认MERGED，目标main。累计工作从09:04:29 UTC起，09:50转向，未重置预算。

原EKF工作树保留、暂停提交310c815dcf95e69368c7787b8303c3ddaca646cf已推送origin/analysis/20261027-imu-core。37已完成cell+1部分cell及44测试保留，不能当FGO验证。原归档第一次命令因不存在install.log退出2，原档案仍保留，第二版重新从实际文件清单归档；获取及SHA待阶段完成补齐。

当前已完成FGO角积分、F1–F3因子、含bias的半正定边界先验、仅incident因子消元、因果frontend/CLI、独立合成生成器与不导入在线Objective/Jacobian的回读器。旧入口保持逐字节不变。新43项测试、旧37项回归通过，第二版8次smoke及8次独立回读全通过。第一版开发测试38项有1次失败（直接构造图未取config迭代预算），已修正并保留原日志；正式矩阵尚未启动。smoke-v1/2均保留，v2加入真实初始位姿扰动并将Odom源pose置零，避免把外部起点当无误差真值；这些修改均在正式冻结前。

下一步提交本套源码/配置/协议，记录确切Git/SHA，启动唯一正式矩阵：8场景×3开发seed×4臂=96CLI，24份同条件输入，预计4704次发布；单臂/批次120s/7200s上限，无自动重试。之后独立回读、保留全部负结果、输出覆盖/失败及共同有效时段比较，归档并创建main草稿PR。实际历史实包/独立核验由B负责，A不读取原包或留出。
