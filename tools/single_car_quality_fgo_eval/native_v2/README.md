# B原生质量接口实包核验

采用固定A12a1d943源码；`policy_math.py`按实际A公式独立实现，旧中立fixture不改不套用。`numerics.py`只复用B PR59独立标量公式，读器不导入A策略、图/Jacobian或qaudit。`probe_runner.py`是明确的**执行器**，调用原A Pipeline并只读观察缓存，不是独立读器或第二定位器。

本轮已完成8条主性能回放，勿重复运行矩阵。实际组合提交5e91a26851bf0ac9813388d505e32f2c86c3f808，独立执行分支execution/20261027-quality-field-12a1；交付报告与所有SHA见docs/field_tests/20261024_25/single_car_quality_fgo_eval_v2/。本B分支基于868349b，未把A改动私自修补到内核。

以下在本B Git checkout、隔离venv执行；全部输出必须是不存在的Git外目录，无resume/覆盖。实际逐字argv另保存在SOURCE_VERSIONS和完整run.json中。

```bash
python -m tools.single_car_quality_fgo_eval.native_v2.prepare --output "$NEW/prepared"
# 仅需要真正重现实验时运行：两包×四组最多8条，原结果保留；4进程同anchor paced。
python -m tools.single_car_quality_fgo_eval.native_v2.batch --prepared "$PREPARED" \
  --execution-checkout "$EXEC" --output "$NEW/performance"
# 已有可取得归档只需校验并运行下列读取器，不重跑估计器：
python -m tools.single_car_quality_fgo_eval.native_v2.reader --prepared "$PREPARED" \
  --performance "$PERF" --output "$NEW/readback"
python -m tools.single_car_quality_fgo_eval.native_v2.bindings --prepared "$PREPARED" \
  --performance "$PERF" --output "$NEW/bindings"
python -m tools.single_car_quality_fgo_eval.native_v2.rank_check --performance "$PERF" --output "$NEW/rank"
python -m tools.single_car_quality_fgo_eval.native_v2.verify_controls --prepared "$PREPARED" \
  --performance "$PERF" --controls "$CONTROLS" --output "$NEW/control_readback"
python -m tools.single_car_quality_fgo_eval.native_v2.inventory --prepared "$PREPARED" \
  --performance "$PERF" --controls "$CONTROLS" --all-wall "$ALL_WALL" --output "$NEW/inventory"
```

生成实控用`controls`（4真实prefix+4N10干预），其余3墙用`extend_controls`复用4prefix仅加12干预；总20控制，均跨17次实际边缘化，属于加速验证而非主性能延迟测量。已有20份完整结果直接回读，不再次执行。控制自有输入文件保留原case/原bag/原消息身份作来源引用，实际改后serialized文件另记真实SHA；原件不变。移机核验按传入根目录和文件basename解析控制输入/config，不要求原producer绝对路径。

`negative`复制私有日志后修改、重新封装输出SHA；只有语义拒绝才通过。`summarize`独立统计全量/共同、触发/unknown/恢复、停车窗和actual availability；不读真值轨迹，不选参数。完整发布周期用processing_start到data_flushed；旧不完整耗时列保留，不称纯CPU或现场ROS延迟。所有工具仅处理两开发包，原P1不迁移其他场次。
