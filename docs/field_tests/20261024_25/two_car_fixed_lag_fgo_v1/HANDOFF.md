# 双车固定窗口 D0/D1 首轮交接

本轮合成工作完成：模型/接口先提交，20秒联合图、必要测试、3个新seed×4场景×D0/D1共24组、
逐车/逐seed/分窗评价、同期传播图和独立回读均已交付。历史两包清点完成，实包四组NOT_RUN/BLOCKED。

最重要结果：正常场景收益小且部分yaw退化；无质量抑制的peer +1.2m偏差会明显污染两车。
Car2故障窗相对正常RMSE增量 .1379–.1575m，恢复初期仍残留 .0494–.0740m，不能写成统一精度改善。
见 [FINDINGS.md](FINDINGS.md)、[完整报告](REPORT.md)、[同期传播图](car2_fault_propagation.png)。

## 精确版本与边界

- 仓库 `phyllis-TANG/uwb-coop-localization-ros1`；共同基准 `868349b543a03a6a713d1675e1d4ada7d905410c`。
- 独立分支 `analysis/20261027-two-car-fgo-baseline`，worktree `/home/ubuntu22/uwb-two-car-fixed-lag-fgo-v1`。
- 预登记提交 `2149658`；正式执行/源码冻结提交 `1595c982bc4d6206cbe3ad6ddaad774b50898766`。
  之后提交仅为报告/审核/交接，不重新执行或改权。原始参数与依赖SHA在tools的config/dependency_lock，
  执行源代码SHA和24组输入/配置/运行SHA在 [RUN_MATRIX.json](RUN_MATRIX.json)。
- 只新增用户指定的tools和docs两个子目录；未修改旧内核、旧结果、公共几何或原始输入。
  原工作树仍在 `experiment/two-car-independent-integrity-bridge-20261023`、`115b17d`，状态干净。
  检查未发现适用AGENTS.md。ps仅见当前隔离命令空间，不能据此证明宿主机没有其他进程；
  单车/其他worktree不切换、不停止，未启动ROS/串口/车辆、未reset/clean。
- 固定外参是逐车配置参数，不在线估计；peer为两车天线中心3D斜距。没有独立无误差对车位置观测，
  没有IMU/PR61/新peer质量；反向只诊断，同源raw不重复计数，缺测不填0。

## 证据与限制

最终新测试27项（联合22、生成器5）及原单车37项均PASS；[门禁回执](FOUNDATION_TEST_RECEIPT.json)
记录确切源SHA。24组全部DONE，各63联合时刻/每车63输出，前2时刻暖启动，共同accepted61时刻。
全部有限输出和共同有效时段、yaw/相对位置/间距、四个分窗均在CSV/metrics.json并列，没有删掉退化seed。

[独立回读](INDEPENDENT_READBACK.json)24 PASS：3024发布、1464目标、1512输入窗口、1008消元记录。
有限差分只抽每组首末共48次；最大H/g/常数差7.08e-8/8.33e-10/2.50e-15。
D0先验交叉信息为0、D1非零；保留完整6×6和非零offset。[D0独立性](D0_INDEPENDENCE.json)9项PASS，
peer偏差/缺测不改变D0轨迹；墙链故障时Car2只有<5.61e-6的联合优化停止数值差。

全部回放为virtual：24组完整cell耗时累计21.132s、矩阵22.873s，绝非车载端到端实时测量。
update计时只含联合处理，不含两前端聚合/读消息/日志I/O，队列估计也有此限制。
F0浮点±.4s边缘行为保持一致并披露；原整数ns和截止依赖独立复核。
两车首网格不同时BLOCKED，任车Odom包围端点缺失则共同输出无效；整个接收流约3s以上停顿
可能触发pending上限失败，未宣称支持任意整流缺口恢复。详见 [VALIDATION.md](VALIDATION.md)。

[历史就绪记录](HISTORICAL_READINESS.md)给出015334/033248实际bag SHA、原点/朝向/外参/时钟/人工参考来源。
外参原点与Car2符号冲突、初yaw及共同时间配置未验收；无连续真值。没有绕过BLOCKED运行条件性4组，
没有用终点反推初值、迁移Car2 P1到Car1/新场次，未读取T09/T11/T13/T15或未验收视频作精度参考。

## 运行与产物

结果根目录：`/home/ubuntu22/uwb-two-car-fixed-lag-fgo-v1-artifacts`（Git外）。
formal-v1含全部12份消息输入/独立真值与标签/24组发布/先验与消元journal及源码快照；
report-v1为独立评价，formal-audit-v1为独立数值回读。Git只登记紧凑审核报告/图，不含消息大产物。
未新复制bag/视频，也未猜测Linux挂载到I盘的映射；后续本地大文件仍按I盘规则。

实际使用已有只读依赖venv，未修改其他端环境；Python3.10.12、NumPy2.2.6、SciPy1.15.3、
Matplotlib3.10.9。如下命令在仓库根目录，输出目录必须新建于Git外：

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
PY=/home/ubuntu22/uwb-single-car-imu-fgo-20261027-artifacts/venv/bin/python
OUT=/home/ubuntu22/uwb-two-car-fixed-lag-fgo-v1-artifacts
$PY -m unittest discover -s tools/two_car_fixed_lag_fgo_v1 -p 'test_*.py' -v
$PY -m unittest discover -s tools -p 'test_single_car_*.py' -v
# 以下为已实际执行的正式命令；不要原位重跑/覆盖formal-v1。
$PY tools/two_car_fixed_lag_fgo_v1/batch.py --output "$OUT/formal-v1" --test-receipt "$OUT/foundation_test_receipt.json"
$PY tools/two_car_fixed_lag_fgo_v1/report.py --matrix "$OUT/formal-v1" --output "$OUT/report-v1"
$PY "$OUT/formal-audit-v1/driver.py"
```

规范入口是batch，PASS回执须匹配源SHA且Git干净才生成正式seed。本次开发只用7/8，正式101/211/307
冻结后首次生成，各24组只跑一次；生成器单独API不提供防提前查看机制。

完整归档 `two-car-fixed-lag-fgo-v1-1595c98.tar.gz`（12,915,946字节），
SHA256 `0e0156d75374cbe8e2180ef0eb36a7f282b5c59c842b6392d1ae4ae1956c8f8b`。
349个载荷文件从压缩包内逐项读回验SHA；[ARTIFACTS.json](ARTIFACTS.json)登记矩阵、包清单、
归档与独立回读SHA及可取得的共享文件系统位置。未声称上传到公共HTTP或另一台机器独立取回。
归档含冻结源/输入/产物/独立回读/开发失败证据和当时审核快照，最终交接说明以本Git目录为准。

后续应先处理完整接收流缺口策略和实包明确配置/就绪验收；IMU作为新登记消融。首轮结果不等待这些问题，
也不将这些后续项算作已完成。草稿PR不自动合并。
