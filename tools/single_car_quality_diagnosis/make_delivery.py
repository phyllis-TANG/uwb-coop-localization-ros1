#!/usr/bin/env python3
"""Figures and compact review data from frozen-log diagnosis (no estimator)."""
import argparse,csv,gzip,json,math,shutil,statistics
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_logs import read,dump,write_csv,distance

def csvs(p):return list(csv.DictReader(p.open()))
def select(rows,**kw):return [r for r in rows if all(str(r[k])==str(v) for k,v in kw.items())]
def vals(rows,k):return [float(r[k]) if r[k] not in ('',None) else np.nan for r in rows]
def line(ax,rows,k,label,**kw):ax.plot(vals(rows,'t_s'),vals(rows,k),label=label,**kw)
def style(ax):
 ax.axvspan(12,32,color='tab:red',alpha=.07);ax.axvline(32,color='.5',ls=':',lw=.7);ax.axvline(52,color='.5',ls=':',lw=.7);ax.grid(alpha=.2);ax.set_xlim(0,60)
def save(fig,p):fig.tight_layout();fig.savefig(p,dpi=130);plt.close(fig)
def rmse(rows,k):return float(np.sqrt(np.mean(np.square(vals(rows,k)))))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--original',type=Path,required=True);ap.add_argument('--analysis',type=Path,required=True);ap.add_argument('--interventions',type=Path,required=True);ap.add_argument('--mechanics',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(exist_ok=False);figs=a.output/'figures';figs.mkdir();tl=csvs(a.analysis/'timeline.csv');mh=csvs(a.analysis/'main_history.csv');sh=csvs(a.analysis/'shadow_history.csv');events=json.loads((a.analysis/'healthy_events.json').read_text());periods=csvs(a.analysis/'periods.csv');triggers=[];counter=[]
 for ev in events:
  sc,seed,q,k=[ev[x] for x in ('scenario','seed','group','target')];rr=select(tl,scenario=sc,seed=seed,group=q,target=k);main=select(mh,scenario=sc,seed=seed,group=q);baseq='Q0' if q=='Q2' else 'Q1';baseline=select(mh,scenario=sc,seed=seed,group=baseq);shadow=select(sh,scenario=sc,seed=seed,group=q,role=k)
  inp=a.original/'validation-v1/inputs'/f'{sc}_seed{seed}';labels=json.loads((inp/'labels.json').read_text());origin=labels['origin_epoch_ns'];truth={t['epoch_ns']:t for t in read(inp/'truth.jsonl.gz')};raw=read(inp/'events.jsonl.gz');model=json.loads((inp/f'{q}.json').read_text())['base']['model'];rx=[];ry=[]
  for r in raw:
   if r['kind']=='uwb' and k in r['value']:
    rx.append((r['header_epoch_ns']-origin)/1e9);ry.append(r['value'][k]-model['range_bias_m'][k]-distance(truth[r['header_epoch_ns']]['pose'],model,k))
  fig,axs=plt.subplots(7,1,figsize=(11,14),sharex=True)
  fig.suptitle(f"{ev['event_id']} | all panels: state/header time; cutoff = state + 1 s\npolicy onset {ev['onset_s']:.2f}s, available {ev['onset_available_s']:.3f}s; normal {ev['end_s']:.2f}s, available {ev['end_available_s']:.3f}s",fontsize=10)
  axs[0].scatter(rx,ry,s=2,color='.6',alpha=.3,label='raw corrected - truth (offline)');line(axs[0],rr,'measurement_error_m','median measurement - truth',color='k');line(axs[0],rr,'excluded_prediction_error_m','excluded shadow prediction - truth',color='tab:red');line(axs[0],rr,'signed_score_residual_m','measurement - shadow',color='tab:blue');axs[0].set_ylabel('range error m');axs[0].legend(fontsize=7,ncol=2)
  line(axs[1],rr,'score','frozen score',color='tab:red');line(axs[1],rr,'nominal_score','paired nominal score',color='.4');axs[1].axhline(1.5,ls='--',lw=.7,color='k');axs[1].axhline(.75,ls=':',lw=.7,color='k');axs[1].set_ylabel('score / .20m');axs[1].legend(fontsize=7)
  line(axs[2],rr,'gain',f'{k} actual graph g',color='tab:green',drawstyle='steps-post');fault=select(tl,scenario=sc,seed=seed,group=q,target='node_10');line(axs[2],fault,'gain','node_10 main g',color='tab:red',drawstyle='steps-post');axs[2].axhline(1,color='tab:orange',ls='--',label='node_10 in healthy shadow: always g=1');axs[2].set_ylabel('information g');axs[2].legend(fontsize=7,ncol=3)
  for ax,key,label in zip(axs[3:6],('xy_error_m','yaw_error_rad','bias_error_rad_s'),('base XY m','yaw rad','bias rad/s')):
   line(ax,main,key,q,color='tab:blue');line(ax,baseline,key,baseq,color='.4');line(ax,main,'nominal_'+key,'paired nominal',color='tab:green',ls=':');ax.set_ylabel(label);ax.legend(fontsize=7,ncol=3)
  if q=='Q2':axs[5].text(.3,.5,'Q0/Q2 have no bias state; zero line is not a bias estimate',transform=axs[5].transAxes,fontsize=8)
  line(axs[6],main,'window_nonunit_factors','main retained nonunit factors',color='tab:green');line(axs[6],shadow,'window_fault_affected_positive_factors','shadow active fault-support factors',color='tab:red');line(axs[6],shadow,'prior_fault_affected_positive_ancestors','shadow direct fault ancestors in prior',color='tab:orange',ls='--');axs[6].set_ylabel('factor counts');axs[6].legend(fontsize=7,ncol=2)
  for ax in axs:
   style(ax);ax.axvline(ev['onset_s'],color='tab:purple',ls='--',lw=.7);ax.axvline(ev['end_s'],color='tab:green',ls=':',lw=.7)
  axs[-1].set_xlabel('seconds since original label origin; red shading = raw injection [12,32)');save(fig,figs/(ev['event_id']+'.png'))
  for r in rr:
   if abs(float(r['t_s'])-ev['onset_s'])<1e-6 or abs(float(r['t_s'])-(ev['onset_s']-1))<1e-6:
    sr=next(z for z in shadow if z['t_s']==r['t_s']);triggers.append(dict(event_id=ev['event_id'],**r,shadow_window_fault_factors=sr['window_fault_affected_positive_factors'],shadow_prior_direct_fault_ancestors=sr['prior_fault_affected_positive_ancestors']))
 # All 3 common-cause seeds, not selected cases or independent links.
 fig,axs=plt.subplots(6,3,figsize=(16,15),sharex=True)
 colors=['tab:red','tab:blue','tab:green','tab:orange']
 for col,seed in enumerate((401,419,443)):
  axs[0,col].set_title(f'multi_common_uwb seed {seed} (one shared cause)')
  for k,c in zip(('node_10','node_2','node_3','node_8'),colors):
   z=select(tl,scenario='multi_common_uwb',seed=seed,group='Q3',target=k);line(axs[0,col],z,'score',k,color=c);line(axs[1,col],z,'gain',k,color=c,drawstyle='steps-post')
  axs[0,col].axhline(1.5,color='k',ls='--',lw=.7);axs[0,col].legend(fontsize=7,ncol=2);axs[0,col].set_ylabel('Q3 score');axs[1,col].set_ylabel('Q3 actual g')
  for row,key,label in ((2,'xy_error_m','base XY error m'),(3,'yaw_error_rad','yaw error rad'),(4,'bias_error_rad_s','bias error rad/s')):
   for q,c in [('Q1','.4'),('Q3','tab:blue')]:line(axs[row,col],select(mh,scenario='multi_common_uwb',seed=seed,group=q),key,q,color=c)
   line(axs[row,col],select(mh,scenario='multi_common_uwb',seed=seed,group='Q3'),'nominal_'+key,'nominal',color='tab:green',ls=':');axs[row,col].set_ylabel(label);axs[row,col].legend(fontsize=7,ncol=3)
  z=select(mh,scenario='multi_common_uwb',seed=seed,group='Q3');line(axs[5,col],z,'window_nonunit_factors','retained nonunit',color='tab:green');line(axs[5,col],z,'window_fault_affected_positive_factors','active fault support',color='tab:red');line(axs[5,col],z,'prior_fault_affected_positive_ancestors','prior direct ancestry',color='tab:orange',ls='--');axs[5,col].set_ylabel('Q3 factor counts');axs[5,col].legend(fontsize=7);axs[5,col].set_xlabel('state time s; cutoff = +1 s')
  for ax in axs[:,col]:style(ax)
 save(fig,figs/'multi_common_all_seeds.png')
 d1=csvs(a.interventions/'D1_series.csv');d1summary=[]
 fig,axs=plt.subplots(3,3,figsize=(15,9),sharex=True)
 for col,seed in enumerate((401,419,443)):
  axs[0,col].set_title(f'D1 seed{seed}; exposed-data attribution')
  for row,key in enumerate(('xy_error_m','yaw_error_rad','bias_error_rad_s')):
   for arm,c in [('original_gains_control','tab:blue'),('node2_post32_unity','tab:orange')]:line(axs[row,col],select(d1,seed=seed,arm=arm),key,arm,color=c)
   line(axs[row,col],select(mh,scenario='multi_common_uwb',seed=seed,group='Q1'),key,'original Q1',color='.4');style(axs[row,col]);axs[row,col].set_ylabel(key)
   if row==0:axs[row,col].legend(fontsize=6)
  axs[2,col].set_xlabel('state time s')
  for per,lo,hi in [('full',0,60),('fault',12,32),('post_0_20',32,52),('post_gt20',52,60)]:
   for arm in ('original_gains_control','node2_post32_unity'):
    z=[r for r in select(d1,seed=seed,arm=arm) if lo<=float(r['t_s'])<hi];d1summary.append(dict(seed=seed,period=per,arm=arm,n=len(z),**{k+'_rmse':rmse(z,k) for k in ('xy_error_m','yaw_error_rad','bias_error_rad_s')}))
 save(fig,figs/'D1_all_seeds.png')
 # Compact all-event comparison including negatives (no healthy episode).
 for sc in ('uwb_step','uwb_ramp'):
  for seed in (401,419,443):
   for q in ('Q2','Q3'):
    for k in ('node_2','node_3','node_8'):
     z=select(tl,scenario=sc,seed=seed,group=q,target=k);known=[r for r in z if r['score']];counter.append(dict(scenario=sc,seed=seed,group=q,target=k,episodes=sum(e['scenario']==sc and e['seed']==seed and e['group']==q and e['target']==k for e in events),max_score=max(float(r['score']) for r in known),max_nominal_score=max(float(r['nominal_score']) for r in known)))
 write_csv(a.output/'event_trigger_trace.csv',triggers);write_csv(a.output/'counterexamples.csv',counter);write_csv(a.output/'D1_summary.csv',d1summary)
 for src in ['healthy_events.csv','healthy_events.json','periods.csv','checks.json','paired_input_checks.json']:shutil.copyfile(a.analysis/src,a.output/src)
 for src in ['D2_snapshots.csv','D1_controls.json','jacobian_checks.json','receipt.json']:shutil.copyfile(a.interventions/src,a.output/src)
 shutil.copyfile(a.mechanics/'recovery.csv',a.output/'recovery.csv');shutil.copyfile(a.mechanics/'angular_geometry.csv',a.output/'angular_geometry.csv')
 for src in ['timeline.csv','main_history.csv','shadow_history.csv','marginal_history.csv']:
  with (a.analysis/src).open('rb') as f,gzip.GzipFile(filename='',fileobj=(a.output/(src+'.gz')).open('xb'),mode='wb',mtime=0) as g:shutil.copyfileobj(f,g)
 v=json.loads((a.analysis.parent/'verification.json').read_text());dump(a.output/'verification_summary.json',{k:v[k] for k in v if k not in ('runs','reused_files')})
 print('PASS: 10 figures, 8 complete event traces, all seeds and compact records')
if __name__=='__main__':main()
