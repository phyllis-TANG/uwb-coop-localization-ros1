# 合并前修订：缺失bias与有效零bias

修订前分支HEAD：`f2b6cb6b223d39f630100e3bcdbdf4b992602097`。这是诊断导出口径修正，冻结v1源码、原始测量、正式结果和已保存诊断解均不改变。

旧诊断`error()`以`(bias or 0)−truth`处理缺失值，主图导出还以0作为不存在字段的默认值。Q0/Q2没有bias状态，导出0会混淆“未估计”和“估计为0”，相关图也会产生伪零线。现仅用`is None`判缺失：bias与bias_error保持JSON null/CSV空值；真实0.0仍计算`0.0−truth`。RMSE只使用非null值，全缺失时保持null，不把0过滤掉。

同步范围：

| 导出 | 总行数 | 无bias状态行数 |
|---|---:|---:|
| main_history.csv | 2124 | 1062 |
| shadow_history.csv | 4248 | 2124 |
| timeline.csv | 8496 | 4248 |
| D2_snapshots.csv/JSON | 28 | 4 |

影子/因子时序和D2快照还显式增加bias列，使估计值和误差的缺失语义一致。上述行在不同表中相关、重复，不是独立试验。D1全部354行来自Q3，保留有效bias；跨时序/D1的264行有效零bias仍可正常读取与计算。

两张Q2图`uwb_step_419_Q2_node_2_03.png`、`uwb_step_419_Q2_node_3_04.png`取消bias伪零线，标明无bias状态。其余8张图与修订前字节SHA完全一致；Q1/Q3既有bias字段数值、8事件结论以及全部90项原指标比对保持一致。

新增两个针对性测试：

- `test_missing_bias`覆盖不存在字段、显式None、三维快照；验证误差与RMSE为None、JSON为null、CSV为空、绘图值为NaN而非0。
- `test_valid_zero_bias`覆盖四维快照中有效0.0；真值为.017时误差必须为−.017，真值为0时误差为0；验证CSV读取与RMSE仍保留有效零。

两个测试通过，另对全部时序/快照检查缺失语义，并重新执行已有只读FSM/倍率/指标检查。详见review/bias-null-tests.log、bias-null-validation.json、bias-null-comparison.json。

本次仅运行`analyze_logs.py`读取已有完整日志、`reexport_solutions.py`读取原`full_intervention_results.json.gz`保存的354条D1和28条D2解，再生成图表；未调用`intervene.py`、run_matrix或任何优化器。正式96组、6次主图重建、28次快照求解，本次新增运行次数均为0。intervene.py只同步修正未来输出函数，未执行它。

原正式证据归档SHA `7a5ff137f2f7fb250ebda466e163f94d137d59f660b48eb4f9150847bbdc3ab8`，原诊断归档SHA `d71635a4883cf0ad1ac2227dcd1f855da1164e9eeea2ae1528aa317418eb1def`，均保留。修订导出另存Git外`bias-null-revision/`及独立补充归档，不覆盖原47文件归档；新归档路径和SHA见ARTIFACTS.json的`bias_null_export_revision`。新源码/输入/命令及改动前后文件SHA见review/bias-null-provenance.json和bias-null-commands.json，最终交付清单见review/DELIVERY_FILES_SHA256.json。

修订前review/provenance.json中的`diagnosis_sources_sha256`仍记录原实际归因计算源码；新导出源码另记，不能拿新源码SHA冒称重新求解的来源。原receipt中的6/28是历史已完成次数，本次reexport_receipt另记0次新增求解。PR #63保持草稿、未合并。
