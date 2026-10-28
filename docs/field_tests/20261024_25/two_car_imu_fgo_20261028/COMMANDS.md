# 执行命令与复取

实际cwd `/home/ubuntu22/uwb-two-car-imu-fgo-20261028`。使用已有外部环境，无安装/升级共享依赖。以下为已执行主要命令；所有主运行的真实sys.argv另由run.json捕获并汇总在RUN_COMMANDS.json。source/input/config/output SHA见各版本RUN_PLAN/RUN_INDEX/run.json及SOURCE_VERSIONS；不是凭命令推定成功。

```bash
# 以下变量仅缩写本轮实际绝对路径；不重启已完成矩阵。
TASK_ART=/home/ubuntu22/uwb-two-car-imu-fgo-20261028-artifacts
TASK_PY=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$TASK_ART/tmp" MPLCONFIGDIR="$TASK_ART/mpl-cache"
"$TASK_PY" -m unittest discover -s tools/two_car_imu_fgo -p 'test*contract.py' -v
"$TASK_PY" tools/two_car_imu_fgo/batch.py freeze --root "$TASK_ART/synthetic-v1" --test-log "$TASK_ART/tests-v3/contracts-serialized.log"
"$TASK_PY" tools/two_car_imu_fgo/batch.py run --root "$TASK_ART/synthetic-v1"
"$TASK_PY" tools/two_car_imu_fgo/field_inputs.py --old-output "$TASK_ART/old-inputs-v2"
"$TASK_PY" tools/two_car_imu_fgo/field_batch.py freeze --root "$TASK_ART/old-matrix-v1" --inputs "$TASK_ART/old-inputs-v2" --test-log "$TASK_ART/tests-field-v1/contracts.log"
"$TASK_PY" tools/two_car_imu_fgo/field_batch.py run --root "$TASK_ART/old-matrix-v1"
"$TASK_PY" tools/two_car_imu_fgo/repair.py freeze --artifacts "$TASK_ART" --root "$TASK_ART/repair-v2" --test-log "$TASK_ART/tests-bug01-v3/contracts.log"
"$TASK_PY" tools/two_car_imu_fgo/repair.py run --root "$TASK_ART/repair-v2"
"$TASK_PY" tools/two_car_imu_fgo/repair.py select --artifacts "$TASK_ART" --root "$TASK_ART/repair-v2" --original synthetic-v1 --output "$TASK_ART/synthetic-selected-v2"
"$TASK_PY" tools/two_car_imu_fgo/repair.py select --artifacts "$TASK_ART" --root "$TASK_ART/repair-v2" --original old-matrix-v1 --output "$TASK_ART/old-selected-v2"
"$TASK_PY" tools/two_car_imu_fgo/evaluate.py --matrix "$TASK_ART/synthetic-selected-v2" --output "$TASK_ART/synthetic-readback-v2"
"$TASK_PY" tools/two_car_imu_fgo/evaluate_field.py --matrix "$TASK_ART/old-selected-v2" --output "$TASK_ART/old-readback-v2"
"$TASK_PY" tools/two_car_imu_fgo/verify_prefix.py --matrix "$TASK_ART/old-selected-v2" --inputs "$TASK_ART/old-inputs-v2" --output "$TASK_ART/old-prefix-v2"
"$TASK_PY" tools/two_car_imu_fgo/new_inputs.py --archive "$TASK_ART/retrieved-inputs/UWB_field_20261024_25_20261025_071212.tar.gz" --output "$TASK_ART/new-inputs-v1" --stage-b-artifacts "$TASK_ART"
"$TASK_PY" tools/two_car_imu_fgo/make_report.py --evaluation "$TASK_ART/synthetic-readback-v2" --output "$TASK_ART/synthetic-report-v2"
"$TASK_PY" tools/two_car_imu_fgo/verify_pairs.py --artifacts "$TASK_ART" --output "$TASK_ART/input-pairs.json"
"$TASK_PY" tools/two_car_imu_fgo/package_summary.py --artifacts "$TASK_ART"
```

旧包原消息读回使用`field_readback.py --bag <原bag绝对路径> --packets <old-inputs-v2/015334或033248> --output <case_readback.json>`；独立验证全部消息，不读取单车004023/005135作为双车输入。新包新输入工具内部调用同一独立字段读器。测试先后v1/v2/v3、严格适配失败old-inputs-v1、BUG01修复合同失败tests-bug01-v2均保留；失败不覆盖、不宣称运行完成。

复取时先核ARTIFACTS.json归档SHA，解压到新的Git外目录，再核包内EVIDENCE_MANIFEST.json所有成员SHA。可直接以包内final-source/tools/two_car_imu_fgo/evaluate.py / evaluate_field.py读selected-v2索引，输出到新的目录；不需要重新优化。selected索引相对artifact_root可搬迁，run.json中的原绝对输入路径仅历史记录，不用于读回定位。

原始bag不重复塞进证据归档：18日两包在冻结仓库datasets/field_raw/20261018/bags；T08/T10按FIELD_INPUTS及manifest的Release archive/精确成员SHA取得。不要下载视频或提取其他包。完整原消息字段包已在证据归档中；若需再次双解码核验才读取这四个原bag。
