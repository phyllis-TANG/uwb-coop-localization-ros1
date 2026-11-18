"""Post-freeze descriptive reporting; no search/optimizer calls."""
import json,gzip,csv,collections
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from coverage import DOC,ART,write,csvwrite

def main():
 inp=json.loads(gzip.decompress((DOC/'INPUTS.json.gz').read_bytes()));meta={r['observation']['id']:r['reference'] for r in inp};records=[]
 for p in sorted((ART/'runs').glob('*.json')):
  if any(s in p.name for s in ['attempt','checkpoint','PLAN','STATUS']):continue
  r=json.loads(p.read_text());r['meta']=meta[r['task']['id']];records.append(r)
 lookup={(r['meta']['condition'],r['meta']['seed'],r['task']['method']):r for r in records};full=[];fails=[]
 for r in records:
  m=r['metrics'];cond=r['meta']['condition'];method=r['task']['method']
  if r['state']!='ACCEPTED':fails.append(dict(key=r['task']['key'],state=r['state'],gradient_inf=r['gradient_inf'],rank=r['rank'],dimension=r['dimension']))
  for c in range(2):
   full.append(dict(condition=cond,seed=r['meta']['seed'],method=method,car=c+1,state=r['state'],rmse_m=m['rmse_m'][c],peak_m=m['peak_m'][c],anchor_residual_rms_m=m['anchor_residual_rms_m'][c],anchor_residual_slope_m_s=m['anchor_residual_slope_m_s'][c],motion_residual_rms_m=m['motion_residual_rms_m'][c],peer_residual_rms_m=m['peer_residual_rms_m'],shared_peer_bias0_m=m['bias0_m'],shared_peer_slope_m_s=m['bias_slope_m_s'],true_peer_slope_m_s=m['true_slope_m_s'],slope_error_m_s=m['slope_error_m_s'],wall_seconds=r['wall_seconds'],solver_seconds=r['seconds'],nfev=sum(s['nfev'] for s in r['stages'])))
 csvwrite(DOC/'FULL_RESULTS.csv',full);write(DOC/'FAILURE_LEDGER.json',fails)
 groups=collections.defaultdict(list)
 for r in full:groups[(r['condition'],r['method'],r['car'])].append(r)
 summary=[]
 for (cond,m,c),rs in groups.items():
  summary.append(dict(condition=cond,method=m,car=c,runs=len(rs),accepted=sum(r['state']=='ACCEPTED' for r in rs),mean_rmse_m=float(np.mean([r['rmse_m'] for r in rs])),worst_peak_m=max(r['peak_m'] for r in rs),mean_anchor_residual_rms_m=float(np.mean([r['anchor_residual_rms_m'] for r in rs])),mean_motion_residual_rms_m=float(np.mean([r['motion_residual_rms_m'] for r in rs])),mean_peer_residual_rms_m=float(np.mean([r['peer_residual_rms_m'] for r in rs])),mean_shared_slope_m_s=None if rs[0]['shared_peer_slope_m_s'] is None else float(np.mean([r['shared_peer_slope_m_s'] for r in rs])),mean_abs_shared_slope_m_s=None if rs[0]['shared_peer_slope_m_s'] is None else float(np.mean([abs(r['shared_peer_slope_m_s']) for r in rs])),mean_wall_seconds=float(np.mean([r['wall_seconds'] for r in rs]))))
 csvwrite(DOC/'SUMMARY.csv',summary)
 pairs=[];trend=[];optional=[]
 for cond in ['normal','ramp_only','motion_only','both']:
  for seed in range(2026111801,2026111811):
   for base,method in [('M0','M2'),('M0','M3'),('M2','M3')]:
    a=lookup[(cond,seed,base)];b=lookup[(cond,seed,method)]
    for c in range(2):pairs.append(dict(condition=cond,seed=seed,baseline=base,method=method,car=c+1,both_accepted=a['state']==b['state']=='ACCEPTED',rmse_gain_m=a['metrics']['rmse_m'][c]-b['metrics']['rmse_m'][c],peak_gain_m=a['metrics']['peak_m'][c]-b['metrics']['peak_m'][c],peer_residual_reduction_m=a['metrics']['peer_residual_rms_m']-b['metrics']['peer_residual_rms_m']))
  for seed in range(2026111801,2026111811):
   r=lookup[(cond,seed,'M3')];base=lookup[('normal' if cond in ['normal','motion_only'] else 'ramp_only',seed,'M3')];m=r['metrics'];trend.append(dict(condition=cond,seed=seed,state=r['state'],true_slope_m_s=m['true_slope_m_s'],estimated_slope_m_s=m['bias_slope_m_s'],slope_error_m_s=m['slope_error_m_s'],estimated_total_drift_m=m['bias_slope_m_s']*4.42,motion_induced_slope_shift_m_s=m['bias_slope_m_s']-base['metrics']['bias_slope_m_s']))
 for cond in ['normal','correlated_optional']:
  for seed in range(2026111801,2026111811):
   a=lookup[(cond,seed,'M3')];b=lookup[(cond,seed,'M3W')]
   for c in range(2):optional.append(dict(input_noise='white' if cond=='normal' else 'AR1_rho0.8',covariance_relation='MISMATCHED' if cond=='normal' else 'MATCHED',seed=seed,car=c+1,baseline_reused_from_main=cond=='normal',both_accepted=a['state']==b['state']=='ACCEPTED',rmse_gain_m=a['metrics']['rmse_m'][c]-b['metrics']['rmse_m'][c],raw_abs_slope_m_s=abs(a['metrics']['bias_slope_m_s']),whitened_abs_slope_m_s=abs(b['metrics']['bias_slope_m_s']),abs_false_slope_reduction_m_s=abs(a['metrics']['bias_slope_m_s'])-abs(b['metrics']['bias_slope_m_s']),wall_increment_seconds=b['wall_seconds']-a['wall_seconds']))
 csvwrite(DOC/'PAIRS.csv',pairs);csvwrite(DOC/'TREND_DIAGNOSTICS.csv',trend);csvwrite(DOC/'AR1_PAIRS.csv',optional)
 cov=list(csv.DictReader((DOC/'DENSE_COVERAGE.csv').open()));gaps=[]
 for candidate in ['5-14','109-114']:
  for c in [1,2]:
   rows=[r for r in cov if r['candidate']==candidate and int(r['car'])==c];active=[]
   def flush():
    if not active:return
    gaps.append(dict(candidate=candidate,car=c,start_s=float(active[0]['time_s']),end_s=float(active[-1]['time_s']),samples=len(active),coverage_failure=any(float(x['support_min'])<.75 or float(x['fill_distance_max_m'])>.4+1e-12 for x in active),frame_seam_failure=any(float(x['frame_height_spread_max_m'])>.25 for x in active),height_step_failure=any(float(x['height_step_max_m'])>.15 for x in active)));active.clear()
   for r in rows:
    if r['passed']=='False':active.append(r)
    else:flush()
   flush()
 csvwrite(DOC/'GAP_SEGMENTS.csv',gaps)
 # Paired plots show every seed; no outcome-selected examples.
 conditions=['normal','ramp_only','motion_only','both'];fig,axs=plt.subplots(1,3,figsize=(14,4),constrained_layout=True)
 for c in range(2):
  for m in ['M0','M2','M3']:
   vals=[next(r['mean_rmse_m'] for r in summary if r['condition']==cond and r['method']==m and r['car']==c+1) for cond in conditions];axs[c].plot(range(4),vals,'o-',label=m)
  axs[c].set_xticks(range(4),conditions,rotation=20);axs[c].set(title=f'Car{c+1}: all 10 finite seeds',ylabel='RMSE [m]');axs[c].legend()
 for i,cond in enumerate(conditions):
  rr=[r for r in trend if r['condition']==cond];axs[2].scatter(np.full(10,i),[r['estimated_slope_m_s'] for r in rr],alpha=.65);axs[2].plot([i-.2,i+.2],[rr[0]['true_slope_m_s']]*2,color='black',lw=3)
 axs[2].set_xticks(range(4),conditions,rotation=20);axs[2].set(title='M3 peer trend: all seeds; black=true',ylabel='bias slope [m/s]');fig.savefig(DOC/'paired_results.png',dpi=150);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
 for i,cond in enumerate(['white','AR1_rho0.8']):
  rr=[r for r in optional if r['input_noise']==cond and r['car']==1]
  for r in rr:axs[i].plot([0,1],[r['raw_abs_slope_m_s'],r['whitened_abs_slope_m_s']],'o-',alpha=.5)
  axs[i].set_xticks([0,1],['original M3','whitened M3']);axs[i].set(title=cond+(' (mismatch)' if i==0 else ' (match)'),ylabel='absolute false slope [m/s]')
 fig.savefig(DOC/'ar1_false_trend.png',dpi=150);plt.close(fig)
 # Main report is generated only from complete denominators.
 table=[]
 for cond in conditions:
  for m in ['M0','M2','M3']:
   ss=[next(r for r in summary if r['condition']==cond and r['method']==m and r['car']==c) for c in [1,2]];table.append('|'+cond+'|'+m+'|'+'|'.join(f"{r['mean_rmse_m']:.6f} / {r['worst_peak_m']:.6f}" for r in ss)+f"|{ss[0]['accepted']}/10|" )
 ttable=[]
 for cond in conditions:
  rr=[r for r in trend if r['condition']==cond];ttable.append(f"|{cond}|{rr[0]['true_slope_m_s']:.6f}|{np.mean([r['estimated_slope_m_s'] for r in rr]):.6f}|{np.mean([abs(r['estimated_slope_m_s']) for r in rr]):.6f}|{np.mean([r['motion_induced_slope_shift_m_s'] for r in rr]):+.6f}|")
 ot=[]
 for cond in ['white','AR1_rho0.8']:
  rr=[r for r in optional if r['input_noise']==cond];one=[r for r in rr if r['car']==1];ot.append(f"|{cond}|{np.mean([r['raw_abs_slope_m_s'] for r in one]):.6f}|{np.mean([r['whitened_abs_slope_m_s'] for r in one]):.6f}|"+'|'.join(f"{np.mean([r['rmse_gain_m'] for r in rr if r['car']==c]):+.6f}" for c in [1,2])+f"|{np.mean([r['wall_increment_seconds'] for r in one])*1000:+.3f}|")
 mainstates=collections.Counter(r['state'] for r in records if r['meta']['condition']!='correlated_optional' and r['task']['method']!='M3W');optstates=collections.Counter(r['state'] for r in records if r['meta']['condition']=='correlated_optional' or r['task']['method']=='M3W');write(DOC/'EXECUTION_COUNTS.json',dict(main=dict(mainstates),optional_new=dict(optstates),method_runs=len(records),optimizer_calls=sum(r['optimizer_calls_started'] for r in records),optional_comparison_records=40,reused_main_records=10,independent_readback_main=120,independent_readback_optional=30))
 text='''# 连续路线定位对照报告

冻结SHA：4d9003de7a9320d25374948f9093557b3364c3a3。主矩阵120/120完成，119 ACCEPTED、1 NOT_STATIONARY；主读回120条PASS。扩展实际新增30次、40条方法比较记录（复用主矩阵10条）；全部状态见EXECUTION_COUNTS，非接受项见FAILURE_LEDGER。无追加重试，没有重跑主矩阵计时。

## 路线与回放

主路线Car2源5.44–9.86s，Car1源10.44–14.86s，长4.42s。原计划5–14s未整体通过；补2帧后的最长段未变化。备用109–114s的最长通过段109.66–114s（4.34s），仍优先选主路线最长段。GAP_SEGMENTS给出每车具体断点，DENSE_COVERAGE列所有采样。0.02s/0.1m密采样不是连续空间数学保证，也不是地形可通行/轮地接触保证。

CPU实际重新打开单一连续USD、逐时读取组合变换：222关键帧及221个中间插值，共443次PASS；天线位置/车间距离最大差为0（本次浮点输出）。姿态为世界竖直程序车的GT yaw，不是完整真实车体姿态。CPU_REPLAY.csv与5张关键帧/GIF可复核；IsaacGPU探测失败，渲染和动力学未执行，阻塞及命令见HANDOFF。缺口不被当作通路，原始帧高差未被平滑隐藏。

## 主矩阵：逐车位置

24时刻，dt=4.42/23≈0.192174s；单次整个路线联合估计天线XY，公开输入提供地形导出的固定高度，因此3D位置误差的高度分量为0，不能据此声称实现高度融合。所有测距均按3D天线位置生成。人工锚点在评价前固定，两车/各方法/种子共享布局。位置先验含0.5m噪声，测距0.04m、运动增量0.02m为仿真假设。

|条件|方法|Car1平均RMSE / 全seed最大峰值m|Car2平均RMSE / 全seed最大峰值m|数值接受|
|---|---|---:|---:|---:|
'''+ '\n'.join(table)+'''

主表保留全部有限结果，包含未驻点项；PAIRS逐条标识双方接受，不隐去分母。误差由与求解器隔离保存的参考轨迹计算，参考和注入标签不进入求解器API。锚点/高度是明示仿真观测合同，不是由优化结果反标定。

## 真实零偏差时的虚假趋势

M0不使用peer、不估偏差；M2仅常偏差，斜率固定0；M3的一个peer斜率由两车共享，不能拆成两车独立传感器偏差。逐车锚距残差RMS及残差斜率另列FULL_RESULTS；peer残差和bias slope为共享量。ramp从0到0.30m，斜率0.067873303m/s，不能沿用旧1秒窗口的0.30m/s。运动异常只在Car2中段一个增量施加沿yaw的0.15m，不修改参考轨迹，不是月壤动力学。

|条件|真实斜率m/s|M3平均估计斜率|M3平均绝对斜率|配对运动异常引起的平均斜率变化|
|---|---:|---:|---:|---:|
'''+ '\n'.join(ttable)+'''

运动异常的配对有符号趋势变化约+0.000901m/s；平均绝对趋势略降不等于没有失配吸收。正常与异常都保留所有10个seed，不按趋势符号选择。

normal与motion_only的真实bias严格为0；表中非零趋势是噪声/失配吸收，不可解释成真实UWB漂移。TREND_DIAGNOSTICS保留每个种子的符号、绝对量、总漂移和配对变化。不事后设置一个有利的“虚假趋势告警”阈值，也不以10种子作罕见风险保证。

![主对照](paired_results.png)

## 小型AR(1)对照

在相同输入上比较原M3和M3W。预设运动协方差Σij=0.02²×0.8^|i−j|，四个运动分量互相独立；M3W仅白化运动残差及其Jacobian，不白化测距，也不改bias参数。白噪声输入为协方差失配，AR1输入为完全匹配，两种情况真实peer偏差都为0。每类10配对种子；40条方法记录中10条原M3白噪声来自主矩阵，不重计时，新增30次。

|输入|原M3平均绝对虚假斜率m/s|白化后|Car1 RMSE收益m|Car2 RMSE收益m|平均单次总成本增量ms|
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(ot)+'''

匹配时虚假斜率平均绝对量只下降约0.000024m/s，失配时略增；本小样本没有给出普遍抑制虚假趋势的证据。

收益为原M3−白化M3，正数才是改善。单次wall含检查点和评价，结果JSON最终写盘另在阶段墙钟中；毫秒级差异受运行环境影响，只有一次预定测量，没有选最快重跑。该小实验只能说明指定协方差下的匹配/失配表现，参数不是实物标定。配对详细分母在AR1_PAIRS，不能将单车RMSE改善自动解释为虚假趋势减少。

![AR1配对](ar1_false_trend.png)

## 来源和边界

点云与gt.txt来自LuSNAR作者的Moon_1合成序列；Car1与Car2来自同一轨迹相隔5秒，不是两条独立实测轨迹。原10帧及新增2帧各自SHA256在CONTINUOUS_SOURCES；新增帧还做ZIP CRC检查。人工四角锚点来自冻结的路线中心/跨度规则，不来自LuSNAR设施。车体、天线与其杆臂是程序示意，未标定真实车辆。世界转换、旧LiDAR外参假设、栅格处理和GPU版本见README/RESEARCH_LOG。

轮地接触、月壤力学和真实NLOS传播属于后续独立实验。本轮优先交付点云支持范围、连续运动学资产与透明的观测层定位对照，未将填补区或模拟参数包装成真实月球通行证据。
'''
 (DOC/'REPORT.md').write_text(text)
 print(json.dumps(dict(main_states=dict(mainstates),optional_new_states=dict(optstates),runs=len(records),rows=len(full),failures=len(fails))))
if __name__=='__main__':main()
