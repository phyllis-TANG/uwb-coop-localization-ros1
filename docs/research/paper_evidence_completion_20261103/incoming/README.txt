UWB 逐车收益论文：详细提纲与证据盘点 v1

先阅读 UWB_Paper_Outline_and_Evidence_Audit_v1.docx。它是写作与执行提纲（13页），不是投稿论文。
正文按6页规划；8页为内部扩展预算。实际会务规则仍需按目标年份核实。

仓库审查固定版本：phyllis-TANG/uwb-coop-localization-ros1
commit: d39b284e2a1dd84a322a359187a4e4b926a56e62
覆盖main递归路径4368项、取回208份文本；不含未合并分支或本地盘全量文件。

关键文件
- experiment_comparison_matrix.csv：实测与仿真实验族、baseline、参考与适用范围。
- bag_register_116.csv/json：116条文件身份（114实测+2仿真），并非116次有效独立实验。
- static_combined_results_source.json：用户此前提供的10包、160行保存统计。
- static_per_bag_calibration_effects_80.csv：逐包/阶段/方法/车辆的校正效应C。
- static_scope_comparison_20.csv/json：五种覆盖口径、两车、两方法的摆位交互T。
- dynamic_A1_B1_all_16_stops.csv：已归档A1/B1全部16条停车结果。
- simulation_PR92_readback.csv：PR92逐seed交互结果的复算汇总。
- figure_plan.csv：论文图表状态与待完成事项。
- figure_asset_inventory.csv：243条图像/PDF路径，含格式变体和重复，不代表243张论文图。
- repository_path_inventory.csv、retrieved_source_index.csv：检索范围与固定版本来源。
- source_snapshot.json、repo_tree.json：复算所需的仓库文本与路径快照。
- equations.tex：提纲中的公式源文本。
- audit_verification.json：本轮身份、数值和覆盖核验结果。

指标：D=MSE(cooperative)-MSE(independent)，负值代表协同收益；
C=D(historical calibration)-D(raw)；T=mean(C,G2)-mean(C,G1)。
参考误差包络建立在每轴2cm的条件假设上，不是统计置信区间。
人体操作窗、恢复窗与正常窗来自相同采集，不能算作新增独立重复。
恢复窗同时保留既定规则排除run9的4包口径与全部5包口径。

离线复算（解压后在包根目录运行）
python build_audit.py
只需Python标准库，生成 deliverables/ 下的复算结果；不运行定位器、不解码bag。
已有结果表均附在包根目录，方便直接审阅。
如需重建Word（可选，依赖python-docx；建议安装Noto Sans SC字体）：
python build_document.py
公式图片已附；重新绘制可用 python make_equations.py（依赖matplotlib）。
文档字体不打包，缺少字体时由本机替换，分页可能变化。

验证边界
本轮核对了保存统计的算术关系与文本blob身份；未独立重查原始轨迹时间戳、mask，
未解码原始bag，未重跑估计器，未验收连续动态真值。
A2/B2最终冻结结果、逐方法轨迹/共同时间戳和硬件摆位最终记录仍待本地导入。
已有结果中的异常和实测/仿真符号差异保留，不作追号调参。
ZIP不包含原始bag或全部图像二进制；包含可追溯路径清单和本轮新计算证据。
