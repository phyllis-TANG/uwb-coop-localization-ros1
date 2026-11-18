# 验收与执行回执

## 命令与输入

以下从仓库根运行，PYTHON为ENVIRONMENT中的独立venv解释器，均设PYTHONDONTWRITEBYTECODE=1及OPENBLAS/OMP/MKL线程1。输出均在Git外独立目录。

- 数学检查：`$PYTHON tools/moon1_trend_height_eval/tchecks.py --out <artifacts>/math005`；正式数学回执为MATH_ACCEPTANCE.json，最终开发检查math005通过，中心差分最大误差1.5871e-8，真实优化器0。
- 开发：`$PYTHON tools/moon1_trend_height_eval/tbatch.py --mode development --out <artifacts>/development001`（具体执行身份以development/FREEZE与RUN为准）。暴露seed911170101，32方法/64调用，32接受。
- 探索：`$PYTHON tools/moon1_trend_height_eval/tbatch.py --mode explore --out <artifacts>/explore001 --acceptance docs/research/moon1_trend_height_eval/ACCEPTANCE.json --freeze 648ad7411fece15efc6ce75a31f8eb60e431e406`。1920方法/3840调用；不再执行该批次。
- 独立便携复核：README完整命令，实际输出<artifacts>/portable_readback001。冻结后新增verify_delivery.py仅用于读回，不属于冻结估计器；先禁止真实least_squares，再执行完整数学/持久化假求解器测试、输入/阶段/统计/哈希复核和300项匹配恒等式。通过，真实调用0。

## 实际通过项

独立距离/运动/prior/注入与高度实现重建；跨条件/高度共享标准噪声；M0对peer注入不变但不要求高度不变；M3 b1=0与M2一致；normal/constant/ramp无噪声零残差；step不强制匹配。range/data/total满秩；reference/故障字段拒绝；原物理梯度门槛保留。

调用前attempt、硬上限、孤立attempt拒绝、重复调用拒绝、目录独占锁均经假求解器检查。实际无孤立attempt、无不可用结果，所有有限P0执行P1一次。

全3840阶段读回残差/J/梯度最大差分别4.40e-14/7.11e-15/3.34e-12；中心差分最大1.998e-8；独立逆信息矩阵协方差块最大差1.61e-17。1920终态标签与全部统计分母复算一致；原目录与便携归档产生CSV/JSON逐字节一致。源码及5316历史哈希不变。

## 开发失败与审计边界

早期math001因配置生成尚未结束出现FileNotFoundError，未调用优化器；历史清单初次遇到Git带引号的Unicode文件名，改为NUL分隔读取并明确symlink哈希。math002/003/004为零优化器检查；最终冻结使用math005。没有因探索结果修改源码/门槛或择优重跑。

冻结前seed审计覆盖固定仓库可读文本和592个受跟踪gzip；补充审计在冻结后只读检查18个NPZ及一个Overleaf ZIP，无冲突，明确记于SUPPLEMENTARY_SEED_AUDIT.json。没有声称掌握未记录的外部运行。补充审计未变更seed或运行计划。

开发32方法/64真实调用；探索1920方法/3840真实调用；所有读回/数学检查0真实调用；合计3904≤4032。formal_runs=0。
