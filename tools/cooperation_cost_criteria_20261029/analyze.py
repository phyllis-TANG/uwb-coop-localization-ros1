"""Read-only paired evidence analysis. No online estimator/optimizer imports."""
import argparse,csv,hashlib,itertools,json,math
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SRC=ROOT/'docs/research/history_recovery_minimal_20261029'
DOC=ROOT/'docs/research/cooperation_cost_criteria_20261029'
MAIN=['I','J','W025','C004','K004']
DIAGNOSTIC=['N','Nclip','A0_4','A4_0']
CASES=['nominal_seed101','car1_common_wall_bias_seed101']
PHASES={'all':(1,64),'pre':(1,24),'fault':(24,38),'recovery':(38,48),'late':(48,59),'clean_active_window':(59,64)}
EPS=1e-12

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def dump(p,o):Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def save(p,rows):
 with Path(p).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def rms(x):return float(np.sqrt(np.mean(np.square(x)))) if len(x) else None
def relation(a,b,eps=EPS):
 d=np.asarray(a)-np.asarray(b)
 if np.all(abs(d)<=eps):return 'arithmetic_tie'
 if np.all(d<=eps) and np.any(d < -eps):return 'A_arithmetic_dominates'
 if np.all(d>=-eps) and np.any(d>eps):return 'B_arithmetic_dominates'
 return 'tradeoff'
def signed_change(target,reference):return rms(target)-rms(reference)

def main(out):
 lock=json.loads((SRC/'SHA256SUMS.json').read_text());inputs={}
 for name in ['TIMESERIES.csv','METRICS.csv','COSTS.csv','RUN_INDEX.json','REPORT.md','CHECKS.json']:
  p=SRC/name;assert sha(p)==lock[str(p.relative_to(ROOT))],name;inputs[str(p.relative_to(ROOT))]=sha(p)
 rows=load(SRC/'TIMESERIES.csv');old=load(SRC/'METRICS.csv');idx={(r['case'],r['method'],r['car'],float(r['t_s'])):r for r in rows};assert len(idx)==len(rows)==2268
 metrics=[];paired=[];denoms=[];numerical=[]
 for case in CASES:
  for method in MAIN+DIAGNOSTIC:
   for phase,(lo,hi) in PHASES.items():
    alltimes=[float(t) for t in range(lo,hi)]
    for scope in ['all_finite','common_accepted']:
     times=[t for t in alltimes if all(idx[case,m,c,t]['finite']=='True' and (scope=='all_finite' or idx[case,m,c,t]['common_accepted']=='True') for m in MAIN+DIAGNOSTIC for c in ['car1','car2'])]
     cars=[]
     for car in ['car1','car2']:
      rr=[idx[case,method,car,t] for t in times];ii=[idx[case,'I',car,t] for t in times];total=[idx[case,method,car,t] for t in alltimes]
      for r,i in zip(rr,ii):assert r['state_epoch_ns']==i['state_epoch_ns'] and r['cutoff_epoch_ns']==i['cutoff_epoch_ns']
      e=[float(r['xy_error_m']) for r in rr];ei=[float(r['xy_error_m']) for r in ii];y=[float(r['yaw_error_rad']) for r in rr];yi=[float(r['yaw_error_rad']) for r in ii]
      delta=signed_change(e,ei);dy=signed_change(y,yi);point=np.asarray(e)-ei
      q=dict(case=case,method=method,role='primary_fixed_configuration' if method in MAIN else 'offline_diagnostic_not_fair_ranking',phase=phase,scope=scope,car=car,denominator=len(alltimes),n=len(times),xy_rmse_m=rms(e),reference_xy_rmse_m=rms(ei),delta_xy_rmse_m=delta,help_signed_m=-delta,yaw_rmse_rad=rms(y),delta_yaw_rmse_rad=dy,mean_positive_harm_m=float(np.mean(np.maximum(point,0))),sampled_positive_harm_integral_m_s=float(np.sum(np.maximum(point,0))*1.),sampled_positive_help_integral_m_s=float(np.sum(np.maximum(-point,0))*1.),max_positive_harm_m=float(max(0,max(point))),reference_accepted=sum(r['reference_accepted']=='True' for r in total),main_accepted=sum(r['main_accepted']=='True' for r in total),unknown=sum(r['mode']=='unknown' for r in total),fallback=sum(r['mode']=='reference_fallback' for r in total),failure=sum('failed' in r['status'] or 'error' in r['status'] for r in total),missing_publications=0)
      original=next(r for r in old if all(r[k]==q[k] for k in ['case','method','phase','scope','car']));assert int(original['n'])==len(times) and int(original['denominator'])==len(alltimes)
      for k in ['xy_rmse_m','yaw_rmse_rad']:numerical.append(abs(q[k]-float(original[k])));assert numerical[-1]<1e-12
      metrics.append(q);cars.append(q)
     paired.append(dict(case=case,method=method,role=cars[0]['role'],phase=phase,scope=scope,denominator=len(alltimes),n=len(times),car1_help_signed_mm=-1000*cars[0]['delta_xy_rmse_m'],car2_cost_signed_mm=1000*cars[1]['delta_xy_rmse_m'],car1_xy_rmse_mm=1000*cars[0]['xy_rmse_m'],car2_xy_rmse_mm=1000*cars[1]['xy_rmse_m'],car1_yaw_rmse_deg=math.degrees(cars[0]['yaw_rmse_rad']),car2_yaw_rmse_deg=math.degrees(cars[1]['yaw_rmse_rad']),car1_delta_yaw_deg=math.degrees(cars[0]['delta_yaw_rmse_rad']),car2_delta_yaw_deg=math.degrees(cars[1]['delta_yaw_rmse_rad']),unknown=cars[0]['unknown'],fallback=cars[0]['fallback'],failure=cars[0]['failure']))
 lookup={(r['case'],r['method'],r['phase'],r['scope'],r['car']):r for r in metrics}
 pairs=[];globalpairs=[]
 for a,b in itertools.combinations(MAIN,2):
  for case in CASES:
   for phase in PHASES:
    for scope in ['all_finite','common_accepted']:
     aa=[lookup[case,a,phase,scope,c] for c in ['car1','car2']];bb=[lookup[case,b,phase,scope,c] for c in ['car1','car2']]
     va=[r['xy_rmse_m'] for r in aa];vb=[r['xy_rmse_m'] for r in bb];ya=[r['yaw_rmse_rad'] for r in aa];yb=[r['yaw_rmse_rad'] for r in bb]
     pairs.append(dict(case=case,phase=phase,scope=scope,A=a,B=b,n=aa[0]['n'],xy_relation=relation(va,vb),xy_yaw_relation=relation(va+ya,vb+yb),A_minus_B_car1_xy_mm=1000*(va[0]-vb[0]),A_minus_B_car2_xy_mm=1000*(va[1]-vb[1]),A_minus_B_car1_yaw_deg=math.degrees(ya[0]-yb[0]),A_minus_B_car2_yaw_deg=math.degrees(ya[1]-yb[1]),interpretation='arithmetic only; no practical margin or statistical inference'))
  for scope in ['all_finite','common_accepted']:
   aa=[lookup[case,a,ph,scope,c] for case in CASES for ph in PHASES if ph!='all' for c in ['car1','car2']];bb=[lookup[case,b,ph,scope,c] for case in CASES for ph in PHASES if ph!='all' for c in ['car1','car2']]
   va=[r['xy_rmse_m'] for r in aa];vb=[r['xy_rmse_m'] for r in bb];ya=[r['yaw_rmse_rad'] for r in aa];yb=[r['yaw_rmse_rad'] for r in bb]
   globalpairs.append(dict(A=a,B=b,scope=scope,xy_relation_all_prespecified_phases=relation(va,vb),xy_yaw_relation_all_prespecified_phases=relation(va+ya,vb+yb),includes_both_conditions=True,cost_not_comparable=True,practical_dominance='UNDETERMINED'))
 # Same method fault-minus-nominal stays distinct from cooperation-minus-I.
 condition=[]
 for r in metrics:
  if r['case']!=CASES[1]:continue
  n=lookup[CASES[0],r['method'],r['phase'],r['scope'],r['car']]
  condition.append({k:r[k] for k in ['method','phase','scope','car','n']}|dict(contrast='same_method_fault_minus_nominal',delta_xy_rmse_m=r['xy_rmse_m']-n['xy_rmse_m'],delta_yaw_rmse_rad=r['yaw_rmse_rad']-n['yaw_rmse_rad']))
 out.mkdir(exist_ok=True)
 for name,rs in [('PER_CAR',metrics),('TRADEOFF_POINTS',paired),('PAIRWISE_RELATIONS',pairs),('GLOBAL_RELATIONS',globalpairs),('PAIRED_CONDITIONS',condition)]:save(out/(name+'.csv'),rs)
 dump(out/'CHECKS.json',dict(status='PASS',source_rows=len(rows),unique_identities=len(idx),recomputed_metric_scalars=len(numerical),max_old_metric_difference=max(numerical),source_sha256=inputs,estimator_runs=0,source_modified=False,scope='readback only; no independent experiments, no confidence intervals'))
 plots(out,paired)
 print(json.dumps({'status':'PASS','rows':len(rows),'points':len(paired),'pairwise':len(pairs),'global':globalpairs},indent=2))

def plots(out,points):
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 colors={'I':'black','J':'#0072b2','W025':'#009e73','C004':'#d55e00','K004':'#cc79a7','N':'#56b4e9','Nclip':'#e69f00','A0_4':'#777777','A4_0':'#882255'}
 groups=[(CASES[0],'all','Normal: all accepted states'),(CASES[1],'fault','Biased walls: fault [24,38)'),(CASES[1],'recovery','Biased walls: recovery [38,48)')]
 def draw(ax,case,phase,methods,title):
  selected=[r for r in points if r['case']==case and r['phase']==phase and r['scope']=='common_accepted' and r['method'] in methods]
  for k,r in enumerate(selected):
   m=r['method'];x=r['car2_cost_signed_mm'];y=r['car1_help_signed_mm'];ax.scatter(x,y,c=colors[m],s=48,marker='s' if m in DIAGNOSTIC else 'o',zorder=3)
   offsets={'I':(8,-13),'J':(-30,4),'W025':(8,-16),'C004':(8,18),'K004':(8,-22),'N':(8,8),'Nclip':(-35,-16),'A0_4':(8,-16),'A4_0':(8,10)}
   ax.annotate(m,(x,y),xytext=offsets[m],textcoords='offset points',fontsize=9,arrowprops=dict(arrowstyle='-',lw=.5,color=colors[m]))
  ax.axhline(0,c='grey',lw=.6);ax.axvline(0,c='grey',lw=.6);ax.grid(alpha=.2);ax.margins(.22);ax.set_title(title+'\nn='+str(selected[0]['n']));ax.set_xlabel('Car2 cost vs I (mm RMSE); lower is better');ax.set_ylabel('Car1 help vs I (mm RMSE); higher is better')
 fig,axs=plt.subplots(1,3,figsize=(15,4.8))
 for ax,(case,phase,title) in zip(axs,groups):draw(ax,case,phase,MAIN,title)
 fig.suptitle('Fixed configurations only; arithmetic tradeoffs, not significance or safety limits',fontsize=12);fig.tight_layout();fig.savefig(out/'MAIN_TRADEOFF.png',dpi=170);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(11,4.8))
 for ax,phase in zip(axs,['late','clean_active_window']):draw(ax,CASES[1],phase,MAIN,'Biased walls: '+phase)
 fig.suptitle('Full declared recovery tail retained; no fitted frontier',fontsize=12);fig.tight_layout();fig.savefig(out/'RECOVERY_TAIL.png',dpi=170);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(11,4.8))
 draw(axs[0],CASES[1],'recovery',['I','J','C004','N','Nclip'],'Offline fixed-time cut: not a causal policy')
 draw(axs[1],CASES[1],'fault',['I','J','C004','A0_4','A4_0'],'Unequal budgets: publication algebra only')
 fig.tight_layout();fig.savefig(out/'DIAGNOSTICS_ONLY.png',dpi=170);plt.close(fig)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=DOC);a=p.parse_args();main(a.output)
