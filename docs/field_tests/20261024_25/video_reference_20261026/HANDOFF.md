# 视频端交接

见README和五份契约文件。基准4a379da4044a5fd6d36cb8c3e2c53f4a7d120d5b；独立分支analysis/field-video-20261026-reference。
媒体完整性、原件身份、16片2Hz提取、18片完整解码、标定稳定性、逐片空间候选、原odom事件时序、清单补丁已完成。
位置参考批准范围not_accepted；不输出checkpoints/antenna_reference，不可报告轨迹RMSE。T14/T15仍有单事件阶段歧义，人工跟踪失败不足以解决。
Car1车头已确认红色支架/机械臂侧；公共geometry未改。P/Q实际测量和映射、Car2板几何、成像/同步误差界待补证。
保留全部原件、失败运行和工作目录；不要重跑已通过媒体QC，不用Q或融合轨迹反调参考，不自动合并main。
