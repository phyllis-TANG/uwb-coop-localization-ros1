# B：必要条件核验，不实现新定位器

入口为同名docs目录的B_DECISION.md、B_ANALYSIS.md、B_ASSUMPTIONS.json。
PROOF_CONFIG.json与docs/PREREGISTRATION.md先于计算提交d5aa03d；执行源码bb99db0。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/cooperative_followup_20261029/b_method/analyze.py \
  --output docs/research/cooperative_followup_20261029/b_method/new_results
PYTHONDONTWRITEBYTECODE=1 python3 tools/cooperative_followup_20261029/b_method/verify.py
```

analyze只用stdlib Fraction/Decimal；输出目录须在指定docs b_method内且尚不存在。
它只计算一份在线观测对应的两个真值解释，真值/准确角色只在离线评价环节使用；
并对原PR72的紧凑RMSE数值作4次差分，读取8行成本。没有原始数据、FGO/优化器、
种子、阈值搜索或二维候选试验；不把闭式代理模型改叫原始UWB方法。
results中的预算检验仅是一维天线中心位置，本轮没有重新执行PR72二维杆臂/完整prior审计。
