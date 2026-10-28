#!/usr/bin/env python3
"""Plot saved outputs only. Missing bias is NaN for plotting, never zero."""
import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ARMS=('M0','M1','M2','M3');COLORS=dict(zip(ARMS,['#666666','#e3892b','#337ab7','#218c63']))
SCENARIOS=('nominal','gyro_constant_bias','car1_gyro_gap','peer_bias','car1_common_wall_bias')


def make(evaluation,output):
    evaluation=Path(evaluation);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    with gzip.open(evaluation/'timeline.csv.gz','rt') as f:rows=list(csv.DictReader(f))
    metrics=list(csv.DictReader((evaluation/'metrics.csv').open()));costs=list(csv.DictReader((evaluation/'costs.csv').open()))
    for scenario in SCENARIOS:
        fig,axes=plt.subplots(7,2,figsize=(13,15),sharex=True)
        for col,seed in enumerate((101,211)):
            for method in ARMS:
                for i,car in enumerate(('car1','car2')):
                    values=[r for r in rows if r['scenario']==scenario and int(r['seed'])==seed and r['method']==method and r['vehicle']==car]
                    t=[float(r['state_time_s']) for r in values]
                    for row,key,scale in [(i,'antenna_xy_m_error',1),(2+i,'yaw_rad_error',180/math.pi),(4+i,'bias_rad_s_error',1)]:
                        y=[float(r[key])*scale if r[key] else np.nan for r in values]
                        axes[row,col].plot(t,y,label=method,color=COLORS[method],lw=1.1)
                    valid=[int(r['valid']=='True')+i*1.15 for r in values]
                    axes[6,col].step(t,valid,where='post',color=COLORS[method],lw=.8,alpha=.8)
                    failed=[r for r in values if 'solver_' in r['status'] or 'marginal_error' in r['status']]
                    if failed:axes[i,col].scatter([float(r['state_time_s']) for r in failed],[float(r['antenna_xy_m_error']) for r in failed],marker='x',s=15,color=COLORS[method])
            axes[0,col].set_title(f'{scenario}, seed {seed}')
            for ax in axes[:,col]:ax.axvspan(24,38,color='#d95f02',alpha=.10);ax.axvline(48,color='gray',ls=':',lw=.6);ax.grid(alpha=.2)
            axes[-1,col].set_xlabel('state time (s); availability cutoff = t + 1s (virtual)')
        for ax,label in zip(axes[:,0],['Car1 antenna XY error (m)','Car2 antenna XY error (m)','Car1 wrapped yaw error (deg)','Car2 wrapped yaw error (deg)','Car1 bias error (rad/s)','Car2 bias error (rad/s)','valid: C1 0/1; C2 +1.15']):ax.set_ylabel(label)
        axes[0,0].legend(ncol=4);fig.tight_layout();fig.savefig(output/(scenario+'.png'),dpi=140);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(14,6),sharex=True);x=np.arange(len(costs));labels=[]
    for i,r in enumerate(costs):
        labels.append(r['scenario']+'\n'+r['seed']+' '+r['method'])
        for k,color in [('accepted','#218c63'),('car1_valid','#337ab7'),('car2_valid','#e3892b')]:axes[0].scatter(i,int(r[k]),s=12,label=k if i==0 else None,color=color)
        axes[1].bar(i,float(r['elapsed_s']),color=COLORS[r['method']])
    axes[0].legend();axes[0].set_ylabel('count / 63 joint outputs');axes[1].set_ylabel('offline replay + IO wall s');axes[1].set_xticks(x,labels,rotation=90,fontsize=6)
    fig.tight_layout();fig.savefig(output/'coverage_cost.png',dpi=160);plt.close(fig)
    table=['# 全40单元表','', 'XY为天线中心；yaw单位度；bias单位rad/s。M0/M1无bias状态，空值不替换0。', '']
    for mask in ('all_finite','joint_common_valid'):
        table += ['## '+mask,'','|场景|seed|方法|n C1/C2/pair|C1 XY m|C1 yaw deg|C1 bias|C2 XY m|C2 yaw deg|C2 bias|相对XY m|斜距 m|','|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
        for scenario in SCENARIOS:
            for seed in (101,211):
                for arm in ARMS:
                    rs=[r for r in metrics if r['scenario']==scenario and int(r['seed'])==seed and r['method']==arm and r['mask']==mask and r['segment']=='all']
                    def get(c,k):return next(r for r in rs if r['vehicle']==c and r['metric']==k)
                    out=[scenario,str(seed),arm,'/'.join(get(c,'relative_xy_m' if c=='pair' else 'antenna_xy_m')['selected_publications'] for c in ('car1','car2','pair'))]
                    for c in ('car1','car2'):
                        for k in ('antenna_xy_m','yaw_rad','bias_rad_s'):
                            v=get(c,k)['rmse'];out.append('—' if not v else f'{float(v)*(180/math.pi if k=="yaw_rad" else 1):.5f}')
                    out += [f'{float(get("pair",k)["rmse"]):.5f}' for k in ('relative_xy_m','distance_m')]
                    table.append('|'+ '|'.join(out)+'|')
        table.append('')
    table += ['各pre/fault/recovery/late分段、每车有效与共同accepted另见metrics.csv；配对四种条件作用见contrasts.csv；同seed同epoch正常增量见propagation.csv。']
    (output/'TABLES.md').write_text('\n'.join(table)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evaluation',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();make(a.evaluation,a.output)
