# A端 P-S1b 交接

实际checkout `/home/ubuntu22/uwb-midterm-s1b-identifiability-20261116-clean`；分支 `research/midterm-s1b-identifiability`。固定基准 `df323eccdffd375a2fb255ebbfd734b6c2be4aac`，未修改或自行合并PR97。原工作区仍为 `115b17deb2f848e596d1638a0b45cf360deae947`，状态干净。

完整提交索引：

- 协议冻结：`005c78f3c466f6892b53ae7c34410ef177cee377`。
- 分析实现：`b64a9c7ff0860f92159d392a608a3b7b07064c9f`；清空PYTHONPATH的完整回放在该HEAD执行。
- 结果、报告和接口：`eac874af58e949b9bb06eb97e3d2443ea99fe4cd`。
- 交付内容及CSV格式检查完成：`86883ad3e159fc859366e888389419af94c4b80e`。
- 本HANDOFF为上述交付的后续登记提交；为避免文档自引用哈希，不伪造自身提交号。克隆后以 `git rev-parse HEAD` 获得当前分支完整HEAD，最终交付消息另列实际推送HEAD。

A1–A7完成：解析/数值差分、三种信息来源加PR97强先验对照、全谱与完整零空间、奇异位置块的SVD消元、初值/中心/强度分离、真实观测噪声、逐车位置与偏差误差/失败/先验依赖。冻结19场景×13数据实现×11变体=2717次；其中18为原及新增近共线主矩阵、1为明确删墙观测负对照。全部是开发数据；12种子不能在B端再称盲确认。

关键结论：原weak静止/直行的23/25秩亏不包含偏差方向，b有观测支持；含噪peer偏差仍可能受非线性位置误差和先验影响。near满秩也不等于强信息；只保留peer的负对照才存在不同b的精确等价状态。主矩阵没有solver失败、存在44个配对变体行的偏差超阈值；负对照7次solver失败保留。不能将所有失败归于偏差不可辨识，也不能预设转弯或增广必定有效。

B端采用 `docs/research/midterm_simulation_s1b/S2_INTERFACE.md`；优先核对CONFIG、INFORMATION、PAIRED_SUMMARY和BIAS_DECOMPOSITION。README给完整复现命令；REPORT给论证和边界。Git外产物 `/home/ubuntu22/uwb-midterm-s1b-artifacts-20261116/run001` 及隔离回放run002-isolated不覆盖历史结果，逐文件SHA在EXTERNAL_INDEX和ISOLATION_REPLAY中。SHA256SUMS覆盖交付代码和证据，本HANDOFF单独由Git提交绑定。

检查状态：76项有限差分最大误差9.2443e-10；76个信息矩阵完整零空间及投影检查通过；2717行独立代价/误差/失败读回通过；247份观测噪声精确重建；清空继承ROS搜索路径后四份核心输出逐字节一致；174份基准登记/配置文本种子检查无冲突；`check_delivery.py`及固定基准范围`git diff --check`通过。Git变更仅在指定两个新目录，均为相对固定基准新增。

剩余问题：没有现场噪声/先验标定；12种子只做开发描述；没有8维gyro固定窗、边缘化或相关噪声验证；没有与生产无增广后端比较；没有保护级或实车性能声明。B端若继续，应先冻结新模型合同和独立确认种子，不直接把本批局部信息阈值用于在线安全拒判。

发布范围：推送独立分支并创建草稿PR，不自动合并。远端状态以实际GitHub响应及最终交付消息为准。
