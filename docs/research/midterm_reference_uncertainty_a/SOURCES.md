# 固定来源与阅读边界

所有仓库来源固定为30f9379249a4e695acf75910c40862a770e6f4ce，未吸收移动main或本轮B/C未交付修改。SOURCE_HASHES.json记录该起点全部5442个tracked文件SHA；关键输入/代码在FREEZE_MANIFEST再次绑定。原PR123、PR124的SHA256SUMS均已核验。

- PR124：`docs/research/midterm_nonlinear_region_b/`的README、SOURCES、MATH、PROTOCOL、CONFIG、INPUTS、RESULTS、REPORT、DECISION_MEMO、HANDOFF、DEVELOPMENT和REVISION；实际`tools/midterm_nonlinear_region_b/interval.py`、`inputs.py`、`invert.py`。明确第四参考已知、无运动/先验、2/3维、完整四维噪声事件、保留队列、固定域及相关R尚未实现。
- PR123：`docs/research/midterm_nonlinear_decomposition_a/`的README、PROTOCOL、MATH、REPORT、DECISION_MEMO、HANDOFF及结果检查。提供局部非线性不可直接继承仿射Gaussian保证的证据，及退化支持集合的严谨语义；不重复读回1800端点。
- PR121：`docs/research/midterm_inset_validation_b/MATH.md`及`tools/midterm_prior_mechanism_b/math_model.py`。核实固定δc、74随机观测和4固定先验行、已知候选peer的常b；本轮没有修改或调用其定位器。
- 已交付文献结论：`docs/research/midterm_integrity_literature_c/THEORY_AUDIT.md`、`METHOD_OPTIONS.md`、`notes/LITERATURE_SETS.md`、`notes/MODEL_AUDIT.md`。本轮按仓库已审计文本使用噪声事件反演及包含原则，没有声称重新获得/逐式核查外部最终出版PDF。参考位置集合扩展、风险接口与具体反例是本轮推导，不归称原论文已验证当前平台。
- 平台依据只读：`ros_ws/src/uwb_coop_localization/config/anchors.yaml`（明确仿真示例）；`docs/field_tests/20260927/results/single_link_los_ground_truth_summary.json`（三段静态记录统计与bag身份）；`docs/field_tests/20261024_25/video_reference_20261027/calibration_review.json`、`MISSING_EVIDENCE.md`（内参、安装与时间/真值验收限制）。未重读bag、重采样或重新标定；不把这些有限来源外推为全平台已知误差界。

ASSUMPTION_REGISTER逐条区分“文件内容已知”“仿真假设”“平台待证”。本轮不给暂无来源的量填任意数值，也不按旧实验最大误差选择参考半径。
