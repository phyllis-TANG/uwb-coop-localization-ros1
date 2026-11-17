"""Full-denominator summaries, seed-paired bootstrap and plots; no search."""
import argparse,csv,math,collections
import numpy as np
from fractions import Fraction as F
from common import *

def num(v):return float(F(v)) if v is not None else None
def csvwrite(path,rows):
 if not rows:return
 with path.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def wilson(k,n):
 if not n:return None,None
 z=1.959963984540054;p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return c-h,c+h

def analyze(src,out):
 out.mkdir(parents=True,exist_ok=False);c=config();allrows=[];summaries=[];paired=[]
 for stage in ['deterministic','random']:
  path=src/stage
  if not path.exists():continue
  times={r['id']:r['wall_seconds'] for r in [json.loads(x) for x in (path/'WALL_COSTS.jsonl').read_text().splitlines()]}
  rows=[]
  for f in sorted(path.glob('*.receipt.json')):
   r=read(f);r.update(stage=stage,wall_seconds=times.get(r['id']),area_upper=num(r['area_upper']),area_lower=num(r['area_lower']),radius=num(r['radius']));rows.append(r);allrows.append(r)
  groups=collections.defaultdict(list)
  plan=read(DOC/'INPUTS.json.gz')[stage]
  for r in rows:groups[(r['condition'],r['method'])].append(r)
  for condition in sorted({x['condition'] for x in plan}):
   planned=sum(x['condition']==condition for x in plan)
   for method in ['OLD','PROFILED']:
    rs=groups[condition,method];valid=[r for r in rs if r['certificate']=='PASS' and r['numerical_failure'] is None];n=len(valid);hit=sum(r['truth_contained'] for r in valid);ci=wilson(hit,n) if stage=='random' else (None,None)
    def mean(key):
     pool=rs if key in ['search_seconds','certificate_seconds','result_io_seconds','metrics_evaluation_seconds','wall_seconds','processed','undecided'] else valid
     return float(np.mean([r[key] for r in pool if r[key] is not None])) if any(r[key] is not None for r in pool) else None
    summaries.append(dict(stage=stage,condition=condition,method=method,planned=planned,executed=len(rs),unexecuted=planned-len(rs),cert_failed=sum(r['certificate']!='PASS' for r in rs),valid_certified=n,numerical_failure=sum(r['numerical_failure'] is not None for r in rs),budget_stops=sum(r['termination'] in ('BOX_BUDGET','TIME_BUDGET') for r in rs),empty=sum(r['empty'] for r in rs),truth_contained=hit,coverage_valid=hit/n if n else None,coverage_full_lower=hit/planned,coverage_ci_low=ci[0],coverage_ci_high=ci[1],noise_event=sum(r['noise_event'] for r in rs),mirror_retained=sum(r['mirror_contained'] is True for r in rs),mean_radius=mean('radius'),radius_n=sum(r['radius'] is not None for r in valid),mean_area_upper=mean('area_upper'),mean_search=mean('search_seconds'),mean_certification=mean('certificate_seconds'),mean_result_io=mean('result_io_seconds'),mean_metrics=mean('metrics_evaluation_seconds'),mean_wall=mean('wall_seconds'),mean_processed=mean('processed'),mean_undecided=mean('undecided')))
  for condition in sorted({x['condition'] for x in plan}):
   old={r['case']:r for r in groups[condition,'OLD']};new={r['case']:r for r in groups[condition,'PROFILED']};pairs=[(old[k],new[k]) for k in sorted(set(old)&set(new))]
   for metric in ['wall_seconds','search_seconds','certificate_seconds','result_io_seconds','processed','area_upper','radius','truth_contained']:
    vals=[(a[metric],b[metric]) for a,b in pairs if a[metric] is not None and b[metric] is not None and (metric not in ['area_upper','radius','truth_contained'] or (a['certificate']==b['certificate']=='PASS' and a['numerical_failure'] is None and b['numerical_failure'] is None)) and not (metric in ['wall_seconds','search_seconds','certificate_seconds','result_io_seconds'] and a['reused'])]
    if not vals:continue
    a=np.array(vals,float);diff=a[:,1]-a[:,0];ci=(None,None);ratio=float(a[:,0].mean()/a[:,1].mean()) if a[:,1].mean()!=0 else None
    if stage=='random' and len(a)>=c['bootstrap']['minimum_pairs']:
     rng=np.random.default_rng(c['bootstrap']['seed']);ix=rng.integers(0,len(a),(c['bootstrap']['repetitions'],len(a)));ci=tuple(np.quantile(diff[ix].mean(1),[.025,.975]))
    paired.append(dict(stage=stage,condition=condition,metric=metric,pairs=len(a),old_mean=float(a[:,0].mean()),new_mean=float(a[:,1].mean()),new_minus_old=float(diff.mean()),ci_low=ci[0],ci_high=ci[1],old_over_new=ratio))
 csvwrite(out/'RUNS.csv',allrows);csvwrite(out/'SUMMARY.csv',summaries);csvwrite(out/'PAIRED.csv',paired)
 # Separate denominator plot, no silent elimination of budget or unavailable runs.
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.collections import PatchCollection
 from matplotlib.patches import Rectangle
 random=[r for r in allrows if r['stage']=='random'];conds=sorted(set(r['condition'] for r in random))
 if random:
  fig,ax=plt.subplots(1,3,figsize=(15,4))
  for method,mark in [('OLD','o'),('PROFILED','x')]:
   ss=[r for r in summaries if r['stage']=='random' and r['method']==method]
   for j,key in enumerate(['mean_wall','mean_area_upper','coverage_valid']):ax[j].plot(range(len(ss)),[r[key] for r in ss],marker=mark,label=method);ax[j].set_xticks(range(len(ss)),[r['condition'] for r in ss],rotation=35)
  for a,title in zip(ax,['All-in method cost (s)','Certified area upper bound (m²)','Empirical XY inclusion (100 seeds/condition)']):a.set_title(title);a.legend();a.grid(alpha=.2)
  fig.tight_layout();fig.savefig(out/'COST_SIZE_INCLUSION.png',dpi=150);plt.close(fig)
  fig,ax=plt.subplots(1,2,figsize=(12,4));d={r['case']:r for r in random if r['method']=='OLD'}
  pairs=[(d[r['case']],r) for r in random if r['method']=='PROFILED' and r['case'] in d]
  ax[0].scatter([a['wall_seconds'] for a,b in pairs],[b['wall_seconds'] for a,b in pairs],s=8,alpha=.5);ax[0].set_xlabel('OLD all-in seconds');ax[0].set_ylabel('PROFILED all-in seconds')
  names=[];counts=[]
  for method in ['OLD','PROFILED']:
   rr=[r for r in random if r['method']==method];names+= [method+' executed',method+' budget',method+' cert failure',method+' empty'];counts+=[len(rr),sum(r['termination'].endswith('BUDGET') for r in rr),sum(r['certificate']!='PASS' for r in rr),sum(r['empty'] for r in rr)]
  ax[1].bar(range(len(counts)),counts);ax[1].set_xticks(range(len(counts)),names,rotation=70);ax[1].set_title('Full planned denominator: 600 per method')
  fig.tight_layout();fig.savefig(out/'PAIRED_COST_DENOMINATORS.png',dpi=150);plt.close(fig)
 # Preselected deterministic examples: normal, near, mirror; no truth-based selection.
 for case in ['d00','d06','d12','legacy_s2_budget']:
  fig,axes=plt.subplots(1,2,figsize=(10,4))
  for ax,method in zip(axes,['OLD','PROFILED']):
   f=src/'deterministic'/(case+'_'+method+'.json.gz')
   if not f.exists():continue
   r=read(f);rects=[]
   for n in OC.retained(r['result']):
    b=OC.unpack(n['box']);rects.append(Rectangle((float(b[0][0]),float(b[1][0])),float(b[0][1]-b[0][0]),float(b[1][1]-b[1][0])))
   ax.add_collection(PatchCollection(rects,facecolor='orange',alpha=.7,edgecolor='none'));p=r['case']['evaluation']['truth'];ax.plot(float(p[0]),float(p[1]),'kx');ax.set_xlim(-6,6);ax.set_ylim(-6,6);ax.set_aspect('equal');ax.set_title(case+' '+method);ax.set_xlabel('X(m)');ax.set_ylabel('Y(m)')
  fig.tight_layout();fig.savefig(out/(case+'_REGIONS.png'),dpi=150);plt.close(fig)
 return dict(records=len(allrows),summaries=len(summaries),paired_rows=len(paired))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(analyze(a.results,a.out))
