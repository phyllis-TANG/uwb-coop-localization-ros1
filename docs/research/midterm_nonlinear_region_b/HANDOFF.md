# 交接与验收

工作区 `/home/ubuntu22/uwb-midterm-nonlinear-region-b`；分支 `research/midterm-nonlinear-region-prototype-b`；固定起点 `f9c27436836b814afdea47945887015dcb55fca5`。独立环境与Git外结果根为 `/home/ubuntu22/uwb-midterm-nonlinear-region-b-artifacts`。未修改历史目录、月球目录或正文，未等待其他端，未合并任何PR。

初始冻结：`e5c1d6e1ee83b99859a5c099281efd95b90d1d26`。
修复冻结：`888912f64a7a3b8cd33a24fb7c5394255e1c1dce`。
最终交付SHA以PR完整HEAD为准，避免自引用哈希。

初始批次validation保存5例后因读回根域字符串格式错误停止；修订批次validation-r2复用5例（哈希完全不变），只搜索另外3例。原结果和attempt不覆盖，原日志/身份/hash在stopped_batch；便携results保存最终8例完整树及ORIGINAL_RUN。RESUME_PLAN与REVISION说明暴露范围和修复。不要重跑任一已完成案例。

预期验收：13项开发测试通过；只读check.py对8例返回PASS、search_calls=0、optimizer_calls=0；SHA256SUMS全部匹配。README提供完整命令。读回将核对源码/输入哈希、原复用结果哈希、完整分割树、全部内外叶证书及投影面积/半径，不调用搜索器或优化器。开发tests使用单独小例，会调用其合成搜索，不属于正式批次重跑。

正式唯一搜索8次、处理9837盒；1例空集、1例预定盒预算中止、0例数值失败、0例实际时间超限。阶段1门控通过；两个镜像案例双支保留，两个边界案例接触边界。假时钟超时和注入数值失败在开发中单列验证，不能说正式已发生这些事件。

全部非线性优化器调用0；局部比较只是同输入仿射直接代数解。不能把可计算的局部椭圆当成外包证书，不能把8个确定性案例写成95%覆盖率Monte Carlo。全部概率结论条件于固定域、已知模型/协方差和输入表示包含。下一步建议先研究约束传播，见DECISION_MEMO，本轮不自动启动短窗口或25维实验。
