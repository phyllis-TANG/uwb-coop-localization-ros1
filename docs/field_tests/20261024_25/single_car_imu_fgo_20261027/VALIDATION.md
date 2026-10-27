# 执行与核验记录

## 现场与隔离

原工作始于2026-10-27 09:04:29 UTC，09:50收到转向；累计预算沿用，没有重置计时。FGO独立工作树`/home/ubuntu22/uwb-single-car-imu-fgo-20261027`，分支`analysis/20261027-single-car-imu-fgo`，起点112586ceb9ce674a083fb43f7d8afb7768a15aaf。origin为phyllis-TANG/uwb-coop-localization-ros1；开始时干净，无适用AGENTS.md。PR57已合并，目标main。原single_car_fixed_lag/sequential_replay/run_single_car_fixed_lag与397beb6逐字节相同，本PR没有修改它们或任何B目录。

Python3.10.12独立venv；NumPy2.2.6、SciPy1.15.3、jsonschema4.25.1、matplotlib3.10.9、rosbags0.10.11。实际执行均显式设置OPENBLAS_NUM_THREADS=1、OMP_NUM_THREADS=1、PYTHONDONTWRITEBYTECODE=1；详情见[ENVIRONMENT.json](review/ENVIRONMENT.json)。global Python的SciPy与全局NumPy不兼容，配置生成第一次误用global import失败，随后改回独立venv成功；未修改全局依赖。所有原始输入只读，本A未访问实包/留出/视频，未启ROS/串口/硬件。

## 实际检查与负结果

| 阶段 | 数量/结果 | 证据 |
|---|---|---|
| 新因子图测试首轮 | 38项中37通过、1失败 | tests-initial.log，直接构造WindowGraph忽略config迭代预算，CLI当时已显式传预算 |
| 修正与扩展后 | 最终43项通过 | tests-freeze-candidate.log，阶段旧日志均保留 |
| 原因子图/顺序回放回归 | 37项通过 | tests-old-regression.log |
| 开发smoke-v1/v2 | 各8次CLI全完成、各8独立回读PASS | [SMOKE_INDEX](review/SMOKE_INDEX.csv)，不计入正式矩阵 |
| 正式冻结矩阵 | 24输入、96CLI、4704发布；0失败/超时 | [RUN_INDEX](review/RUN_INDEX.csv)、[INPUT_INDEX](review/INPUT_INDEX.csv) |
| 正式独立源/数值回读 | 96/96 PASS，约10.10s | formal-readback-v1/readback.json及逐cell记录 |
| 独立真值/评价回读 | 96RMSE及4704发布重算PASS | [回读记录](review/04_evaluation_readback.json)，最大RMSE差5.55e-17m |

新测试涵盖解析/有限差分Jacobian、残余bias符号、连续RW联合协方差积分、±π、非零杆臂/初始朝向、角积分分段合成、同刻/截止边界/1ns、源/receive乱序重复、未来/过期、缺口/恢复、轴与单位负例、关闭回归、启动/初值/失败回退无隐含Odom角度、半正定/秩不足边界、不双算因子、100帧有界性、零信息bias、与全历史首次消元前一致及无噪声非线性路径一致、消元后prefix不变性、CLI/序列化与损坏证据负例。

独立audit.py只共享JSON/哈希I/O，不导入在线Objective、Jacobian、积分器或优化器。核验4704次原前端插值/中位数/样本与截止；72078段角积分、原记录身份和左保持；3408次目标函数代价；2016次新图边缘化均记录，仅每13次作一次独立有限差分，共144次。信息矩阵最大差1.07e-7、仿射梯度3.50e-9、目标代价1.07e-14。F0的独立代价仅核对各次最终已接受图，完整回归另外37项。没有把抽样说成全量Jacobian检查。

所有臂累计2688次边缘化。F3实际峰值21个四维关键帧=84标量，瞬时22帧=88；F0–F2为63/66。没有独立对角prior重置，旧因子只消元一次，保留位置/yaw/bias交叉和affine offset。半正定/秩退化负例通过；正式数据未触发求解数值失败，不代表弱几何或bias已可观测。

## 协议字节与语义

执行源码提交为e3a20fe04a6d53973696ec055dbc71eb135e0f77，96个run均记录此HEAD且工作区干净，全部源码SHA运行前后一致。正式源协议SHA为`b377df4988b6307d8edb31f6291c79237324de962a2f41d8397836353e260520`；归档formal-v1/source中保留原字节。

batch将formal-v1/protocol.json另存为排序键的规范JSON，故其**副本字节SHA**为`81d651d7ce3d560e9edbc2cef62d025d24b1f5c7d28fc16731a63f2d5f2579bb`。两份JSON逐项相等，未修改参数或协议；figures.summary中的protocol_sha256指该副本，checkpoint.fingerprint指源文件。两者区别明确保留，不改写既有证据来消除差别。见[03_formal_completed](review/03_formal_completed.json)。schema SHA为`44f8c1b37f047f57fe2f3b929cd936f81b7176114bf5fe24fd9688f55d05de60`。

## 解释边界

F0/F1最大XY差2.01e-15m、yaw差2.02e-15rad；因合成Odom.pose正是积分前一测量角速度产生，二者按构造等价，不证明实包上游等价。所有seed是开发种子，3个种子与相关帧不支持长期风险概率结论。漂移/缺口改变RNG消耗，不将跨场景同编号seed当严格配对噪声；同一输入四臂完全一致。

原平移因子仍需Odom yaw表达；F2/F3删除的是独立Odom yaw约束及预测中的Odom角增量，没有宣称上游全独立。bias均值采用间隔左端常量近似，RW联合噪声为工程模型；时钟不确定度仅披露，未另传播为角噪声。历史非线性因子消元后不能重线性化，弱/静止几何可能不可观测。有限解、满数值秩、收敛或prior矩阵都不是准确性/完好性保证。

全部4704次有限输出都进入全量误差；192次暖启动与24次缺角导致estimate_valid=false，4488次有效。求解尝试4512次、失败0；正常每次47/49有效，缺口F2/F3为43/49。共同有效47或43帧另报。没有只报表现好的片段，也没有人工终点因子。正式结果F3对F0的17/24恶化、对F2的13/24恶化全部保留。
