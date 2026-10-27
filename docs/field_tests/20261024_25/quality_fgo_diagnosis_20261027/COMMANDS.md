# 真实命令、顺序和复现边界

工作目录`/home/ubuntu22/uwb-quality-fgo-diagnosis-20261027`；新大证据根`/home/ubuntu22/uwb-quality-fgo-diagnosis-20261027-artifacts`。下列是本轮实际命令。完整结构化argv及执行源码SHA见review/commands.json，原96组的真实argv/input/config/source SHA见review/provenance.json及外部verification.json。Git外原执行run.json记录原环境版本。

## 隔离与检查

```bash
pwd
rg --files -g AGENTS.md /home/ubuntu22/双车协同
# 同时检查 /AGENTS.md、/home/AGENTS.md、/home/ubuntu22/AGENTS.md、工作空间AGENTS.md
# 均不存在；新检出递归亦无AGENTS.md。
git -C /home/ubuntu22/双车协同/uwb-coop-localization-ros1 status --short --branch
git -C /home/ubuntu22/双车协同/uwb-coop-localization-ros1 rev-parse HEAD
git -C /home/ubuntu22/双车协同/uwb-coop-localization-ros1 worktree list --porcelain
ps -eo pid,ppid,lstart,etime,args --sort=pid
# 后续使用不展示沙箱完整命令的 ps -eo pid,ppid,etime,comm。
git -C /home/ubuntu22/双车协同/uwb-coop-localization-ros1 cat-file -t 868349b543a03a6a713d1675e1d4ada7d905410c
git -C /home/ubuntu22/双车协同/uwb-coop-localization-ros1 cat-file -t 12a1d94379b58c5a759b1698425fb90d48587609
git -C /home/ubuntu22/双车协同/uwb-coop-localization-ros1 worktree add -b analysis/20261027-quality-fgo-diagnosis /home/ubuntu22/uwb-quality-fgo-diagnosis-20261027 868349b543a03a6a713d1675e1d4ada7d905410c
```

七份指定文档先通过`git show c5563df609f52df64727cf2618381abfda3cd3bb:<path>`完整阅读；共同基准包含同一交付。未切换任何已有检出。初始ps只能看到PID namespace内进程，不能证明宿主没有其他运行。云技能要求的environment_status不可用，网络policy文件不存在；没有据此假定网络就绪，也没有改网络设置。

## 只读证据与最小归因

下面用短变量准确表达实际路径；原真实argv在commands.json。

```bash
R=/home/ubuntu22/uwb-quality-fgo-diagnosis-20261027
A=/home/ubuntu22/uwb-quality-fgo-diagnosis-20261027-artifacts
O=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts
P=/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python
cd "$R"
python3 tools/single_car_quality_diagnosis/verify_evidence.py --original "$O" --output "$A/verification.json" > "$A/verification.log"
```

数值阶段每条命令均加`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`；画图另加`MPLCONFIGDIR=$A/mpl-cache`。

```bash
# v4在干预登记前完成，v6额外核对Q1/Q2/Q3完整prior链和影子历史；事件数值完全一致。
$P tools/single_car_quality_diagnosis/analyze_logs.py --experiment "$O/validation-v1" --output "$A/log-analysis-v4" > "$A/log-analysis-v4.log" 2>&1
# 先提交预登记，提交88a0e73，然后才执行D1/D2：
git -c user.name=Codex -c user.email=codex@openai.com commit -m 'Register offline quality FGO diagnosis and minimal attribution interventions'
$P tools/single_car_quality_diagnosis/intervene.py --experiment "$O/validation-v1" --analysis "$A/log-analysis-v4" --output "$A/interventions-v1" > "$A/interventions-v1.log" 2>&1
$P tools/single_car_quality_diagnosis/mechanics.py --experiment "$O/validation-v1" --output "$A/mechanics-v1" > "$A/mechanics-v1.log" 2>&1
$P tools/single_car_quality_diagnosis/analyze_logs.py --experiment "$O/validation-v1" --output "$A/log-analysis-v6" > "$A/log-analysis-v6.log" 2>&1
$P tools/single_car_quality_diagnosis/validate.py --experiment "$O/validation-v1" --analysis "$A/log-analysis-v6" --interventions "$A/interventions-v1" --output "$A/tests-v1.json" > "$A/tests-v1.log" 2>&1
$P tools/single_car_quality_diagnosis/make_delivery.py --original "$O" --analysis "$A/log-analysis-v6" --interventions "$A/interventions-v1" --mechanics "$A/mechanics-v1" --output "$A/delivery-final" > "$A/make_delivery-final.log" 2>&1
python3 tools/single_car_quality_diagnosis/verify_evidence.py --original "$O" --output "$A/verification_after.json" > "$A/verification_after.log"
```

`verification.json == verification_after.json`；v4与v6的8事件JSON逐项完全相同。D1/D2各按登记只执行一次，没有为做图重解估计器。脚本参数`--output`的目标目录需全新；复核时先替换为自己的Git外新根，不要原样覆盖这些目录。必要独立检查详见review/tests-v1.json。没有新增96组矩阵，也没有重新执行旧正式估计器CLI。

读器开发失败：v1遇F0 bias=null；v3遇原生Q1消元无quality_weights；v5遇旧原生Q0无逐次prior字段。这三次只读分析失败均保留原log，没有原输入或估计器产物变更；v2/v4/v6完整通过。初次git commit缺作者配置，后用单条命令显式Codex身份成功，未设置共享全局/仓库身份。画图初版和最终版各生成一次，最终版只清除无执行作用的死分支，没有重算估计器。

## 新证据归档与分支交付

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/single_car_quality_diagnosis/package_evidence.py --artifacts "$A" --nas /home/ubuntu22/nas/data/uwb_coop_artifacts/quality_fgo_diagnosis_20261027_12a1d943
# 打包程序先逐成员核验，再复制、从NAS重新读完整文件核验SHA。
git diff --check
```

归档receipt在ARTIFACTS.json，逐文件SHA在归档manifest。最终提交/推送/草稿PR收据在HANDOFF和review/delivery_receipt.json；不自动合并，不改ROS/串口/实车。

## 合并前bias缺失语义修订：仅重新导出

实际新目录`N=/home/ubuntu22/uwb-quality-fgo-diagnosis-20261027-artifacts/bias-null-revision`。以下数值命令使用前述单线程/PYTHONDONTWRITEBYTECODE设置，测试和画图也使用原MPLCONFIGDIR；结构化argv与源码SHA见review/bias-null-commands.json。复核时将N换成自己的全新Git外目录。

```bash
$P tools/single_car_quality_diagnosis/test_bias_semantics.py > "$N/tests.log" 2>&1
$P tools/single_car_quality_diagnosis/analyze_logs.py --experiment "$O/validation-v1" --output "$N/analysis" > "$N/analysis.log" 2>&1
$P tools/single_car_quality_diagnosis/reexport_solutions.py --experiment "$O/validation-v1" --saved "$A/interventions-v1" --output "$N/saved-solutions" > "$N/saved-solutions.log" 2>&1
$P tools/single_car_quality_diagnosis/make_delivery.py --original "$O" --analysis "$N/analysis" --interventions "$N/saved-solutions" --mechanics "$A/mechanics-v1" --verification "$A/verification.json" --output "$N/delivery" > "$N/delivery.log" 2>&1
$P tools/single_car_quality_diagnosis/validate.py --experiment "$O/validation-v1" --analysis "$N/analysis" --interventions "$N/saved-solutions" --output "$N/validation.json" > "$N/validation.log" 2>&1
```

仅从原保存解重导出，未调用intervene.py或任何求解器。原两份归档保留并重新核验SHA。新增补充归档使用独立目录：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/single_car_quality_diagnosis/archive_export_revision.py --revision "$N" --nas /home/ubuntu22/nas/data/uwb_coop_artifacts/quality_fgo_diagnosis_20261027_bias_null_export > "$N/archive.log" 2>&1
```
