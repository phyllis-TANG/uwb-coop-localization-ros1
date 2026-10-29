# 已执行命令与复现入口

以下为实际执行的核心命令，工作目录均为`/home/ubuntu22/uwb-cooperative-a-evidence-20261029`。原归档/解包、新计算均在Git外任务目录，不覆盖旧产物。命令只读保存状态，不启动估计器。

```bash
# 检查点：命令输出中的main为0ef38e8b84dc88cb7b0e26fea595ac05c5162676
 git status --short
 git log -2 --oneline
 git ls-remote origin refs/heads/main
 df -h /home/ubuntu22/uwb-cooperative-a-evidence-20261029-artifacts
```

原现场进程、基线和目录检查记录见PREREGISTRATION；收尾检查见checks/FINAL_SITE.txt。依赖复用现有venv（Python3.10.12、NumPy2.2.6、Matplotlib3.10.9）；未安装大型环境。

```bash
# 14:37已执行，使用默认--output evidence-v1与默认NAS路径
/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python tools/cooperative_followup_20261029/a_evidence/prepare.py > /home/ubuntu22/uwb-cooperative-a-evidence-20261029-artifacts/prepare-v1.log 2>&1

# 下列前缀用于后续Python命令；真实各次调用均设置这三个环境变量
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
TASK_A_PY=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python
TASK_A_ROOT=/home/ubuntu22/uwb-cooperative-a-evidence-20261029-artifacts
TASK_A_TOOLS=tools/cooperative_followup_20261029/a_evidence

# 首次漏传--evidence，退出2，仅usage，未产生分析目录
"$TASK_A_PY" "$TASK_A_TOOLS/extract.py" --output "$TASK_A_ROOT/analysis-v1" > "$TASK_A_ROOT/extract-v1.log" 2>&1
# 第二次参数齐全，遇离线变量重名TypeError；保留analysis-v1和日志
"$TASK_A_PY" "$TASK_A_TOOLS/extract.py" --evidence "$TASK_A_ROOT/evidence-v1" --output "$TASK_A_ROOT/analysis-v1" > "$TASK_A_ROOT/extract-v1-attempt2.log" 2>&1
# cb1b67b修复后完整通过，不覆盖v1
"$TASK_A_PY" "$TASK_A_TOOLS/extract.py" --evidence "$TASK_A_ROOT/evidence-v1" --output "$TASK_A_ROOT/analysis-v2" > "$TASK_A_ROOT/extract-v2.log" 2>&1

"$TASK_A_PY" "$TASK_A_TOOLS/summarize.py" --analysis "$TASK_A_ROOT/analysis-v2" --evidence "$TASK_A_ROOT/evidence-v1" --output "$TASK_A_ROOT/summary-v1" > "$TASK_A_ROOT/summarize-v1.log" 2>&1
# 整数ns导出修正，保留v1；计算数值/原始证据不变
"$TASK_A_PY" "$TASK_A_TOOLS/summarize.py" --analysis "$TASK_A_ROOT/analysis-v2" --evidence "$TASK_A_ROOT/evidence-v1" --output "$TASK_A_ROOT/summary-v2" > "$TASK_A_ROOT/summarize-v2.log" 2>&1
"$TASK_A_PY" "$TASK_A_TOOLS/audit_semantics.py" --evidence "$TASK_A_ROOT/evidence-v1" --output "$TASK_A_ROOT/semantics-v1" > "$TASK_A_ROOT/semantics-v1.log" 2>&1
"$TASK_A_PY" -m unittest discover -s "$TASK_A_TOOLS" -p 'test_*.py' -v > "$TASK_A_ROOT/tests-v2/checks.log" 2>&1
```

上述核心调用与日志逐一对应；变量写法仅将当时重复的绝对路径收拢。首次4项测试在tests-v1，最终8项在tests-v2。代码提交时使用单条命令的`git -c user.name=Codex -c user.email=codex@openai.com commit`，未改变共享Git身份配置。首次普通commit因未配置作者退出128，无提交/分析数据变化，随后采用上述已有Codex署名。

复现请选择**全新**输出父目录，设置`TASK_A_ARTIFACTS`指向它；先`prepare.py --output 新目录/evidence-v1 --archive 已验证原归档路径`，再按同样子目录名运行extract/summarize/audit。prepare会把原归档复制/解包到新目录；原始证据完全一致时才通过。extract和summary的输出目录必须不存在，CSV以独占模式写入。若仅复查交付表，无需解包大证据；验证DELIVERY_SHA256即可。后处理包与原归档的取得方式见ARTIFACTS.json。

```bash
PYTHONDONTWRITEBYTECODE=1 "$TASK_A_PY" "$TASK_A_TOOLS/package_readback.py" --output "$TASK_A_ROOT/package-v1" > "$TASK_A_ROOT/package-v1.log" 2>&1
```

派生产物包随后用Python `mkdir(exist_ok=False)`创建新的NAS专属目录、`open('xb')`复制，并重新计算SHA；未触碰原归档。具体目标及校验数值在ARTIFACTS/PACKAGE_CHECK。最终Git提交/推送仅当前分支，无force；草稿PR状态以最终回复和远端记录为准。
