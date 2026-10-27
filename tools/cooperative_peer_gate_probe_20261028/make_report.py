#!/usr/bin/env python3
"""Compact tables/figures from independently evaluated time series, no replay."""
import argparse,csv,gzip,json,math,shutil
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
SEEDS=(101,211,307)
SCENARIOS=('nominal','peer_bias','wall_bias','peer_gap','car1_common_wall_bias')
COLORS={'G0':'.4','G1':'tab:red','G2':'tab:blue'}
def table(p):
 with Path(p).open() as f:return list(csv.DictReader(f))
def select(rows,**kw):return [r for r in rows if all(str(r[k])==str(v) for k,v in kw.items())]
def values(rows,k):return [float(r[k]) if r[k] not in ('',None) else np.nan for r in rows]
def plot(ax,rows,key,label,scale=1.,**kw):ax.plot(values(rows,'t_s'),np.array(values(rows,key))*scale,label=label,**kw)
def style(ax):
 ax.axvspan(24,38,color='tab:red',alpha=.07);ax.axvline(38,color='.5',ls=':',lw=.7);ax.axvline(58,color='.5',ls='--',lw=.7);ax.set_xlim(0,64);ax.grid(alpha=.2)
def save(fig,p):fig.tight_layout();fig.savefig(p,dpi=125);plt.close(fig)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--evaluation',type=Path,required=True);ap.add_argument('--matrix',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(exist_ok=False);figdir=a.output/'figures';figdir.mkdir();timeline=table(a.evaluation/'timeline.csv');metrics=table(a.evaluation/'metrics.csv');deltas=table(a.evaluation/'paired_deltas.csv')
 for sc in SCENARIOS:
  fig,axs=plt.subplots(8,3,figsize=(17,18),sharex=True)
  for col,seed in enumerate(SEEDS):
   gate=select(timeline,scenario=sc,seed=seed,method='G2');axs[0,col].set_title(f'{sc}\nseed {seed}; state time, cutoff = t + 1 s',fontsize=10)
   plot(axs[0,col],gate,'peer_measurement_truth_error_m','peer median - truth',color='k');plot(axs[0,col],gate,'auxiliary_prediction_truth_error_m','G0 reference - truth',color='tab:orange');axs[0,col].set_ylabel('range error m');axs[0,col].legend(fontsize=7)
   plot(axs[1,col],gate,'q','engineering q',color='tab:blue');axs[1,col].axhline(3,color='k',ls='--',lw=.7,label='reject q > 3');axs[1,col].set_ylabel('q (null omitted)');axs[1,col].legend(fontsize=7)
   states={'missing':0,'unknown':1,'rejected':2,'accepted':3};axs[2,col].step(values(gate,'t_s'),[states[r['gate_state']] for r in gate],where='post',color='tab:green');axs[2,col].set_yticks(range(4),list(states));axs[2,col].set_ylim(-.3,3.3);axs[2,col].set_ylabel('G2 category')
   for row,key,label,scale in [(3,'car1_antenna_xy_error_m','Car1 antenna XY m',1),(4,'car2_antenna_xy_error_m','Car2 antenna XY m',1),(5,'relative_antenna_xy_error_m','relative antenna XY m',1),(6,'car1_yaw_error_rad','Car1 yaw error deg',180/math.pi),(7,'car2_yaw_error_rad','Car2 yaw error deg',180/math.pi)]:
    for method in ('G0','G1','G2'):plot(axs[row,col],select(timeline,scenario=sc,seed=seed,method=method),key,method,color=COLORS[method],scale=scale)
    if sc!='nominal' and row in (4,7):plot(axs[row,col],select(timeline,scenario='nominal',seed=seed,method='G2'),key,'nominal G2',color='tab:green',ls=':',scale=scale)
    axs[row,col].set_ylabel(label);axs[row,col].legend(fontsize=7,ncol=3)
   for ax in axs[:,col]:style(ax)
   axs[-1,col].set_xlabel('state seconds; red = raw fault [24,38); dashed = 38+20')
  save(fig,figdir/(sc+'_all_seeds.png'))
 for sc in ('peer_bias','car1_common_wall_bias'):
  fig,axs=plt.subplots(5,3,figsize=(16,12),sharex=True)
  for col,seed in enumerate(SEEDS):
   axs[0,col].set_title(f'{sc}: history seed {seed}')
   for method in ('G0','G1','G2'):
    rows=select(timeline,scenario=sc,seed=seed,method=method)
    plot(axs[0,col],rows,'car2_antenna_xy_error_m',method,color=COLORS[method])
    plot(axs[3,col],rows,'prior_cross_information_norm',method,color=COLORS[method]);plot(axs[4,col],rows,'prior_affine_offset_norm',method,color=COLORS[method])
   for method in ('G1','G2'):
    rows=select(timeline,scenario=sc,seed=seed,method=method);plot(axs[1,col],rows,'window_fault_peer_factors' if sc=='peer_bias' else 'window_fault_wall_factors',method,color=COLORS[method]);plot(axs[2,col],rows,'prior_fault_peer_factors' if sc=='peer_bias' else 'prior_fault_wall_factors',method,color=COLORS[method])
   for row,label in enumerate(('Car2 antenna XY m','active fault-support factors','direct fault ancestors in prior','joint cross-information norm','prior affine-offset norm')):
    axs[row,col].set_ylabel(label);axs[row,col].legend(fontsize=7,ncol=3);style(axs[row,col])
   axs[-1,col].set_xlabel('state time s; ancestry is not causal effect magnitude')
  save(fig,figdir/(sc+'_history.png'))
 fig,axs=plt.subplots(2,3,figsize=(16,8))
 causes=('peer_bias','wall_bias','peer_gap','car1_common_wall_bias')
 for col,seed in enumerate(SEEDS):
  for row,period in enumerate(('fault','recovery')):
   ax=axs[row,col];x=np.arange(len(causes));width=.24
   for i,method in enumerate(('G0','G1','G2')):
    yy=[float(next(r for r in deltas if r['scenario']==sc and r['seed']==str(seed) and r['method']==method and r['scope']=='joint_common_accepted' and r['period']==period and r['contrast']=='fault_increment_versus_matched_nominal')['car2_antenna_xy_error_m_delta_rmse']) for sc in causes];ax.bar(x+(i-1)*width,yy,width,label=method,color=COLORS[method])
   ax.set_xticks(x,['peer bias','single wall','peer gap','Car1 common\nwalls']);ax.set_title(f'seed {seed}, {period}');ax.set_ylabel('Car2 RMSE - matched nominal (m)');ax.axhline(0,color='k',lw=.7);ax.grid(axis='y',alpha=.2);ax.legend(fontsize=8)
 save(fig,figdir/'car2_propagation_paired.png')
 boundary=[r for r in timeline if r['scenario']=='peer_bias' and r['method']=='G2' and float(r['t_s']) in (24.,38.)]
 with (a.output/'mixed_boundary.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(boundary[0]),lineterminator='\n');w.writeheader();w.writerows(boundary)
 for name in ('metrics.csv','gate_counts.csv','paired_deltas.csv','costs.csv','marginal_FD_checks.json','receipt.json'):shutil.copyfile(a.evaluation/name,a.output/name)
 with (a.output/'timeline.csv.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0) as z:z.write((a.evaluation/'timeline.csv').read_bytes())
 shutil.copyfile(a.matrix/'index.json',a.output/'RUN_INDEX.json')
 print('PASS: eight all-seed figures, all 45-cell tables and compressed time series')
if __name__=='__main__':main()
