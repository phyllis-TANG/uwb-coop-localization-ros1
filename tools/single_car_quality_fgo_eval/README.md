# B质量因子图核验工具

没有定位器，不导入A质量判定函数。已有PR59全矩阵不重跑；先校验归档并复制到新的Git外目录。当前实包只做冻结停止窗诊断和原输入准备；中立检查器/负例属于合成日志fixture，A原生接入仍pending。[阶段交接](../../docs/field_tests/20261024_25/single_car_quality_fgo_eval_v1/HANDOFF.md)

每个输出目录必须不存在；无覆盖、无resume。隔离venv使用`tools/requirements-single-car-replay.txt`和jsonschema4.25.1；实际环境见归档pip freeze。以下从本B checkout执行：

```bash
"$NEW_VENV/bin/python" tools/single_car_quality_fgo_eval/prepare_reuse.py --output "$NEW_RESULTS/reused"
"$NEW_VENV/bin/python" tools/single_car_quality_fgo_eval/endpoints.py \
  --reused "$NEW_RESULTS/reused" --output "$NEW_RESULTS/stop"
"$NEW_VENV/bin/python" tools/single_car_quality_fgo_eval/verify_endpoints.py \
  --reused "$NEW_RESULTS/reused" --diagnostics "$NEW_RESULTS/stop" --output "$NEW_RESULTS/stop_readback"
"$NEW_VENV/bin/python" tools/single_car_quality_fgo_eval/input_facts.py \
  --reused "$NEW_RESULTS/reused" --output "$NEW_RESULTS/facts"
"$NEW_VENV/bin/python" tools/single_car_quality_fgo_eval/prepare_ready.py \
  --reused "$NEW_RESULTS/reused" --facts "$NEW_RESULTS/facts" --output "$NEW_RESULTS/ready_for_A"
"$NEW_VENV/bin/python" tools/single_car_quality_fgo_eval/readiness.py \
  --reused "$NEW_RESULTS/reused" --facts "$NEW_RESULTS/facts" --output "$NEW_RESULTS/readiness"
"$NEW_VENV/bin/python" tools/single_car_quality_fgo_eval/check_contract.py --output "$NEW_RESULTS/fixture"
"$NEW_VENV/bin/python" tools/single_car_quality_fgo_eval/negative_contract.py --output "$NEW_RESULTS/negative"
"$NEW_VENV/bin/python" tools/single_car_quality_fgo_eval/prefix_fixture_controls.py --output "$NEW_RESULTS/prefix_fixture"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "$NEW_VENV/bin/python" \
  -m unittest discover -s tools/single_car_quality_fgo_eval -p 'test_*.py' -v
```

`ready_for_A/{004023,005135}`给实际A v1事件、原始富字段和标量目录，F0/F3基线配置不含终点/停止窗。质量配置与A执行提交仍null；不要把`fixtures.py`的数值当标定或实包参数。原人工终点仅在单独`evaluation_only.json`/stop诊断侧，不能送给A规则。`CONTRACT.json`是B提出的审核字段/语义，`A_BINDING_TEMPLATE.json`是待实际交接的空绑定，不是A已冻结接口。

真实A到来后，从共同base建立另一独立执行checkout，取确切A SHA并合入当前B分支，记录实际组合提交/所有源SHA/配置/协议再运行新方法；本B分支不合入A内核。根据A原生schema建立只做读取/数学重算的适配器；不导入在线质量函数，不能用SHA相等代替语义核验。若命名评分/FSM不同，独立实现实际冻结规则，不通过重命名强行当本样例通过。当前CLI只接受明确synthetic scope，实际field输入会被拒绝直到原生适配经过测试。

原PR59因果控制仅复用旧证据；新影子干预必须真实执行至边缘化后，比较全部数值入口和prior，元数据规范化范围需披露。不得从主图吸收后的残差给链路贴健康标签。32→33是同套测试扩展，不累计成65；合成坏样例16组和33项unit也分别报告，不当实包运行次数。
