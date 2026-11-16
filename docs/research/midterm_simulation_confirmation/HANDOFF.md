# A端正式执行交接

被验收冻结版本为PR102 `6317e977572b4e8fb8282211485356562ddc62d2`。先行验收提交`8e9850fbbedd73116b93273a98b700b6d91eb077`已经在正式输入生成之前完成。用户后续明确授权通过即运行，取代B文档暂停表述。本轮完整HEAD和草稿PR链接见最终回执；不在提交内自引用自身SHA。

实际完成7200/7200方法、14400/14400阶段，缺失0，无重试、无参数变更；新seed741216001..741216050现全部暴露。7175接受，25未驻点，全部7200有限最终估计进入主统计。独立残差/J/梯度/误差、冻结读回、144组1332项统计摘要/区间及轻量证据复核都通过。

可以保留的结论：指定core+.3m、已知受影响链路下，B2相对B1逐车MSE的24个95%逐项配对区间均低于0；零注入存在增广代价；弱/near静止peer与有误差强prior继续影响估计。不能写成B2普遍优于B0（其core+.3m对应24区间仅9个低于0）、无偏差无损、所有样本收敛或实车验证。区间相关、无多重比较保证，独立n仍50。

原始目录 `/home/ubuntu22/uwb-s2-confirmation-artifacts/formal-frozen` 保留输入与完整阶段矩阵；轻量包、文件SHA、汇总和图在本目录。复核优先verify_portable，无需重新定位。完整只读命令见README。禁止以本批已暴露种子作为新的盲确认，或删除25个非接受记录后声称更好效果。

交付分支research/midterm-s2-confirmation，草稿PR以research/midterm-s2-validation-ready为base，仅新增midterm_validation_acceptance和midterm_simulation_confirmation两个文档目录（独立审查/作图脚本随证据保存在目录内）。不合并PR，不操作公共定位后端或实车。
