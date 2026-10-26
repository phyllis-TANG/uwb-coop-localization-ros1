# T10探索性试跑交接

**已实际运行三种原有基线，严格验收条件仍未获准。** 这轮工作解决“所有实包都停在条件检查”的推进问题，不提供真实定位精度结论。

- 原始输入：PR51成功重试184755可迁移包，run SHA `b9c7b241ff170e17a1d8bc078859c480951db0bdf42f19c2566c13a50fdf2b95`；原bag SHA `f2853240661be0cef53e77cee9a5a33f74cfb1524231d2eb94b2dcacaa57c558`。
- 实际源码：`98f1aaaf4ef48bacbdf84b3efdc2bee01292f993`，运行时工作树干净。原`causal_baselines/model.py`、`replay.py`与PR51合并基准`8dd0bbc`完全一致。只增加自有`t10_exploratory`目录与此报告目录。
- 一包、7个工程假设配置、每组3种原有方法；不能写成21次独立现场实验。总耗时约63秒，23,982行状态回读，数值失败事件0；新增6项测试通过。
- UWB-only单车诊断537帧收敛。距离拟合残差中位数C1≈0.262m、C2≈0.374m，不是位置误差。它不需要base外参、room初始位姿或跨机时间；也不是A端公平方法对照中偷偷新增的第四种融合器。
- 名义配置固定加入peer，相对independent的输出差中位数C1≈2.94cm、C2≈4.88cm，不能称为收益/损害。末10秒变化、时钟/杆臂敏感性见[报告](REPORT.md)。

## 假设与严格门槛

名义起点/朝向、几何中心等于积分点、header总时间调整均为工程假设。时钟接口参数不是已测误差界，固定R/Q未标定。T10末点和视频未作初始化/标定；Car2沿用T09人工末点的来源限定见[澄清](PROTOCOL_CLARIFICATION.md)。

PR51严格模板与入口、公共geometry/manifest、原始/标准化字节都未改。严格来源支持的room融合仍BLOCKED，视频位置参考仍not_accepted；这轮运行不把软件ready/valid当成参考或精度验收。实包RMSE/ATE/精度提升均为空；T09/T11/T13/T15没有定位回放。

## A端如何接续

先读[REPORT.md](REPORT.md)、[nominal_config.json](nominal_config.json)与[source README](../../../../tools/field_20261024_25/t10_exploratory/README.md)。可以用这套输入与显式假设，在A自己的统一EKF中测试候选策略；先验证默认基线不变，再冻结自己的实现/参数，不能把不同版本数字直接混比。保持探索性状态，不绕过原严格入口冒充source-backed结果。

这里没有改A端内核，也没有运行PR47候选。先检查测距/几何一致性和静止条件下的输出响应，不以T10终点反调偏置；补测是否必要由这些结果与所需论文结论共同决定，不因参考尚未批准而默认重录全部八包。

## 产物与恢复

[summary.json](summary.json)包含全部7配置的紧凑结果、计数、敏感性与来源；[ARTIFACTS.json](ARTIFACTS.json)包含完整27MB记录的归档身份、45成员验证和SHA。完整归档由协调窗口单独交付；公开文件不登记私人访问地址，其他环境可用公开输入与固定源码重建。原始bag/MOV、venv和代码仓库不在结果归档中。环境在[environment.json](environment.json)记录为执行后采集，测试日志为[TESTS.log](TESTS.log)。

复现需要自己的新Git外输出目录和PR51已验证输入：

```bash
"$PYTHON" tools/field_20261024_25/t10_exploratory/pilot.py \
  --packet "$EXTRACTED/T10_inputs" --output "$NEW_OUTPUT" --max-seconds 900
```

源程序不覆盖已有目录，无resume混用；参数或源码改变使用新结果目录并另记来源。完整逐事件记录已保存，本环境绝对路径不作为跨窗口协议。未启动车辆/ROS/串口，未删除原件或其他端成果，不自动合并。
