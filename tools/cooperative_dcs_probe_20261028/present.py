#!/usr/bin/env python3
"""Read saved evidence only; reproducible all-seed tables, traces and figures."""
import argparse,csv,gzip,json,math,shutil
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import SCENARIOS,SEEDS,METHODS,read,dump,sha
COLORS={'D0':'#6c757d','D1':'#d97706','D2':'#2864b4','D3':'#138453'}
LABELS={'nominal':'Nominal','peer_bias':'Forward peer +1.20 m','car1_common_wall_bias':'Car1 four walls +0.30 m'}
PERIODS={'all':lambda t:True,'pre':lambda t:3<=t<24,'fault':lambda t:24<=t<38,'recovery':lambda t:38<=t<48,'late':lambda t:48<=t<=63}
def rows(p):
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return list(csv.DictReader(f))
def save_csv(p,rs):
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def make(evaluation,matrix,out):
    out.mkdir(exist_ok=False);(out/'figures').mkdir();(out/'results').mkdir()
    for name in ['metrics.csv','paired_contrasts.csv','weights.csv','costs.csv','receipt.json','audits.json']:
        shutil.copyfile(evaluation/name,out/'results'/name)
    metrics=rows(evaluation/'metrics.csv');contrast=rows(evaluation/'paired_contrasts.csv');timeline=rows(evaluation/'timeline.csv.gz')
    index={(r['scenario'],int(r['seed']),r['method'],r['scope'],r['period'],r['metric']):r for r in metrics}
    def val(s,k,m,p,q,scope='joint_common_accepted'):return float(index[s,k,m,scope,p,q]['rmse'])
    lines=['# 全部逐车结果','', '数值为真值误差RMSE，位置/间距单位m，yaw单位rad；base XY与天线XY不可混用。下表采用四方法共同accepted时刻；fault=24..37共14，recovery=38..47共10，late=48..63共16，pre=3..23共21，全程共同61。原始范围全程63，前两帧启动仍有有限预测；全有限/每车accepted/共同accepted三口径均在CSV，缺项不剔除分母。', '', '## 全程及分段绝对误差','']
    for s in SCENARIOS:
        lines+=['### '+s,'','|seed|方法|段|n/原分母|Car1 base XY|Car2 base XY|Car1 yaw|Car2 yaw|相对天线XY|天线间距|','|---|---|---|---|---|---|---|---|---|---|']
        for k in SEEDS:
            for p in PERIODS:
                for m in METHODS:
                    r=index[s,k,m,'joint_common_accepted',p,'car1_base_xy_m']
                    vs=[val(s,k,m,p,q) for q in ['car1_base_xy_m','car2_base_xy_m','car1_yaw_rad','car2_yaw_rad','relative_xy_m','distance_m']]
                    lines.append(f'|{k}|{m}|{p}|{r["n"]}/{r["denominator"]}|'+ '|'.join(f'{v:.6f}' for v in vs)+'|')
        lines.append('')
    lines+=['## 两种配对差分，禁止互换解释','','下表delta=目标RMSE−参考RMSE，正值更差；均取精确相同状态epoch的四方法共同accepted交集。A=同一故障输入，相对D0；B=同一方法，相对配对nominal。两列参考对象不同。','','|场景|seed|方法|段|n|Car1 A|Car2 A|Car1 B|Car2 B|','|---|---|---|---|---|---|---|---|---|']
    ci={(r['scenario'],int(r['seed']),r['method'],r['period'],r['contrast'],r['metric']):r for r in contrast if r['scope']=='joint_common_accepted'}
    for s in SCENARIOS[1:]:
        for k in SEEDS:
            for p in ['fault','recovery','late']:
                for m in METHODS:
                    cs=[ci[s,k,m,p,c,q] for c in ['same_fault_input_vs_D0','same_method_fault_vs_nominal'] for q in ['car1_base_xy_m','car2_base_xy_m']]
                    lines.append(f'|{s}|{k}|{m}|{p}|{cs[0]["n"]}|'+ '|'.join(f'{float(c["delta_rmse"]):+.6f}' for c in cs)+'|')
    (out/'TABLES.md').write_text('\n'.join(lines)+'\n')
    # Every scenario and seed: true errors and actual peer leverage at same epoch.
    for s in SCENARIOS:
        fig,axs=plt.subplots(6,3,figsize=(14,14),sharex=True)
        specs=[('car1_base_xy_m','Car1 base XY error [m]'),('car2_base_xy_m','Car2 base XY error [m]'),('relative_xy_m','Relative antenna XY error [m]'),('residual_m','Peer predicted - measured [m]'),('information_weight','Local GN information ratio'),('influence','Peer gradient influence psi')]
        for j,k in enumerate(SEEDS):
            for m in METHODS:
                rs=[r for r in timeline if r['scenario']==s and int(r['seed'])==k and r['method']==m]
                for i,(key,label) in enumerate(specs):
                    axs[i,j].plot([float(r['t_s']) for r in rs],[float(r[key]) if r[key] else math.nan for r in rs],color=COLORS[m],lw=1.3,label=m)
            axs[0,j].set_title('seed '+str(k))
            for i,(_,label) in enumerate(specs):
                ax=axs[i,j];ax.grid(alpha=.22);ax.axvspan(1,3,color='grey',alpha=.12)
                if s!='nominal':ax.axvspan(24,38,color='#e9b349',alpha=.14);ax.axvline(48,color='grey',ls=':',lw=.8)
                if j==0:ax.set_ylabel(label)
                if i==5:ax.set_xlabel('State time [s]; available at t + 1 s (virtual)')
            axs[4,j].set_ylim(-.04,1.04)
        axs[0,0].legend(ncol=4,fontsize=9)
        fig.suptitle(LABELS[s]+' | all finite publications, same receipt cutoff',fontsize=14)
        fig.text(.5,.012,'Grey: startup. D0 / rejected D2: zero current factor effect; prior is retained.\nD1/D2 GN curvature differs from gradient weight; D3 both use s^2. Plots do not measure ROS latency.',ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.04,1,.97));fig.savefig(out/'figures'/f'{s}_synchronous.png',dpi=140);plt.close(fig)
    # Separate axes for distinct references, no team average or seed averaging.
    fig,axs=plt.subplots(2,2,figsize=(12,9))
    for i,p in enumerate(['fault','recovery']):
        for j,c in enumerate(['same_fault_input_vs_D0','same_method_fault_vs_nominal']):
            ax=axs[i,j]
            for m in METHODS[1:]:
                for k,marker in zip(SEEDS,['o','s','^']):
                    x=float(ci['car1_common_wall_bias',k,m,p,c,'car1_base_xy_m']['delta_rmse']);y=float(ci['car1_common_wall_bias',k,m,p,c,'car2_base_xy_m']['delta_rmse'])
                    ax.scatter(x,y,color=COLORS[m],marker=marker,label=f'{m} / {k}',s=65)
            ax.axhline(0,color='black',lw=.7);ax.axvline(0,color='black',lw=.7);ax.grid(alpha=.2);ax.set_title(p+' | '+('same faulty input vs D0' if j==0 else 'same method vs nominal'));ax.set_xlabel('Car1 base XY RMSE difference [m]');ax.set_ylabel('Car2 base XY RMSE difference [m]')
    axs[0,0].legend(fontsize=8,ncol=3);fig.suptitle('Car1 common-wall bias: separate reference conditions; positive = worse')
    fig.tight_layout();fig.savefig(out/'figures'/'paired_tradeoffs.png',dpi=150);plt.close(fig)
    # Full internal weights, not just final-state summaries.
    mechanism=[];history=[]
    for s in SCENARIOS:
        for k in SEEDS:
            raw=read(matrix/f'new-runs/{s}_seed{k}__D3/updates.jsonl.gz');origin=raw[0]['state_epoch_ns']-10**9
            for p,pred in PERIODS.items():
                subset=[r for r in raw if pred(r['state_time_s'])]
                for scope in ['all_active','current_factor']:
                    ps=[peer for r in subset for q in r['dcs_linearizations'] for peer in q['peers'] if scope=='all_active' or peer['state_time_s']==r['state_time_s']]
                    mechanism.append(dict(scenario=s,seed=k,period=p,scope=scope,weight_updates=len(ps),downweighted=sum(x['s']<1 for x in ps),min_information_weight=min(x['information_weight'] for x in ps),max_abs_residual_m=max(abs(x['nominal_e']*.2) for x in ps)))
            for r in raw:
                t=r['state_time_s'];prov=r['provenance'];md=r['marginalization_details']
                history.append(dict(scenario=s,seed=k,t_s=t,window_start_s=r['snapshot']['times_s'][0],window_peer=len(prov['window_peer_factor_ids']),prior_peer=len(prov['prior_peer_factor_ids']),
                    # Inclusive 38: original +/-0.4 s aggregation mixes the fault end.
                    fault_adjacent_peer_in_prior=sum(24<=(int(z.split('|')[1])-origin)/1e9<=38 for z in prov['prior_peer_factor_ids']),
                    prior_cross_norm=float(next(v for v in timeline if v['scenario']==s and int(v['seed'])==k and v['method']=='D3' and float(v['t_s'])==t)['prior_cross_norm']),
                    current_prior_id=prov['current_prior_id'],last_consumed_weight='' if not md or not md[-1]['dcs_consumed_peer'] else md[-1]['dcs_consumed_peer'][0]['information_weight']))
    save_csv(out/'results'/'internal_weights.csv',mechanism);save_csv(out/'results'/'history.csv',history)
    dump(out/'PRESENTATION.json',dict(status='PASS',input_receipt_sha256=sha(evaluation/'receipt.json'),script_sha256=sha(Path(__file__)),estimator_runs=0,all_scenarios=list(SCENARIOS),all_seeds=list(SEEDS)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evaluation',type=Path,required=True);p.add_argument('--matrix',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();make(a.evaluation,a.matrix,a.output)
