# 中文交接：双车普通peer门控与传播开发核查

工作树`/home/ubuntu22/uwb-peer-gate-probe-20261028`，分支`analysis/20261028-peer-gate-probe`。新检出从当时远端main `7b67c66f2470d23f6c876f45b6543f72fab66391`创建；算法读取固定`74fa210e7cf6aa322eaebce19530510edb605d22`，不能随新main替换。预登记db1e26b，执行包装冻结完整HEAD `d78a5df8d51fbb98e160ab67d547e73a0bffc803`。实际冻结19原生文件与PR62执行`1595c982bc4d6206cbe3ad6ddaad774b50898766`全部SHA相同。

全部完成：45/45 DONE，24精确SHA复用、21新比较回放；先seed101 nominal/peer_bias六条，再其余39。41项测试通过，初次无.git快照的3个CLI元数据错误日志保留，换到同19文件SHA的独立Git检出通过，非算法修复。没有按结果改q、sigma、幅度、窗口、种子或场景。读器v1/v2和迁移后独立公式回算全部通过，数值表一致，没有为图/报告/归档重跑估计器。

选题结论：普通门控显著压制本批直接peer+1.2m偏差，是必须保留的成熟强基线；不能拿本轮再加鲁棒损失算贡献，因为G1本来已有pseudo-Huber。对Car1四墙共同+.30m，辅助距离误差可达+.4209m但q最大仅约1.95–2.03，均未触发已知拒绝，健康Car2故障/恢复期仍出现约5–9cm的同期正常RMSE增量。未观察到健康peer的已知高分误拒；启动2次unknown保守拒绝另计，正常总拒绝2/63。不能扩大故障“逼出”误拒。late部分位置误差改善、间距/Car1收益与Car2代价并存，反例全保留。参照可信性值得受限后续研究，但本轮没有新方法或完整性保证。

G2辅助从初始化起never-peer，不消费主图状态/prior/权重；同state/cutoff q>3仅拒绝新因子，unknown拒绝、missing独立。旧因子、全部6×6 joint prior交叉/affine/constant均保留，无IMU、墙链新策略或历史回滚。活动窗口与prior来源、实际factor ID、辅助完整snapshot可追溯。61accepted/63每条，两次warmup有限输出保留。全部成本/排队都是本机wall/virtual混合语义，非实车实时延迟。

交付入口REPORT.md；全部seed表TABLES.md；8张全seed同期/历史图FIGURES.md；方法METHODS.md；真实命令COMMANDS.md；冻结RUN_PLAN.json及最终RUN_INDEX.json；源码/输入/配置/产物SHA和测试、逐时刻压缩表在review。固定执行10个文件及原19文件SHA在索引内；评价/绘图/归档源SHA另见review/execution_provenance.json。

大证据根`/home/ubuntu22/uwb-peer-gate-probe-20261028-artifacts`。新归档29,660,829字节、387文件+manifest，SHA `a1c75087eb2a54ff0512e2065cca770d45f5b7d26dabf0e27d3d474c0f52a26f`，NAS实取迁移回算通过；原复用归档SHA `0e0156d75374cbe8e2180ef0eb36a7f282b5c59c842b6392d1ae4ae1956c8f8b`保留并一起可取得。精确路径/取得命令/回读receipt见ARTIFACTS.json。原输入、旧结果、原工作树/分支、公共几何/清单及实车设置未改；只新增用户指定两个目录。机器原有ROS/rosbag未触碰、未重复启动。

任务开始2026-10-27 16:34:27 UTC，6小时硬截止22:34:27 UTC；约一小时内完成矩阵、评价与归档回读，后续只做交付。无待补比较单元。后续不要再次run已完成矩阵；读取归档到新目录运行独立evaluate即可。若继续可信性研究需另版、预登记未暴露数据与保护目标，不以这3个暴露seed调门限或回滚时刻。真实同步、安装、现场输入、长期误报率与净prior因果贡献均未验证，不能把这些写成本轮保证。

结果提交`acc3c255ad5379340bf20a3cf59ceb5bebd5ee9d`已推送并创建[草稿PR #68](https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/68)。本收据/SHA清单为随后的纯元数据提交，最终HEAD以分支/PR为准；不自动合并。
