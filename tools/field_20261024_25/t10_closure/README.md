# T10 B端输入闭环工具

只消费成功重试184755，拒绝其他包/错误SHA；不修改PR46/48数学内核或默认策略。中文结果与B→A机器接口见[HANDOFF](../../../docs/field_tests/20261024_25/t10_closure_20261027/HANDOFF.md)和[t10_handoff.json](../../../docs/field_tests/20261024_25/t10_closure_20261027/t10_handoff.json)。本轮新估计器运行0次，实际做了严格编译、输入选择/迁移、定向视频复查及旧源odom独立回读。

## 直接消费迁移包

克隆包含本工具的PR分支，按[ARTIFACTS](../../../docs/field_tests/20261024_25/t10_closure_20261027/ARTIFACTS.json)核验包SHA。`$EXTRACTED`必须是自己的空目录；`$NEW_OUTPUT`必须不存在。算法只需原隔离NumPy环境，不安装视频依赖到算法环境。

```bash
mkdir "$EXTRACTED"
tar --keep-old-files -xzf docs/field_tests/20261024_25/t10_closure_20261027/inputs/T10_portable_inputs_v2.tar.gz -C "$EXTRACTED"
"$ALGORITHM_PYTHON" tools/field_20261024_25/t10_closure/run_ready.py \
  --template docs/field_tests/20261024_25/t10_closure_20261027/T10_strict_input_template.json \
  --packet "$EXTRACTED/T10_inputs" --output "$NEW_OUTPUT"
```

当前退出2且`new_estimator_runs=0`是预期。封装在B目录显式核验归档派生包的Git登记run SHA、全部成员哈希、T10来源、逐车记录身份与严格来源；它没有改写原标准化run.json或替换原验证器。源PR45 root仍可用`--normalized`输入。媒体清单与历史manifest仅允许明确列出的非算法字段差异，正式bag/所选原片身份或几何改变立即拒绝。

`run_ready.py`调用PR48 `compile_template`，选择原本支持的`odom_only_frame=room`以使三种room基线共享实际初值/时间条件。任一前提未满足时不重跑已有source-frame Odom-only。齐备后调用原PR46 `read_events/write_replay`，沿用有向peer、200ms链路间隔、60ms已到达twist支持、3D斜距及旋转杆臂等政策。没有新的可靠性策略、参考拟合或精度评价接口。

这是严格入口。候选几何中心、marker偏移、合成/工程物理输入不许冒充来源支持参数；`point_definition`须明确物理odom点到天线、体轴x前/y左。主机/采样时间界须有来源且为正整数；未知保持null。既有工程R/Q不因此冒充标定。本轮未生成探索性数值配置。

## 在已有输出上重建/审查

以下均要求不存在的新输出目录；本轮实际argv和退出码在文档的`results/COMMANDS.json`。

```bash
"$ALGORITHM_PYTHON" tools/field_20261024_25/t10_closure/intake.py \
  --normalized "$VERIFIED_PR45_ROOT" --data-root "$REGISTERED_DATA_ROOT" \
  --baseline-run "$EXISTING_PR46_T10_RUN" --output "$NEW_INTAKE"
"$ALGORITHM_PYTHON" tools/field_20261024_25/parameter_clock_prep/interface.py \
  --template "$NEW_INTAKE/T10_strict_input_template.json" --output "$NEW_COMPILE"
"$ALGORITHM_PYTHON" tools/field_20261024_25/t10_closure/readback.py \
  --packet "$NEW_INTAKE" --normalized "$VERIFIED_PR45_ROOT" \
  --review "$REVIEW_OUTPUT" --strict-run "$STRICT_OUTPUT" \
  --reference-decision docs/field_tests/20261024_25/t10_closure_20261027/reference_decision.json \
  --output "$NEW_VERIFICATION"
```

`readback.py`当前验收范围明确是T10输入选择、精确PTS/记录、null保留与**历史source-frame/阻塞结果**；不是通用的新room轨迹精度验算器。上例`intake.py`需要原PR46已登记运行；若不在同环境，直接消费提供的迁移包，不把旧绝对路径当共享缓存。

只有原片审查需要新的隔离视频venv：

```bash
python -m venv "$NEW_VIDEO_VENV"
"$NEW_VIDEO_VENV/bin/python" -m pip install -r tools/field_video_20261026/requirements-video.txt
python tools/field_20261024_25/prepare.py --data-root "$NEW_DATA_ROOT" --assets T10_video --extract
"$NEW_VIDEO_VENV/bin/python" tools/field_20261024_25/t10_closure/inspect_video.py \
  --mov "$NEW_DATA_ROOT/extracted/T10_video/IMG_7347.MOV" --output "$NEW_REVIEW"
```

协议在`protocol.json`预登记；PyAV逐帧读取，仅对选定PTS转图并复用PR49角点，不重新检测/标定。只保存一张缩略接触表、CSV/JSON，不导出4K逐帧目录。单次300s限额，已有证据/视频复查总限90分钟；本轮该阶段约22分钟内收敛。没有重跑全片完整性检查。

测试：`python -m unittest discover -s tools/field_20261024_25/t10_closure -p 'test_*.py' -v`。PR45八包完整大表、旧完整回放、原片、venv都留Git外；提交的1.79MB迁移包仅为T10标准化**输入选择**及紧凑来源，不含原始bag/MOV或完整历史回放结果。新输入/源码/配置指纹使用新目录，没有`--resume`开关。
