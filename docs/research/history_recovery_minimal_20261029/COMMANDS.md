# 实际执行与重放

所有命令在 /home/ubuntu22/uwb-history-recovery-minimal-20261029；Python为 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python。运行均指定OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1。

```bash
python -m unittest discover -s tools/history_recovery_minimal_20261029 -p 'test_*.py' -v
python tools/history_recovery_minimal_20261029/run.py freeze
git -c user.name=Codex -c user.email=codex@openai.com commit -m 'Preregister minimal peer history attribution and publication controls'
python tools/history_recovery_minimal_20261029/run.py run
python tools/history_recovery_minimal_20261029/verify.py
python tools/history_recovery_minimal_20261029/evaluate.py
```

上面python是简写，实际命令使用上述完整venv路径。freeze和run拒绝已存在目录/索引；evaluate的CSV也用独占创建，不覆盖既有结果。需要复现时用全新独立检出执行提交b82a03b614732a57c5934c0aac23b0f1912f7854，并设置HISTORY_OUTPUT为新目录、HISTORY_SOURCE为原归档evidence-v1。先执行合同再freeze/run。freeze锁定当时任务源集合，最后交付添加了只读verify/evaluate；原执行提交用于逐字重现，读器从交付版本读取。不要在当前结果目录重新运行估计器。

只读核验可在当前版本直接运行verify；evaluate需要另一个临时检出/空结果输出以免覆盖CSV。源码所有权仅tools/history_recovery_minimal_20261029及docs/research/history_recovery_minimal_20261029。
