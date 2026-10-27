# 下一工作窗口入口

先读[REPORT.md](REPORT.md)、[VALIDATION.json](VALIDATION.json)、[逐配置输出响应](response_by_profile.csv)，再读[桥接工具](../../../../tools/field_20261024_25/t10_reliability_bridge/README.md)。

本轮已完成PR52→PR53的真实T10接入、9方法×7配置、独立回读和父基线零差异验证。没有修改估计器或阈值，不能把输出差异称为精度收益。门控/限幅在全部配置均未触发，候选与shadow-only完全一致。

不要重跑本轮来寻找更好阈值。下一次任务先冻结独立的新协议，再在开发数据检验受控故障响应或T14遮挡；必须保留正常代价及弱墙正确peer的收益损失。不要打开T09/T11/T13/T15定位评价，不动原件、公共manifest/geometry、严格来源配置、PR52/PR53冻结目录；不启动实车或ROS。

PR52和PR53尚为草稿；本交付分支同时以两者为父。建议先审阅父PR，再审阅本轮新增tools/t10_reliability_bridge及本目录。没有自动合并。

完整生成结果保存在Git外归档；公开ARTIFACTS只登记校验与复现方法，完整归档单独交给所有者，不把私人下载链接写进公共仓库。source执行SHA与公开等价SHA的区别已在报告和SOURCE_IDENTITY中声明。
