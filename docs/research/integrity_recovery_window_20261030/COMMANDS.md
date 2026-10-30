# 实际命令与环境
工作目录/home/ubuntu22/uwb-integrity-recovery-window-20261030。
```
git fetch origin main
git worktree add -b analysis/20261030-integrity-recovery-window-v1 /home/ubuntu22/uwb-integrity-recovery-window-20261030 7001d33da1f77875aa9cd2adbd7ffd155bc13610
```
只读git show origin/main:docs/research/research_convergence_20261030/{README,TARGET_CARD,REPRODUCTION}.txt；来源blob/SHA见SOURCE_RECEIPTS。现场df/ps/git状态已检查，进程只覆盖当前命名空间。未发现适用AGENTS。
```
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export TEMP=$PWD/docs/research/integrity_recovery_window_20261030/tmp
export TMP=$TEMP TMPDIR=$TEMP
UWB_PY=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python
# 计划与prefix包装器提交0b61cfa之后
$UWB_PY tools/integrity_recovery_window_20261030/extension.py > docs/research/integrity_recovery_window_20261030/prefix.log 2>&1
# prefix通过及运行包装器提交9e9ed66之后，仅两次估计器运行
$UWB_PY tools/integrity_recovery_window_20261030/run_extension.py > docs/research/integrity_recovery_window_20261030/run.log 2>&1
$UWB_PY tools/integrity_recovery_window_20261030/verify.py > docs/research/integrity_recovery_window_20261030/verify.log 2>&1
python3 tools/integrity_recovery_window_20261030/summarize.py
MPLCONFIGDIR=$TEMP $UWB_PY tools/integrity_recovery_window_20261030/deliver.py
```
随后只读join SOURCE_GROUPS与各单元trajectory/declarations生成TIMELINE，整理报告/HANDOFF及SHA索引；未重运行估计器。提交用命令局部Codex作者身份，不改全局git配置。运行输出拒绝覆盖；不要直接重执行已有目录。
