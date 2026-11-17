# DUAL-A-V1 真正双车联合区域：A端

单时刻、两未知二维天线位置、单条有界 peer 偏差的数学合同、固定输入与独立验收。全部为合成机制模型，非平台标定、保护级或任务安全保证。只新增本目录及 tools/midterm_dual_robot_contract_a/。

共同起点 3ad69c8137183c1986012e354857b73527978c48。运行标识 DUAL-A-V1。早期接口由 CONTRACT_READY.json 标记，其哈希文件冻结；Git完整提交SHA在PR中报告，不写入自身文件。后续分析仅追加文件；若修改冻结接口，须新版本及兼容性说明。

阅读顺序：MATH → MODEL_CONTRACT → INPUT_SCHEMA → THRESHOLD_CERTIFICATE → INPUTS → CHECKER_TESTS → HANDOFF。后续分析见 COOPERATIVE_INFORMATION_NOTE、DUAL_TIME_NEXT_SPEC、DECISION_MEMO。写作窗口使用 WRITING_NOTE。

标准库执行（Python≥3.10）：

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tools/midterm_dual_robot_contract_a -v
python tools/midterm_dual_robot_contract_a/check.py certificate docs/research/midterm_dual_robot_contract_a/inputs/deterministic.json normal_b0_zero /path/to/certificate.json
python tools/midterm_dual_robot_contract_a/check.py archive docs/research/midterm_dual_robot_contract_a/inputs /path/to/archive FULL_B_SHA
```

禁止搜索器读取 evaluation_only.json。A端没有定位搜索器，没有运行定位Monte Carlo。根盒/手工分割证书只是检查器测试夹具；其模拟成本不属于B性能结果。
