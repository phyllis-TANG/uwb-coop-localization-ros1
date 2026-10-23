# PR40 路径迁移与交接兼容修复 1.2.0

本版本仅修复恢复/审核入口、交接生成和报告行数说明。原实验 v1、正式归档 v1.1、31 次运行、输入、结果、阈值、原执行源码锁及旧哈希清单保持原字节；没有重跑估计器、重新生成传感器输入或选择阈值。

## 审核入口

- [报告勘误](REPORT_CORRECTIONS.md)：metrics.csv 共 **87 个数据行（不含表头）**，其中开发 15 行、诊断 72 行。
- [新生成的 v1.1 交接](HANDOFF.md)：从实际实验路径生成，恢复命令显式含 `--experiment` 和 `--resume-only`。
- [检查点](CHECKPOINT.json)、[19 项测试日志](compatibility_tests.log)、[原证据保护核对](evidence_preservation.json)。
- [恢复核对](resume_verification.json)与[归档审核](artifact_verification.json)：保留原绝对输入路径，并另外记录实际解析路径和哈希；路径仅代表核对时的工作区。
- 兼容源码、旧源码快照及哈希见仓库 `tools/integrity_compat/v1_2_0/manifest.json`。这是独立兼容版本，不改名为新的估计器试验。

## 路径与严格校验规则

合成输入仅使用所选实验的 `runs/<id>/sensors.jsonl`；历史输入仅使用当前仓库中 `protocol.json` 对应案例的 bag。历史协议哈希必须与 run.json 中的原输入哈希一致；两类输入均对实际文件重新计算 SHA256。原 `input_path`、`command`、`imported_from` 绝对路径保留为来源记录，不作为读取后备路径。本地文件缺失、哈希不符、路径越界、未完成运行均直接失败。

恢复入口新增 `--resume-only`，只核对已有完整运行；缺少任何预期项即停止，不启动工作者、不选择阈值。`--handoff-output` 只允许新文件，已有文件拒绝覆盖。普通运行器生成的检查点/HANDOFF 随实际实验目录变化；对登记的冻结 v1.1，写入 `compatibility/v1_2_0/checkpoints/`，不覆盖原清单或根目录 HANDOFF。

## 源码与证据谱系

原实验提交 `f8097700fc36565fdeda76e2952c38833c9df3e6`；原审阅补充提交 `4682ac4c05b7f572cc191cf465d7c07d5831de2a`。原 source_lock.json SHA256：

`afad12945c4190426188cd33f2aef1344537ae924d2b148c60d2bf1e80b842a8`

原执行锁仍记录原运行器哈希，没有把旧运行宣称为由新源码执行。兼容验证只对清单中登记的这一份锁，允许运行器恰好替换成登记的新哈希；估计器、生成器、其他 CORE 文件、协议和配置必须仍符合原锁。审核器、报告生成器的两处兼容变更也另记原/新哈希及逐字节旧源码快照。所有新兼容源码及测试文件都由新清单校验。

旧 `ARTIFACT_SHA256SUMS.txt` 原封保留，直接检查当前工作树会在这 3 个有意修复的工具上报告差异；不能据此声称所有执行源码未变。本版本的 `preserve_original_artifact_hashes()` 明确检查：666 项中的 663 项仍匹配原文件；这 3 个工具同时匹配登记的新哈希与保存的原源码快照。其余任何旧文件差异均失败。先前 PR 审阅的 7 项哈希也完全保持。

新兼容清单 SHA256：`6a974d666d5f2bf3e7fe8d0a1538d4e5f5e867d4b733d084755c84f6a48a1b03`。

## 复核命令

先在当前环境安装 `tools/requirements-integrity-feasibility.txt` 对应依赖，再从仓库根目录执行。这个工作区原有离线依赖目录只是环境记录；代码不依赖旧工作区的输入绝对路径。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tools -p test_integrity_compatibility.py -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/run_single_car_integrity_experiment.py --experiment docs/field_tests/integrity_feasibility_v1_1_20261022 --resume-only
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/verify_single_car_integrity_artifacts.py --experiment docs/field_tests/integrity_feasibility_v1_1_20261022
```

若实验被移动到其他目录，替换 `--experiment` 实参即可；历史 bag 仍须位于当前仓库中协议指定的相对路径且原哈希一致。需要另存交接可加 `--handoff-output <尚不存在的新文件>`；不要覆盖旧 HANDOFF。新测试的换目录案例复制真实 31 条归档运行、当前源码及两包历史输入到带空格的新仓库目录，分别调用 CLI 恢复/审核，核对全部解析路径属于新目录、原绝对路径仅保留记录，以及复制的旧文件前后哈希一致。

## 验证结果与测试对应

19 项测试全部通过。实际换目录恢复与审核核对 31 条运行、2769 次发布、11076 条排除假设记录；实际工作区再次执行同样的只读核对。新增估计器运行数为 0，重新生成输入数为 0，阈值重新选择数为 0。

| 要求 | 对应测试（简写，完整名称见日志） |
|---|---|
| 换目录实际恢复及审核、原记录不变 | ArchivedRelocationTests.test_real_archive_relocated_resume_and_audit_without_estimator |
| 当前实验输入优先；缺失/损坏不回退 | test_relocated_sensors_preserve_absolute_provenance / test_missing_local_input_never_falls_back_to_valid_old_path / test_corrupt_local_input_never_falls_back |
| 当前仓库 bag、协议/输入哈希 | test_historical_bag_uses_current_repository / test_historical_hash_disagreement_and_corruption_rejected |
| v1.1 交接路径、空格与外部实验目录 | test_v1_1_handoff_uses_actual_experiment_and_quoted_paths |
| 不覆盖旧清单/根交接、显式实验参数 | test_checkpoint_does_not_rewrite_frozen_inventory_or_root_handoff / test_cli_requires_explicit_experiment |
| 恢复不生成、不启动、不调阈值、缺失失败 | test_resume_only_all_phases_no_generator_worker_or_threshold_selection / test_resume_missing_or_incomplete_never_starts_worker |
| 原锁不变、仅登记运行器可替换、其余篡改拒绝 | test_original_lock_preserved_exact_registered_runner_only / test_protocol_config_runner_snapshot_and_manifest_tampering_rejected |
| 原快照对应旧清单、输出及阈值保护 | test_original_ledger_accepts_only_explicit_source_snapshot_replacements / test_output_and_threshold_corruption_rejected |
| 87/15/72 行与实际 CSV 对照 | test_archived_metrics_are_87_rows_15_development_72_diagnostic |

本修复不改变既有科学结论、正常误报/实测报警占比口径、故障与误差越界区分、状态/可获得时间轴或 M2 独立先验实现。原 37 项监测/定位测试和 4 项指标测试保留原日志，本轮无需重跑。兼容支持限于清单登记的正式 v1.1 执行锁；旧 v1 的生成失败与输出继续保留作历史证据，不冒充可由当前源码重新执行的运行。不默认启用监测器，不合并 main。
