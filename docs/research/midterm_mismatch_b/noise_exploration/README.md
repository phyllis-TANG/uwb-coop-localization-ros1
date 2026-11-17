# 独立噪声失配探索

在原故障批次及无优化器读回完成后单独冻结。72 条件、50 seed、14400 方法运行；不修改原批次。详见 PROTOCOL.md。

使用专用 venv 与 requirements.txt，BLAS 三种线程变量均为 1。执行入口 tools/midterm_mismatch_b/noise_run.py --mode formal --freeze 完整冻结SHA --out Git外新目录；中断只增加 --resume。只读核验入口 noise_readback.py，分析入口 noise_analysis.py，图表入口 noise_plots.py，具体参数见 --help。

开发 72 输入、576 阶段约 4.2 秒，阶段文件约 4.86 MB；正式规模约 243 MB 阶段压缩文件，另留输入/审计/归档空间，预留至少配置要求的空闲磁盘，2 worker。实际包括同步写盘与读回，预计数分钟至十余分钟。

协方差检查使用已暴露开发 seed 的 20000 个独立噪声块，并非正式定位样本；基准 iid004 与先前保存的开发终点差为 0。正式种子尚未生成观测。
