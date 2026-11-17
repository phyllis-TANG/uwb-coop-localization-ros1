# 本次独立环境

日期2026-11-17 UTC；初始工作目录 `/home/ubuntu22`。
独立checkout `/home/ubuntu22/uwb-moon1-localization-interface`，独立分支 `research/moon1-localization-interface`。
初始完整HEAD、当时main及共同起点均为 `d5bf9c1c7127e71bf6eb30f9a5b807952c810e53`。
origin fetch/push均为 `https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git`。
创建时工作区干净，新目录未被占用。旧height-audit checkout的修改未触碰。
未发现 `/AGENTS.md`、`/home/AGENTS.md`、`/home/ubuntu22/AGENTS.md` 或新checkout内AGENTS.md。
已完整阅读PR114 README/REPORT/PROTOCOL/HANDOFF及六时刻数学定义、prototype、movement、information、验收和读回代码。
方案仅只读固定提交 `b31789444b04792df58dd78d11a906804eed95a2`，没有合并分支。

独立venv：`/home/ubuntu22/uwb-moon1-localization-interface-artifacts/venv`。
Python3.10.12、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9；匹配requirements，实际数值与绘图运行通过。
系统无修改，其他venv未修改。线程限制OPENBLAS/OMP/MKL各1；PYTHONPATH置空、禁写bytecode。
初查磁盘约18GiB可用，批次后约17GiB（300GiB分区）；这是磁盘，不是RAM。
RAM约31GiB总量、25GiB available，无swap。本轮无需GPU，未安装驱动、Isaac或GUI。
进程检查仅看到sandbox内codex-linux-san/bash/ps，不能据此声称宿主机无其他任务。

原始输入只读取PR114新NPZ及已提交来源回执，批次完成后再次核验NPZ哈希不变。
精确环境版本、命令、代码完整SHA和依赖源文件哈希见FREEZE、ACCEPTANCE、COMMANDS、RUN。
