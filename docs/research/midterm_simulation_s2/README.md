# P-S2 B端单常值偏差原型

先读REPORT和HANDOFF。范围是PR97的6时刻双车XY诊断，不是生产后端。四对照B0独立、B1协同、B2单偏差协同、B3已知注入量准确补偿。正式验证未启动，VALIDATION_PROTOCOL_DRAFT未冻结。

输入由CONFIG及PR97 design确定，SOURCE_LOCK列六个指定来源文件SHA，PROVENANCE绑定执行commit和脚本SHA。源码在tools/midterm_simulation_s2。运行前PLAN和配置提交24c7841；该版本运行192条件/768方法，只用了三个独立开发seed，未来正式seed未分配。统计单位是seed，不是时间点/两车/条件数量。D=MSE(method)−MSE(B0)，负为改善；RMSE使用XY欧氏误差，不是单轴平均。

## 运行环境与实际命令
工作区/home/ubuntu22/uwb-midterm-s2-bias-prototype，Python3.10.12、numpy2.2.6、scipy1.15.3、matplotlib3.10.9。复用已有venv，不需安装软件。实际命令按顺序如下（已有输出时拒绝覆盖）：

```bash
UWB_PY=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python
UWB_OUT=/home/ubuntu22/uwb-midterm-s2-bias-prototype-artifacts
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export TEMP="$UWB_OUT/tmp" TMP="$UWB_OUT/tmp" TMPDIR="$UWB_OUT/tmp" MPLCONFIGDIR="$UWB_OUT/tmp"
# 首先无噪声数学检查，随后开发矩阵
"$UWB_PY" tools/midterm_simulation_s2/checks.py --output docs/research/midterm_simulation_s2/CHECKS.json
"$UWB_PY" tools/midterm_simulation_s2/run_development.py --output "$UWB_OUT/development-v1" > "$UWB_OUT/development-v1.log" 2>&1
"$UWB_PY" tools/midterm_simulation_s2/analyze.py --source "$UWB_OUT/development-v1" --output docs/research/midterm_simulation_s2
"$UWB_PY" tools/midterm_simulation_s2/paired_summary.py
"$UWB_PY" tools/midterm_simulation_s2/verify_saved.py
```

本次已运行完成，复核首选最后的verify_saved（只读、无需重新定位），其输出保存在READBACK_CHECKS.json。SHA256SUMS还可核对交付字节。需要复跑开发时使用新的Git外目录；先让checks输出到该新目录，通过后run_development写新目录下run。analyze的--output需新目录，先复制原CONFIG进去，不能指向本次已存在结果目录。paired_summary是本次固定交付入口，仅生成到本任务docs且拒绝已有文件；重跑它应在另一个独立checkout或增加输出参数并登记源码版本。禁止删除旧结果凑出可写目录。

## 产物索引
- CONFIG/PLAN/SEED_REGISTRY/ENVIRONMENT：配置、预登记、暴露史、环境。
- SOURCE_LOCK/PROVENANCE/SHA256SUMS：来源、执行代码和产物身份。
- PER_RUN.csv：1536逐车行，全部6时刻、包括未收敛最后估计；768方法运行，不是1536独立实验。
- SUMMARY.csv：按条件/方法/车的开发均值/范围，另列成功条件结果和失败率。
- PAIRED_STATUS/PAIRED_SUMMARY：逐seed双方收敛状态和D；双方成功子集不替代全部分母。
- ZERO_BIAS_COST：零偏差B2相对B1误差和局部协方差迹代价。
- UNITS.jsonl.gz：无损全审计记录，含输入/噪声/truth SHA、最终状态/偏差/残差、完整SVD与协方差、失败详情。无原始数据大副本。
- CHECKS/INDEPENDENT_CHECKS/READBACK_CHECKS、development.log：数学、公平性、独立指标/补偿复核及运行日志。
- DEVELOPMENT_RMSE/FAILURES/ZERO_BIAS_COVARIANCE.png：图标题明确开发样本与未收敛。图中误差条为3seed范围，不是置信区间。

## 结果解释
B2预知链路，B3额外预知幅值；无故障识别。全局位移比未知航向轮速更强。403/768次未达到预登记一阶最优性标准，全部保留；解处有限协方差只描述局部信息，不能推翻参考退化，不是保护级。有偏prior属于预定模型失配压力条件，不是实测标定。当前只有开发支持，正式矩阵必须等待A固定提交及S2_INTERFACE对齐，并解决数值协议问题后另行冻结。
