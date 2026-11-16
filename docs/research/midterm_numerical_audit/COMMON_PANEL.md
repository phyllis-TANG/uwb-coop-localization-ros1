# B端复现共同输入

来源严格固定：A `ed17e3ad177b5d52c1470e85da9f7a8645dbada9`；B `8174445e3b8e473bef15a82d345b7a7e1d94ac05`；PR97 `df323eccdffd375a2fb255ebbfd734b6c2be4aac`。不要使用PR merge预览SHA或活动分支的新generate。

配置为 `results/PANEL_CONFIG.json`。面板仅good/weak、static/turn、wall/peer、0/.3m、noisy_unbiased_prior/noisy_biased_prior、seed26011601，按此顺序的笛卡尔积编号0–31。32条件×四方法=128原协议求解。没有straight、新seed或新的独立验证样本。

B固定 `tools/midterm_simulation_s2/prototype.py:generate` 是唯一生成器。PCG64以`SeedSequence([26011601,k])`形成四条固定长度流：54测距、20位移、4先验、24初值扰动。跨geometry/kind/bias/profile共享流身份；它们不是32个独立重复。配置sigma为range .04、motion .02、prior .05、initial .15m；biased prior另加[.15,-.10,-.10,.15]m。

初值是B的prior中心+带噪位移积分+初值扰动；B2末维补0。A不得调用survey替代它。prior中心、sigma、观测和初值都是输入本身。truth仅供合成、离线误差及参考点信息；B3 oracle单独传入，不给B0/B1/B2。

## 复现命令

在本审计分支仓库根运行，所有新路径须不存在。需NumPy2.2.6、SciPy1.15.3、Python3.10.12；可复用README所记venv。B checkout只读使用。

```bash
git fetch origin 8174445e3b8e473bef15a82d345b7a7e1d94ac05
git worktree add --detach /tmp/numerical-panel-b-fixed 8174445e3b8e473bef15a82d345b7a7e1d94ac05
export PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
UWB_PY=/home/ubuntu22/uwb-midterm-s1b-artifacts-20261116/venv/bin/python
"$UWB_PY" tools/midterm_numerical_audit/panel_only.py \
  --b-root /tmp/numerical-panel-b-fixed \
  --out /tmp/numerical-common-panel-new --large /tmp/numerical-common-matrices-new
sha256sum /tmp/numerical-common-panel-new/PANEL_INPUTS.jsonl
```

该入口不依赖A历史外部RAW。调用与本轮相同panel函数：128原协议+32 A独立B2+128继续诊断，原/继续结果分开保存，输入文件自动与本提交版本比对哈希。不是重跑旧2717次。仅需输入时直接读取已提交PANEL_INPUTS.jsonl；verify.py已重新调用generate逐项核验32份输入。

哈希定义：每个obs/noise对象采用B `digest`：`json.dumps(sort_keys=True,separators=(',',':'),allow_nan=False)` 后UTF-8 SHA256。文件SHA对磁盘原字节计算，见results/SHA256SUMS.json；两种哈希不得混用。PANEL_INPUTS有完整obs.start、prior_center、sigma及噪声，PANEL_ORIGINAL另有每方法实际消费receipt哈希（B0排除不用的peer，B3扣除oracle）。sources保存各固定文件SHA。

A/B初点、双方终点完整r/J/g/Dᵀg见Git外PANEL_DETAILS.jsonl。位置/偏差终点已在B2_ENDPOINTS.json提交；全部差值见B2_PARITY.csv。独立循环与向量化模型的差异应逐项报告，不能因最终误差类似就跳过残差/J比较。

复现允许wall-clock耗时字段不同；本轮全部128原终点及optimality恰与B固定保存结果一致。跨不同BLAS平台不承诺逐位终点一致，必须先确认输入字节和源码一致，再报告数值差异，不能改哈希或按真值选分支。

## 两端接口对齐

|项目|核验结果|
|---|---|
|坐标/状态|同为房间XY天线点、6时刻、24位置+可选常b，无yaw|
|几何/轨迹|good/weak、static/turn与PR97一致；本面板不覆盖near/straight|
|运动|20个全局坐标差分，sigma=.02，不是未知航向轮速模型|
|测距|每时刻两车各4墙+1peer，sigma=.04，正偏差增距|
|bias|wall为Car1-anchor0；peer为车间；无bias prior、无非负约束|
|位置prior|仅t0四坐标；B .05，本面板A接收同值；A旧矩阵多sigma不能混同|
|初始化|完全B start，初始b=0；A旧survey不参与|
|信息|data+motion与total分开；尺度位置1/bias.1，rank rtol1e-8|
|停止|两原求解器TRF、ftol/xtol/gtol=1e-10、max_nfev300；成功标签不同|
|故障知识|B2已知候选链路，B3还知幅值；不代表故障识别|
|种子/阶段|26011601已暴露，仅数值开发；正式协议仍未冻结|

本轮输入文件SHA256：`df5c46f4a40518488d61755af21659700afda8d8ecd963bb2efb04911bd011a8`。
