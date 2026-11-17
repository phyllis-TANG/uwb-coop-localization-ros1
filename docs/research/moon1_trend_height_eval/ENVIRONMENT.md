# 环境与隔离记录

初始目录/home/ubuntu22。原工作树/home/ubuntu22/uwb-moon1-numerics-timevarying-bias，分支research/moon1-numerics-timevarying-bias，HEAD 8765e12377966cb527e1bbb51e47f7699eaada6b，初始Git干净，未修改。

本轮独立worktree：/home/ubuntu22/uwb-moon1-trend-height-sensitivity；分支research/moon1-trend-height-sensitivity；初始HEAD 0c3dbbb59a5c65087e073ad1c49eaed397f2958b，初始Git干净；origin=https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git。没有吸收移动main。

检查/AGENTS.md、/home/AGENTS.md、/home/ubuntu22/AGENTS.md及新工作树，未发现适用AGENTS.md。初始可见进程为codex-linux-san及检查用bash/ps；该检查只涵盖沙箱可见范围，不宣称宿主机无其他任务。初始磁盘约300GiB、可用31GiB。

Git外结果与独立venv：/home/ubuntu22/uwb-moon1-trend-height-sensitivity-artifacts。Python3.10.12、NumPy2.2.6、SciPy1.15.3、Matplotlib3.10.9。未修改系统Python或其他venv，未安装GPU驱动、启动GUI/Isaac或下载完整数据。BLAS/OMP/MKL线程数均设1，CPU执行。

开发提交96fddaabd3dfcb3f3e668e4a736bcd7b07761a2f；探索冻结648ad7411fece15efc6ce75a31f8eb60e431e406。最终交付HEAD见PR（避免提交内容自引用其自身SHA）。历史来源以FREEZE及HISTORY_SHA256为准；不是补造原资产生成回执。

交付前可用空间约27GiB；仅本任务Git外目录与允许新增目录写入。
