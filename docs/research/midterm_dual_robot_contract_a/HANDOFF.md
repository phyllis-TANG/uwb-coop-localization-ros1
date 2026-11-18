# 给B端的早期接口交付

标识DUAL-A-V1；锁定普通PR [DUAL-A-V1] 的早期完整提交SHA，从该SHA读取CONTRACT_READY.json，逐项核对其文件SHA256。source_commit是共同起点，不能把它误当本轮接口HEAD。早期接口一旦发布保持不变，分析追加不改变输入/阈值/检查器。

B实现自己的5D原集合和4D单bias消元，另给no_peer四位置联合基线。A提供独立证书核，不提供求解器。使用input.schema.json/output.schema.json及core.check规范。必须保留所有镜像支、未决叶和预算队列，不能读评价真值缩域、初始化选支或剪枝。发生异常的运行留FAILED/INTERRUPTED/NOT_RUN记录，不删除分母。

确定性正式分母：16×3=48记录。所有记录独立验收；统计逐车面积上界/半径/实际叶宽、叶分类、计算状态及原始成本；5d与4d的实数投影等价不要求有限外包字节相等。外包不同只能比较已证明的包含界，不能用外包真值包含声称精确C包含。

条件随机门槛：48条确定性记录身份和完整证书均通过（预算中止可接受为诚实宽外包，但须列成本和宽度），空集例得到可靠域内空集、边界/零距离例保留真可行点、强制预算例完整保留队列；5D/4D公式与恢复测试通过；16例中除故意强制预算例外至少主矩阵12例的4D搜索在冻结预算内达到请求位置分辨率且无PENDING。否则不启动120个条件随机输入，报告成本门槛不通过。随机阶段完整分母120×3=360；禁止结果筛seed或追加预算/放松证书后冒充同阶段。

RESULTS_READY.json：按results_ready.schema.json包含schema_version、stage、source_commit(B完整SHA)、files、archive_hash、records。files列归档证书及原始成本日志的每文件SHA256；archive_hash=digest(files)，避免自引用。每条记录含case_id,mode,input_hash,execution_status和certificate_file或reason。B代码HEAD通过Git/PR绑定，manifest可位于Git外归档。

A发现B就绪后先锁定B完整SHA与归档哈希，再只读运行check.py archive，不重跑搜索。可核查树中的处理节点数；墙钟和RSS仅能归档绑定并检查记录完整，不假装可由证书逆推出真实性。完整输入、失败分母、全部成本不可删。

两时刻搜索本轮禁止；是否准入取决于独立验收、分支/分辨率和成本证据，不由本接口就绪自动授权。B未就绪时cross_readback=PENDING，A完成自身工作后不无限等待。
