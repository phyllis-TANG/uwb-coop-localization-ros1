# 单车九组权重敏感性诊断（2026-10-21）

本轮以已合并 PR #32 的 main `21b17f344b58b72c2bd00c9834f89e5d0a9b1bc5` 为基线，只进行离线测试。没有改变原始数据、旧结果、标定偏置、外参假设、在线节点或默认参数，也没有新增 IMU 因子。

先读 `REPORT.md` 和 `REFERENCE_AUDIT.md`；完整输入约束在冻结的 `protocol.json`。`results/` 保存全部九组、两个 bag 的普通 CSV / JSON 文件；没有只保留有利组合。`analyze_sensitivity.py` 是实际求解脚本，`test_sensitivity.py` 是独立算术复核，`build_report.py` 只负责整理报告，不参与求解。

## 复现

需要 Python 3、NumPy、SciPy。使用 PR31 归档的原求解器，不修改该求解器。原重建归档仅作为输入容器，其 SHA-256 为 `5536b5217127de0975b2a3839d844eea37630fb4aa2e7009a231b5c62397a13c`。本轮不重新上传原 bag 或压缩包。

从本仓库根目录执行（把输入归档路径替换成现有本地文件；输出目录必须不存在）：

```bash
python docs/field_tests/20261018/single_car_sensitivity_20261021/analyze_sensitivity.py \
  --review-zip /absolute/path/uwb_single_car_rebuilt_20261020_final_review.zip \
  --transfer-dir docs/field_tests/20261018/single_car_transfer_20261021 \
  --benefit-dir docs/field_tests/20261018/single_car_benefit_20261021 \
  --output /absolute/path/new_sensitivity_results
```

复核当前归档结果：

```bash
python docs/field_tests/20261018/single_car_sensitivity_20261021/test_sensitivity.py
```

报告生成器从本目录的结果生成 Markdown，并可附带生成一个含普通文件下载链接的自包含 HTML：

```bash
python docs/field_tests/20261018/single_car_sensitivity_20261021/build_report.py \
  --html-output /absolute/path/UWB_single_car_sensitivity_review_20261021.html
```

## 文件含义

| 文件 | 内容 |
|---|---|
| `endpoint_comparison.csv` | 全部 18 次求解的终点偏差、末端静止散布、相对冻结融合轨迹的改变量；比较参考 A/U/F 保持原值 |
| `stationary_diagnostics.csv` | 72 条静止窗口记录；散布、首末位移、路径长度都不等同定位精度 |
| `residual_summary.csv` | 以米/度统计的拟合残差；不同权重的目标函数不可直接比较 |
| `residual_by_link.csv` / `residual_by_phase.csv` | 全部链路/阶段的测距拟合残差 |
| `trajectories.csv` / `odom_step_residuals.csv` | 1,692 个天线/车体状态及 1,674 条里程计步进残差 |
| `optimizer_records.json` | 所有组合的参数、停止原因、状态、迭代次数及一阶最优性指标 |
| `checks.json` / `test_verification.json` | 输入哈希、旧结果复现和独立算术验证 |
| `evidence/main_source_verification.json` | GitHub 合并状态与两个旧归档目录的 48 个文件字节核查 |

上述结果文件实际位于 `results/`。原始数据、前两轮归档和旧工作区的未提交修改保持不变。此目录的存在不表示已上传新 PR；归档/发布状态以实际 GitHub 记录为准。
