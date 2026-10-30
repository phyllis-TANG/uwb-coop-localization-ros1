# 实际命令
工作树 `/home/ubuntu22/uwb-integrity-validation-20261030`；执行环境：
```
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export TEMP=$PWD/docs/research/integrity_validation_20261030/tmp
export TMP=$TEMP TMPDIR=$TEMP
UWB_PY=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python
```
顺序：
```
git fetch origin main
git merge-base --is-ancestor fed9157008530663280aa2413ef708e345e678e3 origin/main
# exit 1；没有把预览merge当main。
git worktree add -b analysis/20261030-integrity-validation-v1 /home/ubuntu22/uwb-integrity-validation-20261030 fed9157008530663280aa2413ef708e345e678e3
# PLAN/UNITS先提交e4e86e5；wrapper提交8ca3933
$UWB_PY -m unittest discover -s tools/cooperative_integrity_baselines_20261029 -p 'test_*.py' -v
$UWB_PY tools/integrity_validation_20261030/experiment.py calibration
$UWB_PY tools/integrity_validation_20261030/test_adapter.py
# CALIBRATION和FROZEN_VALIDATION提交f8e1f72后：
$UWB_PY tools/integrity_validation_20261030/experiment.py checkpoint
$UWB_PY tools/integrity_validation_20261030/experiment.py validation
$UWB_PY tools/integrity_validation_20261030/experiment.py boundary
$UWB_PY tools/integrity_validation_20261030/field.py
```
独立读回分别对4101_nominal、5101_nominal、5101_peer_bias、5101_car1_common_wall_bias执行：
```
$UWB_PY tools/cooperative_integrity_baselines_20261029/independent.py --run docs/research/integrity_validation_20261030/units/<unit> --output docs/research/integrity_validation_20261030/INDEPENDENT_<unit>.json
```
共同墙输出名实际为INDEPENDENT_5101_wall.json。命令stdout/stderr见各log。初次git commit缺作者配置失败，未运行单元；后续用`git -c user.name=Codex -c user.email=codex@openai.com commit`，不改全局配置。

最终只读重算：
```
python3 tools/integrity_validation_20261030/check_scores.py
python3 tools/integrity_validation_20261030/summarize.py
MPLCONFIGDIR=$TEMP $UWB_PY tools/integrity_validation_20261030/report.py
```
报告随后补入由SUMMARY直接读取的五问定量回答；没有重跑估计器。
