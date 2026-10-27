# 本轮真实命令与复核

实际Linux检出`/home/ubuntu22/uwb-peer-gate-probe-20261028`；任务输出根`/home/ubuntu22/uwb-peer-gate-probe-20261028-artifacts`。以下为实际执行，不是要求重跑已完成矩阵。完整argv/输入/配置/源码/输出SHA在RUN_PLAN、RUN_INDEX、review/execution_provenance.json及Git外run.json中。

## 现场/隔离

检查了祖先与相关检出的AGENTS.md（无适用文件）、pwd/git status/完整HEAD/worktrees、ps PID/PPID/etime/comm、free -h、df -h；已有ROS/rosbag进程不触碰。远端main实查7b67c66f2470d23f6c876f45b6543f72fab66391，旧原检出仍115b17deb2f848e596d1638a0b45cf360deae947。

```bash
git -C /home/ubuntu22/双车协同/uwb-coop-localization-ros1 ls-remote --heads origin refs/heads/main
git -C /home/ubuntu22/双车协同/uwb-coop-localization-ros1 fetch origin main
git -C /home/ubuntu22/双车协同/uwb-coop-localization-ros1 worktree add -b analysis/20261028-peer-gate-probe /home/ubuntu22/uwb-peer-gate-probe-20261028 7b67c66f2470d23f6c876f45b6543f72fab66391
```

固定19基础文件从`git show 74fa210e7cf6aa322eaebce19530510edb605d22:<path>`逐文件取到frozen-source，SHA与原运行19文件全匹配；RUN_MATRIX文档与原matrix.json字节SHA也完全相同。只读，没有切换其他worktree或改公共文件。

## 测试、冻结和执行

```bash
cd /home/ubuntu22/uwb-peer-gate-probe-20261028
A=/home/ubuntu22/uwb-peer-gate-probe-20261028-artifacts
O=/home/ubuntu22/uwb-two-car-fixed-lag-fgo-v1-artifacts
P=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python
export PEER_GATE_FROZEN_ROOT="$A/frozen-source" PEER_GATE_OLD_ROOT="$O"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
$P tools/cooperative_peer_gate_probe_20261028/prepare.py --old "$O" --output "$A/inputs" > "$A/prepare-v1.log" 2>&1
$P tools/cooperative_peer_gate_probe_20261028/test_probe.py > "$A/tests-v1/probe.log" 2>&1
$P -m unittest discover -s "$A/frozen-source/tools/two_car_fixed_lag_fgo_v1" -p 'test_*.py' -v > "$A/tests-v1/frozen.log" 2>&1
```

最后一条3个CLI元数据错误：快照无.git，git_state失败；24个其余测试通过。保留该失败与source快照。原27测试转到本检出（核对19文件SHA完全相同），未改算法：

```bash
$P -m unittest discover -s tools/two_car_fixed_lag_fgo_v1 -p 'test_*.py' -v > "$A/tests-v2/frozen.log" 2>&1
$P tools/cooperative_peer_gate_probe_20261028/test_index.py > "$A/tests-v2/index.log" 2>&1
$P tools/cooperative_peer_gate_probe_20261028/test_export.py > "$A/tests-v2/export.log" 2>&1
$P tools/cooperative_peer_gate_probe_20261028/runner.py --artifacts "$A" --phase freeze > "$A/freeze-v1.log" 2>&1
```

预登记提交db1e26b；测试通过后，45条完整输入/源码/参数/运行计划与执行文件提交d78a5df8d51fbb98e160ab67d547e73a0bffc803。算法文件此后逐cell SHA不变，执行前Git干净。先运行六条检查点，再续剩余39，不自动重试：

```bash
$P tools/cooperative_peer_gate_probe_20261028/runner.py --artifacts "$A" --phase checkpoint > "$A/checkpoint-v1.log" 2>&1
# 对两场景126发布独立核对G2 helper pose/prior=G0，及q与真实拒绝：checkpoint_101_checks.json PASS
$P tools/cooperative_peer_gate_probe_20261028/runner.py --artifacts "$A" --phase complete > "$A/complete-v1.log" 2>&1
```

原24单元为SHA精确复用/装饰导出，不重新跑；仅15个G2和新增场景6个G0/G1为21次新比较回放。source+output manifests区分这些来源。测试合同中的辅助干预不是扩展矩阵、盲验证或选参。

## 分离公式回读与图表

```bash
$P tools/cooperative_peer_gate_probe_20261028/evaluate.py --matrix "$A/matrix-v1" --frozen-source "$A/frozen-source" --output "$A/evaluation-v1" > "$A/evaluation-v1.log" 2>&1
export TMPDIR="$A/tmp" MPLCONFIGDIR="$A/mpl-cache"
$P tools/cooperative_peer_gate_probe_20261028/make_report.py --evaluation "$A/evaluation-v1" --matrix "$A/matrix-v1" --output "$A/compact-v1" > "$A/report-v1.log" 2>&1
```

独立读器v2使迁移后的归档不依赖原绝对路径，并增加侧车/唯一输入适配器核验。v1源码和结果保留；六份数值表逐字节相同；无估计器重跑：

```bash
$P tools/cooperative_peer_gate_probe_20261028/evaluate.py --matrix "$A/matrix-v1" --frozen-source "$A/frozen-source" --output "$A/evaluation-v2" > "$A/evaluation-v2.log" 2>&1
```

## 归档与从NAS取回

```bash
$P tools/cooperative_peer_gate_probe_20261028/archive_evidence.py --artifacts "$A" --old "$O" --nas /home/ubuntu22/nas/data/uwb_coop_artifacts/cooperative_peer_gate_probe_20261028_74fa210e > "$A/archive-v1.log" 2>&1
```

新归档每文件、NAS完整文件读回SHA核验，原复用归档也复制到独立新NAS目录并校验，不改原文件。归档/manifest/提取后只读回算收据另见ARTIFACTS.json。复核从归档取出的`delivery-source/evaluate.py`运行，输入路径按解包目录重新解析、原run/index/manifest SHA不改。所有新读器输出必须是新Git外目录；原45矩阵输出不得覆盖，也不要再执行checkpoint/complete。
