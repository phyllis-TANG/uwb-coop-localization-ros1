# 确切命令与续接

实际工作树`/workspace/work/uwb-cooperative-integrity-baselines-20261029`；Git外根`/workspace/work/uwb-cooperative-integrity-baselines-20261029-run`。现已完整完成；不要为了读表再次运行估计器。已有目录拒绝覆盖；重建必须用新目录并重冻清单，不隐式resume。

以下准备实际执行过，使用当前授权代理和registry，无视频/bag/PR68归档下载：

```bash
cd /workspace/uwb-coop-localization-ros1
git fetch origin main
git worktree add -b analysis/20261029-cooperative-integrity-baselines /workspace/work/uwb-cooperative-integrity-baselines-20261029 81fb509ba2d2a1b2e1f1151d53a7e73807820bd4
cd /workspace/work/uwb-cooperative-integrity-baselines-20261029
python3 -m venv --system-site-packages /workspace/work/uwb-cooperative-integrity-baselines-20261029-run/venv
```

使用独立venv固定`numpy==2.2.6 scipy==1.15.3`，matplotlib3.10.8只画图；原环境不卸载或修改。安装使用`python -m pip install --no-cache-dir numpy==2.2.6 scipy==1.15.3`，记录在logs/dependencies.log。Python3.12.14、zlib1.3.2；venv依赖不计作研究结果，研究产物总量单独检查<100MB。无数据盘，用户在当前聊天明确授权工作区内RAM复现和轻量写出，未扩大为大型数据授权。

后续命令都使用以下实际执行环境（将变量展开就是原argv）：

```bash
export UWB_REPO=/workspace/work/uwb-cooperative-integrity-baselines-20261029
export UWB_TASK_ROOT=/workspace/work/uwb-cooperative-integrity-baselines-20261029-run
export UWB_PY="$UWB_TASK_ROOT/venv/bin/python"
export TEMP="$UWB_TASK_ROOT/tmp"
export TMP="$UWB_TASK_ROOT/tmp"
export TMPDIR="$UWB_TASK_ROOT/tmp"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
cd "$UWB_REPO"
"$UWB_PY" -m unittest discover -s tools/cooperative_integrity_baselines_20261029 -p 'test_*.py' -v
```

正式三案例在**在线提交d431ba1…的干净工作树**执行；冻结前方案6fc4bef。当前最终工具多了独立读表/负例/打包修订，不能把它冒充原在线执行版本。完整在线提交及逐文件SHA在results/RUN_INDEX、Git外FROZEN_INDEX。

```bash
"$UWB_PY" tools/cooperative_integrity_baselines_20261029/run.py --phase pair --output "$UWB_TASK_ROOT/reproduction-v2"
"$UWB_PY" tools/cooperative_integrity_baselines_20261029/run.py --phase peer --output "$UWB_TASK_ROOT/reproduction-v2"
```

pair先完成nominal及共同墙偏差，保存CHECKPOINT_pair；peer验证相同冻结源码后只运行peer_bias。输入只在内存中，不写raw事件/truth缓存；每场景自动做同输入原生G1控制，nominal自动做receive<=46秒控制。新结果拒绝已有目录。run.py的--phase不允许重复启动已完成案例。

实际独立核验最终版：

```bash
"$UWB_PY" tools/cooperative_integrity_baselines_20261029/negative.py --run "$UWB_TASK_ROOT/reproduction-v2/nominal" --output "$UWB_TASK_ROOT/NEGATIVE.json"
"$UWB_PY" tools/cooperative_integrity_baselines_20261029/readback.py --runs "$UWB_TASK_ROOT/reproduction-v2" --output "$UWB_TASK_ROOT/readback-v4"
"$UWB_PY" tools/cooperative_integrity_baselines_20261029/report.py --runs "$UWB_TASK_ROOT/reproduction-v2" --evaluation-root "$UWB_TASK_ROOT/readback-v4" --output "$UWB_TASK_ROOT/report-v2"
"$UWB_PY" tools/cooperative_integrity_baselines_20261029/package.py --runs "$UWB_TASK_ROOT/reproduction-v2" --readback "$UWB_TASK_ROOT/readback-v4" --report "$UWB_TASK_ROOT/report-v2" --output docs/research/cooperative_integrity_baselines_20261029/results
```

以上目录已经存在；重读请把**输出目录**改为新的`readback-review-*`，输入仍用原reproduction-v2。不要重跑run.py。单独核验保存图的最小纯NumPy入口如下（输出名同样须新）：

```bash
"$UWB_PY" tools/cooperative_integrity_baselines_20261029/independent.py --run "$UWB_TASK_ROOT/reproduction-v2/car1_common_wall_bias" --output "$UWB_TASK_ROOT/review-common-new.json"
```

independent.py本身无在线内核/Jacobian/判定函数导入。readback.py作为协调脚本另调用冻结生成器重建RAM输入/truth以核验身份和评价，未调用估计器；共享解析/配置/primitive身份范围在FROZEN_SPEC披露。全套15测试与8负例不是3场景定位矩阵重跑。

失败/旧读表均保留在Git外：logs/input-precheck-01.log、inputs-precheck-failed.py、pair-v1.log（导入失败，尚无run目录）、readback-v3及其日志（CSV行序字节检查失败）；旧readback-v1/v2、report-v1和原episodes也保留。最终readback-v4仅纠正预先存在报警的onset/延迟和CSV行序验证，其余四类CSV数值及重复计数精确相同。不要把这些版本累计成独立试验。
