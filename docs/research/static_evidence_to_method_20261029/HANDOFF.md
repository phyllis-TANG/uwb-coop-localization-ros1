# STATIC-TO-METHOD-02 交接

**完成10个指定实测静态包，判定G3。** 线索可显示测距变化，但现有独立参考不足以唯一分离故障、正常换点及朝向/回位/环境变化；没有运行方法性能对照，不能宣布G2，也未找到G1必要差异。唯一保留缺项是C组逐次回位后的独立天线实际XYZ及误差与静态窗对应，先恢复旧记录，找不到则缩减主张。LAB_DELTA：无需新增采集，必须新增动态0。

## 现场与文件归属

沿用`/home/ubuntu22/uwb-static-to-method-02-20261029`，分支`analysis/20261029-static-to-method-02`，基准`83f64f5af0dda40228ab115a680bb65ef2379e9a`。开始时工作区clean，仅Git外PREFLIGHT记录“等待附件”；用户随后给出了完整正文，该阻塞已经解除。没有新建第二分支，没有更改PR76。预登记/执行源码提交`81cddb372af353181c56c492a18f333d19784cd9`在补算之前。

只新增本docs目录和`tools/static_evidence_to_method_20261029/`。没有适用AGENTS；磁盘约15GB可用，复用已有Python/NumPy/Matplotlib，无新环境。既有rosmaster/rosbag进程未操作，未发现另一个本任务分析进程。没有ROS导入、车辆/串口/网络采集、原件或公共算法修改。

## 七项交付及检查

- OLD_STATIC_EVIDENCE.csv：严格10行，逐包SHA、测量定义、更正、窗口、已有分析、复用/补算、支持与限制。
- COMPACT_RESULTS.csv：334行＝300行本轮分链/窗口统计＋34行明确标记的旧数值复用。复用不是新增独立试验；同一包整包与分窗重叠。
- METHOD_CARD.md：一页候选问题、在线可用性/unknown、同信息基线、反例、评价口径及历史限制。
- DECISION.md：G3及具体实测证据；无方法收益声明。
- LAB_DELTA.md：唯一办公室缺项，当前新动态0。
- RUN_MANIFEST.json：10输入及源/配置/源码/产物SHA，原补算receipt与缓存位置，复用检查/统计计数。
- 本HANDOFF。附CONTRASTS、29项旧统计核对CHECKS、7项新测试TESTS、可读图EVIDENCE及归档INTAKE。

原始数据共补解码60,611条ranges；其他话题仅读取bag记录头计数以定义全包时轴，不重复原始Frame3、Odom/IMU/视频QC。A两包本轮再次核对其旧中位数/有效计数，MAD补算；B没有找到覆盖所需10链的MAD表，补算；C复用已有中位数/STD，并补齐两车各墙及peer覆盖/MAD。选择补算不是把旧分析叫作缺失原件。

时间均用第一条bag消息接收纳秒为0，T02固定去两端5秒；保存整数header用于身份，不把header时钟替换人工录包时轴。分母为该车窗口内收到的ranges帧；缺topic的覆盖为null/CSV空，已收到帧但缺某链可为0。A未记录Car1/peer，不当故障。MAD不乘1.4826。0差值合法，缺失不得填0。没有由测距结果选择边界或阈值。

## 来源、存储与复现

A/B原件：本工作树`datasets/field_raw/20261017/bags/`及`20261018/bags/`，逐包与catalog SHA匹配。C组从既有缓存归档`/home/ubuntu22/uwb-two-car-imu-fgo-20261028-artifacts/retrieved-inputs/UWB_field_20261024_25_20261025_071212.tar.gz`只提取T01–T04和对应notes；整归档SHA `b7cec6f75584e583e66946fd669dc7495d10e3bcbebc0b67fa480b65b53fd1bf`，无下载，不提取/解码其它bag。INTAKE记录原归档和提取成员身份。

Git外根：`/home/ubuntu22/uwb-static-to-method-02-20261029-artifacts`。`input-v1`约55MB原件副本及notes，`stats-v1`保存每条ranges的record ID、整数接收/header及值缓存；`delivery-v1`保存打包结果。原始数据/解码缓存不提交Git。原件获取方式沿catalog/manifest已有归档，不需新凭据；不可达时只登记访问问题。

从仓库根执行，输出目录必须不存在，复跑请换新目录名：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python tools/static_evidence_to_method_20261029/analyze.py --input-dir /home/ubuntu22/uwb-static-to-method-02-20261029-artifacts/input-v1 --output /home/ubuntu22/uwb-static-to-method-02-20261029-artifacts/stats-v1
OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python tools/static_evidence_to_method_20261029/package.py --stats /home/ubuntu22/uwb-static-to-method-02-20261029-artifacts/stats-v1 --output /home/ubuntu22/uwb-static-to-method-02-20261029-artifacts/delivery-v1
PYTHONDONTWRITEBYTECODE=1 python3 tools/static_evidence_to_method_20261029/test_evidence.py
OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python tools/static_evidence_to_method_20261029/plot_evidence.py --csv docs/research/static_evidence_to_method_20261029/COMPACT_RESULTS.csv --output docs/research/static_evidence_to_method_20261029/EVIDENCE.png
```

提取C原件的代码是只读tar成员白名单提取：先比归档SHA，再比每个manifest成员SHA，只写新input目录；相应命令已保存在COMMANDS.md。当前运行不需要重做。

## 验证及共享范围

29项旧数值核对全部通过：A同口径全包中位数/分母精确一致；C原报告三位小数按预登记0.00051m容差一致。7项新测试通过：精确10包、标准库独立统计回读300行、整数接收时间窗、分母/缺失语义、T02固定窗、禁止跨日期/跨车套P1及独立标量三维几何、复用来源身份、有效零差。

补算复用公共`bag_decoder.py`，未改它。独立测试读保存ranges缓存，使用Python标准库statistics和整数纳秒重新筛选/算median/MAD，不导入分析器或在线求解器；因此验证统计/窗口与交付，不是第二套独立原始协议解码或原始Frame3校验。没有必要重复全部旧原始QC。图只展示人工参考量测差、同标称摆位变化和分布尺度，不是位置误差/置信区间。

所有10包完成，无缺项运行、无失败重试或阈值搜索。PR70/72/75仅引用基线/传播/历史报告，PR76仅前置边界，没有重跑合成四快照。T09/T11/T13/T15继续保护，不读取其定位误差。完成后独立提交、认证可用时草稿PR；不自动合并。
