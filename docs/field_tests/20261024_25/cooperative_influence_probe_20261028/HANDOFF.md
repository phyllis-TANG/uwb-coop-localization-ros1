# 交接：第一轮协同影响控制最小开发

已按PR71完成实现、合同、冻结、16单元开发、全部独立回读和归档；建议停止扩大性能矩阵。优先读[一页结论](REPORT.md)、[实现合同](METHODS.md)、[逐车分段表](TABLES.md)、[包含unknown启动的全部有限发布](ALL_FINITE.md)。本轮不宣称新算法贡献、绝对保护级或完整性保证。

## 基准、所有权与实际运行

工作树/home/ubuntu22/uwb-cooperative-influence-minimal-20261028，分支analysis/20261028-cooperative-influence-minimal，基准aa6d272f9dcb7180d7548a06cb11d5d28445b2dd。冻结执行源码312180ef51c6ea4ba394bc85618674ec36ff786d；归档交付源码5855d0e800974dd9c1cd6f2302017b3065bbc1ae。之后仅增加最终回执与交接，不能把交付HEAD混作算法执行SHA。

仅新增tools/cooperative_influence_probe_20261028及本docs目录，不修改公共geometry/manifest、IMU、旧报告、实包或其他任务。原检出experiment/two-car-independent-integrity-bridge-20261023、115b17deb2f848e596d1638a0b45cf360deae947保持；没有reset/clean，没有启动实车/ROS，没有重复双车IMU任务。原长期ROS/rosbag进程不操作。

两个固定已暴露case（seed101正常、Car1四墙共同+.30m），八种逻辑方法：I/J/W025/U/C004/C100/K004/K100。4复用+4派生+8新主图，每个新主图带私有G0，从启动到边缘化不接受peer/协同后验。主图完整cross/affine prior始终保存，发布裁剪/回退不反馈内部历史。预算检查旋转杆臂后两车实际天线XY；缺失/unknown、裁剪、回退、主图与发布成功分开，无拼接协方差。

16/16齐全，无未运行/阻塞单元；所有预登记状态保留，不扩展case/预算。14新合同+27原F0+7解析通过；唯一开发前BUG_01为失败原因误分类，失败源和日志保留，修复后才冻结矩阵。异步运行期间只新增METHODS文档草稿，故部分元数据dirty=true，原样保留；每条源SHA始终与冻结快照一致，并由最终verify_delivery复核，没有修订算法后混用旧结果。

## 结论与停止门槛

4cm约束实际满足预算，保留Car1部分帮助；固定.25缩权未保证4cm上界。但同预算下候选对裁剪的故障期优势仅亚毫米RMSE量级，恢复期Car2约差1mm；两者都61/61参考有效时刻可发布，没有候选额外可用率证据。候选需SLSQP每63帧主图约35–36s，U关闭控制同样昂贵；本轮不值得据此扩大实验。

对称一维约束与裁剪相等；二维/历史中两者轨迹不同不自动成为贡献。当前增加的是图内可行状态和明确发布合同，而不是已验证更有价值的输出。只有另行定义裁剪无法满足的实际需求，并重新登记比较门槛，才考虑下一步；不追加种子寻找好看结果。

原U与J的完整六维发布最大分量差在两个case均小于预登记1e−4m/rad，实际天线最大差0.0592mm；K100与U最大天线差<0.000086mm。来源见review/delivery_verification.json与solver_controls.csv。K004预算最大正超量1.14e−10m，小于1e−7m容差。当前图完整prior并不提供yaw/绝对误差保护，20秒移窗不意味着历史消失；未做干预分离prior误差贡献。

## 取回证据与复核

完整归档54,249,275字节，SHA256 `50c671e3687c3342b8abe99986ecd6a6488de23e24fe112b16b44d9f8fb3f320`。本地/home/ubuntu22/uwb-cooperative-influence-minimal-20261028-artifacts/archives-v1/；NAS/home/ubuntu22/nas/data/uwb_coop_artifacts/cooperative_influence_probe_20261028_v1/，LAN/VPN授权挂载，非公开HTTP。精确命令/manifest SHA与成员说明见ARTIFACTS.json。

239文件逐SHA核验，从NAS原件解包到全新relocated-v1后，归档自身独立reader重新检查16单元；全部CSV/JSON字节一致，timeline解压内容一致，0估计器重跑。原始逐时刻图状态、私有参照、每次SLSQP迭代、因素来源、完整prior和消元、fallback/unknown标志均在归档，不只是汇总表。1008次消元记录包括派生J重复，不当作独立样本；40087次迭代目标和488次双车发布预算通过。

读器不导入在线求解器/Jacobian，只共享旧独立audit标量非peer公式/几何/FD与schema，独立书写固定权和发布检验。所有真值只在评价器，未用于选保护车或预算。原PR70证据仍在原位置/原SHA，本轮复制选定两case所需文件，没有改旧归档。

本轮交付独立草稿PR供审阅，不自动合并。没有剩余后台矩阵，也不继续扩展完整实验。具体PR地址与最终完整HEAD以提交后的用户回执为准。
