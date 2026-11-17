# 环境与范围

2026-11-17 UTC，实际初始路径 `/home/ubuntu22`。
旧checkout `/home/ubuntu22/uwb-moon1-localization-interface` 初始git status为空，HEAD `27b0ecf4d76124d54912d26d33432e1718dca494`。
独立worktree `/home/ubuntu22/uwb-moon1-numerics-timevarying-bias`，分支 `research/moon1-numerics-timevarying-bias`，从同一固定SHA创建，初始status为空。
origin fetch/push均 `https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git`。
未吸收移动main，未合并PR117或其他分支；没有修改旧工作区或历史目录。
未发现祖先 `/AGENTS.md`、`/home/AGENTS.md`、`/home/ubuntu22/AGENTS.md` 或新checkout内的AGENTS.md。
完整读取PR117文档和工具，并读取实际调用的六时刻prototype、identifiability及PR117模型。

独立Git外结果根：`/home/ubuntu22/uwb-moon1-numerics-timevarying-bias-artifacts`。
独立venv位于其 `venv` 子目录，Python3.10.12 / NumPy2.2.6 / SciPy1.15.3 / Matplotlib3.10.9。
使用PR117的固定requirements建立独立环境，不改系统或其他窗口venv。
OPENBLAS/OMP/MKL线程限制1，PYTHONDONTWRITEBYTECODE=1。运行中环境版本和完整命令另存FREEZE。
初查磁盘300GiB分区约12GiB可用；运行期间再次观察约37GiB可用，属于外部空间变化，本任务未清理其他目录。
CPU运行；无Isaac、GUI、GPU驱动安装、碰撞或月壤动力学。

输入选择：固定PR117已提交reference归档；同窗20条记录逐值一致，归档字节哈希与固定Git提交一致。
未重新打开/生成NPZ，继承的NPZ哈希仅历史来源回执，不能当成本轮再次核实NPZ→轨迹链。
所有新输入由新seed生成；无完整数据集下载。局部无噪声/假求解器测试与探索结果分别保存。

交付前只读核实：PR117已由外部合并，merge SHA为 `1328e2d85f773b43c7ac8610d67fc4cfd9d4ea9f`，当时远端main也指向该SHA。
本分支仍从指定PR117原交付SHA建立，未吸收该移动main；PR目标可直接使用main，本任务没有进行任何合并。
