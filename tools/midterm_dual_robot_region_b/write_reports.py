"""Post-freeze Chinese reports generated from full denominators and saved evidence."""
import csv,statistics
from collections import Counter
from common import *

def reports(analysis,readback,gate):
 rows=list(csv.DictReader((analysis/'RUNS.csv').open()));pairs=list(csv.DictReader((analysis/'PAIRED.csv').open()));branches=list(csv.DictReader((analysis/'SIGN_WITNESSES.csv').open()));det=[r for r in rows if r['stage']=='deterministic'];done=[r for r in det if r['status']=='COMPLETED'];main=[r for r in done if r['group']=='main'];inp=read(DOC/'INPUTS.json.gz');lock=read(DOC/'SOURCE_LOCK.json');freeze=gate['freeze_sha']
 def put(name,text):(DOC/name).write_text(text.strip()+'\n')
 def mean(rs,key):
  vals=[float(r[key]) for r in rs if r.get(key) not in (None,'')];return statistics.mean(vals) if vals else float('nan')
 def cell(case,m):
  rr=[r for r in det if r['case']==case and r['method']==m]
  if not rr:return '不在授权计划'
  r=rr[0]
  if r['status']!='COMPLETED':return r['status']
  return f"{r['termination']} / {r['processed']} / {float(r['wall_seconds']):.3f}"
 table='\n'.join('|'+c['id']+'|'+ '|'.join(cell(c['id'],m) for m in ('J5','P4','N4'))+'|' for c in inp['deterministic'])
 put('DETERMINISTIC_REPORT.md',f'''# 确定性正式验证

A来源：{lock['a_sha']}。运行冻结：{freeze}。36项开发检查通过后执行。完整计划44次，实际完成{len(done)}次；未完成{len(det)-len(done)}次。零搜索读回：{readback['status']}，检查{readback['nodes_checked']}树节点。逐记录B/A证书结果及全部分母在results/RUNS.csv；本轮没有非线性优化器调用。

|case|J5：结束原因 / 处理盒 / 总秒|P4：结束原因 / 处理盒 / 总秒|N4：结束原因 / 处理盒 / 总秒|
|---|---|---|---|
{table}

RESOLUTION_COMPLETE表示按照0.05m规则完成搜索；INSIDE盒可提前停止而大于0.05m，因为整盒已认证。BOX_BUDGET等表示未决队列全部保留。预定forced_budget每方法只处理1盒；不把它算入主矩阵意外预算失败。空集不输出伪造半径。

全流程包含B认证、A认证、投影及写盘，实际逐次执行顺序在原始attempt/receipt。未重复计时选最快，零搜索复核成本单列，不替换原计时。每次默认50000盒/30秒搜索、120秒全流程和1GiB。原始A的更宽上限没有被当作扩预算许可。

A归档兼容分母48，其中4个特殊N4为OUTSIDE_USER_AUTHORIZED_PLAN。授权分母仍44，额外4条不执行、不混进实验失败率。原A的empty_in_domain观测被人为改写，其原零噪声标签不再有效；该例噪声事件为NOT_APPLICABLE，可靠域内空集另行核验。

![成本与处理盒](figures/COST_AND_BOXES.png)
''')
 conds=list(dict.fromkeys(r['condition'] for r in main));ct=[];rt=[]
 for cond in conds:
  group={m:[r for r in main if r['condition']==cond and r['method']==m] for m in ('J5','P4','N4')}
  a=mean(group['J5'],'wall_seconds');b=mean(group['P4'],'wall_seconds');n=mean(group['N4'],'wall_seconds')
  ct.append(f'|{cond}|{a:.3f}|{b:.3f}|{n:.3f}|{a/b:.2f}|')
  ds=[]
  for car in ('p','s'):
   da=mean(group['P4'],car+'_area_upper_m2')-mean(group['N4'],car+'_area_upper_m2');dr=mean(group['P4'],car+'_radius_upper_m')-mean(group['N4'],car+'_radius_upper_m');ds.extend([f'{da:+.6f}',f'{dr:+.6f}'])
  rt.append('|'+cond+'|'+'|'.join(ds)+'|')
 comp=[]
 for m in ('J5','P4','N4'):
  rr=[r for r in done if r['method']==m];comp.append('|'+m+'|'+ '|'.join(f"{sum(float(r[k]) for r in rr):.3f}" for k in ('search_seconds','certificate_b_seconds','certificate_a_seconds','projection_seconds','compressed_io_seconds','wall_seconds'))+'|')
 j5=[r for r in main if r['method']=='J5'];p4=[r for r in main if r['method']=='P4'];n4=[r for r in main if r['method']=='N4'];ratio=mean(j5,'wall_seconds')/mean(p4,'wall_seconds')
 put('COST_AND_REGION_COMPARISON.md',f'''# 五维、四维与完整成本

主矩阵12个输入的J5/P4平均全流程成本之比为{ratio:.2f}。其中J5有{sum(r['termination']!='RESOLUTION_COMPLETE' for r in j5)}/12次未完成分辨率搜索，P4为{sum(r['termination']!='RESOLUTION_COMPLETE' for r in p4)}/12；因此这是同输入、同预定预算下的成本比，不是全部达到相同有限外包精度的加速定理。保守预算结果未被删除。

|条件（每行2固定噪声输入）|J5平均总秒|P4平均总秒|N4平均总秒|J5/P4|
|---|---:|---:|---:|---:|
{chr(10).join(ct)}

没有把固定确定性两例当随机样本作置信区间，也不把阈值或缓存配置按正式结果改变。

|方法（含特殊例的实际运行）|搜索秒|B认证秒|A认证秒|投影秒|压缩IO秒|完整墙钟秒|
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(comp)}

完整墙钟还包括输入、评价、进程启动、attempt/receipt持久化等。最大单方法峰值RSS为{max(float(r['peak_rss_kib']) for r in done)/1024:.2f}MiB。成本逐次记账；认证与IO不可从主比较中删去。A认证没有使用B的剪枝界，结果独立性与执行代价同时保留。


CSV与图中半径/成本是十进制显示近似；严格外向包围端点、半径平方及有理数证据以便携包中的原始JSON为准。显示舍入不参与剪枝、包含检查或门槛判定。

位置输出不要求J5/P4相同。results/PAIRED.csv逐车列面积上界、半径、跨度差值及矩形表示是否相同。面积为去重投影和与包围盒面积的较小可靠上界；上界差值不等于精确可行区域面积差值，也没有精确并集面积声明。

主矩阵P4总成本中位数{statistics.median(float(r['wall_seconds']) for r in p4):.3f}秒，N4为{statistics.median(float(r['wall_seconds']) for r in n4):.3f}秒。随机门槛结果{gate['status']}，见GATE.json。
''')
 put('COOPERATIVE_INFORMATION_REPORT.md',f'''# peer对两辆车的约束

比较同一原始输入上的P4(q9=26)与N4(q8=24)。两车都是未知量；没有把另一车均值当精确锚点。两阈值采用同一总风险口径但不同完整噪声维数，因此添加peer并不保证最终区域单调缩小。

|条件|p面积上界变化m²|p半径变化m|s面积上界变化m²|s半径变化m|
|---|---:|---:|---:|---:|
{chr(10).join(rt)}

表中为P4−N4，每条件两固定输入的描述均值。正值表示报告的外包量变大，不是证明真实可行集合变大；负值也不等于精确可行区域面积减少。逐case完整跨度、边界及内部/未决数据见RUNS.csv。

peer只通过dist(I9−‖p−s‖,B)引入耦合。当给定联合位置所需的b在B内部时，该行可残差为零；它并不必然收紧两辆车各自边缘。q9比q8大还会增加锚点残差预算，可能抵消这项约束。b在边界和内部的结果必须一起保留，不能只选有收益条件。

冻结后仅用已有输入/结果新增固定符号见证分析（SIGN_WITNESSES.csv）：在原评价位置上分别反射两车的y，区分精确固定联合位置可行/不可行/UNKNOWN，以及有限外包命中。这里真值只用于离线评价，未进入搜索。候选符号象限不等于已经证明拓扑分支数。

共线锚点下，同时反射两车保留锚点与peer距离，是模型真实对称。单独反射可能改变peer距离；有界b是否能吸收差异由可行b内/外界判定。内部盒可提供该象限存在可行点的证据，只有未决候选而没有内部盒时保持未知，不能据此删除。

具体见证：collinear_b0_zero中，P4在两车同时取正y或同时取负y的固定联合点均为FEASIBLE_PROVED；只反射一车的两个固定点为EMPTY_PROVED。N4四种固定点全部可行。P4仍各保留497个跨两车异侧的候选联合盒且无内部盒，不能由固定点不可行宣称整个候选支为空。collinear_b6_zero中，P4四种固定点均可行，体现有界偏差仍可吸收部分peer差异。两车各自的上下镜像投影都保留；联合组合受约束不等于每车边缘明显变小。

域和B是合成假设。没有给任务告警限，本轮只报计算完成状态和区域尺寸，不称任务安全可用率。完整噪声事件、精确投影可行性和有限外包包含在RUNS.csv分别列出。

![正常几何](figures/normal_b0_zero.png)
![近共线](figures/near_collinear_b0_zero.png)
![共线](figures/collinear_b0_zero.png)
''')
 if gate['status']!='PASS':
  put('SKIPPED_REASON.md',f'''# 条件随机阶段未启动

确定性阶段随机准入门槛：{gate['status']}。

{chr(10).join('- '+r for r in gate['reasons'])}

P4主矩阵总成本中位数：{gate['main_cost_median_seconds']['P4']:.6f}秒；N4：{gate['main_cost_median_seconds']['N4']:.6f}秒。门槛为各自≤2秒，含独立认证及写盘，不能只用搜索耗时替代。

A预冻结120个随机输入保留；授权P4/N4共240次，实际执行0、未执行240。没有运行J5随机矩阵、补seed、删困难case或改变阈值。A归档若枚举三模式共360条，额外120个J5不在本轮授权计划，不能与这240次门槛跳过混淆。

这不是证书错误的同义词。确定性逐记录及零搜索读回结果见DETERMINISTIC_REPORT和READBACK.json；未通过的是这里列明的计算准入条件。后续单时刻性能工作需新冻结，本轮不扩展两时刻。
''')
 put('DECISION_MEMO.md',f'''# 最终决策

1. **真正双车联合外包已实现。** J5五维、P4四维、N4八行联合基线的{len(done)}/44授权确定性记录完成，B/A逐记录证书和零搜索读回{readback['status']}。保证限于声明域、单peer常偏差、已知对角R和正确观测表示；不是实车/HMI保证。
2. **降维在本批显著降低成本，但不偷换完成精度。** 主矩阵平均J5/P4全流程成本比{ratio:.2f}，J5有{sum(r['termination']!='RESOLUTION_COMPLETE' for r in j5)}次预算停止；有限外包未要求相同。全部保守未决和原成本均保留。
3. **共线同时镜像来自真实模型歧义。** 近共线候选象限若没有内部证据，仍不能区分狭窄可行支与区间保守性；矩形重叠及单圆跨空白另增表示保守性。
4. **peer对p和s的边缘作用需分别看。** 双车耦合及固定符号见证可以受约束，但宽B可吸收一部分差异，q9/q8差异又改变锚点剩余预算。区域不是必然两车都缩小，逐车证据见COOPERATIVE_INFORMATION_REPORT。
5. **唯一主优先项：先优化独立A证书核的重复有理数计算成本，暂不进入两时刻。** 本批成本分解显示独立A检查占据主要全流程成本，P4/N4的2秒门槛{gate['status']}。建议下一轮用本批全部已保存树作零搜索对照，在A自己的算术中缓存重复锚点子盒贡献，保留完整树/队列/投影和每一证书检查，绝不复用B求解器的排除界；逐记录结果须与原A核完全一致，并保留冷启动/IO成本。这是已暴露证据上的工程核验，不冒充新随机验证。

Calafiore可信预收缩接口和最小对照已写入LITERATURE_TRANSFER_NOTE，作为后续备选设计；本轮未启用SOCP剪枝，不同时推荐扩维、预收缩和GMP多条主线。当前先处理已经量化的独立认证成本瓶颈。
''')
 put('HANDOFF.md',f'''# 交接与零搜索验收

基准：{BASE}。
A锁定：{lock['a_sha']}。
运行冻结：{freeze}。
B分支：research/dual-robot-region-b；工作区/home/ubuntu22/uwb-dual-robot-region-b。
Git外原始结果：/home/ubuntu22/uwb-dual-robot-region-b-artifacts/results。
交付HEAD通过PR读取，避免文档自引用。

正式确定性授权44，完成{len(done)}，全量读回{readback['status']}。条件随机门槛{gate['status']}；门槛失败时240授权运行全部NOT_RUN。不自动合并、不扩两时刻。

SOURCE_LOCK.json逐项固定A源码/合同。外部复核先从该完整SHA提取其两个目录到只读来源根，然后设置DUAL_A_SOURCE_ROOT。源码原始路径仍列在SOURCE_LOCK，但可通过该环境变量重定位，全部哈希仍必须一致。

```bash
export PY=/path/to/venv/bin/python
export DUAL_A_SOURCE_ROOT=/path/to/read-only-A-source
$PY tools/midterm_dual_robot_region_b/unpack_delivery.py --evidence docs/research/midterm_dual_robot_region_b/evidence --ready docs/research/midterm_dual_robot_region_b/RESULTS_READY.json --out /tmp/dual-portable
$PY tools/midterm_dual_robot_region_b/readback.py --results /tmp/dual-portable/raw --freeze {freeze} --out /tmp/dual-readback.json
sha256sum -c docs/research/midterm_dual_robot_region_b/SHA256SUMS
```

便携包的certificates/是A的原输出格式，raw/含完整B结果、attempt/receipt和分项计时。A可在解包后用自己的check.py archive验证；expected_sha应取RESULTS_READY.source_commit。该值是payload完整提交，发布READY的元数据提交可在其后；归档哈希固定全部payload字节，源码执行身份另外由run_frozen_sha固定。

A兼容归档48条包含4个不在用户计划的特殊N4，故A archive_check会返回INCOMPLETE并列明这4条NOT_RUN；授权44条逐证书均另核验。见USER_PROTOCOL_PRECEDENCE，不能隐藏兼容分母，也不增跑4例凑数。

原核心运行计时和正式结果不可覆写。若遇到attempt无完整receipt，先运行inventory.py清点；未知身份不自动重试。所有后加分析/绘图/归档脚本均为零搜索交付工具，不在正式执行依赖中，未更改冻结清单。
''')
 print(json.dumps(dict(reports_written=True,completed=len(done),random_gate=gate['status'],j5_p4_mean_wall_ratio=ratio)))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--analysis',type=Path,required=True);p.add_argument('--readback',type=Path,required=True);p.add_argument('--gate',type=Path,required=True);a=p.parse_args();reports(a.analysis,read(a.readback),read(a.gate))
