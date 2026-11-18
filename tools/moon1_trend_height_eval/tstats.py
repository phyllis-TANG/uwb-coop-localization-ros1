"""Seed-cluster summaries: windows are never additional independent replicates."""
from tcommon import *
from collections import defaultdict,Counter

FIELDS=['car1_mse_m2','car2_mse_m2','relative_mse_m2','car1_cov_trace_m2','car2_cov_trace_m2','peer_rms_m','peer_late_minus_early_m','b0_m','b1_m_per_s','total_condition','gradient_inf','cost']

def aggregate(rows,out,expected_windows):
 out=Path(out);groups=defaultdict(list)
 for row in rows:groups[(row['seed'],row['height_sigma_m'],row['condition'],row['method'])].append(row)
 seeds=[]
 for (seed,h,c,m),group in sorted(groups.items()):
  n=len(group);assert n==expected_windows
  complete=all(r['finite'] for r in group);accepted=all(r['accepted'] for r in group);paired=all(r['paired_accepted'] for r in group)
  sr=dict(seed=seed,height_sigma_m=h,condition=c,method=m,planned_windows=n,finite_windows=sum(r['finite'] for r in group),accepted_windows=sum(r['accepted'] for r in group),complete_finite=complete,all_accepted=accepted,all_paired_accepted=paired)
  for k in FIELDS+['car1_benefit_m2','car2_benefit_m2']:
   values=[r[k] for r in group];sr[k]=float(np.mean(values)) if all(v is not None for v in values) else None
  for cidx in [1,2]:sr[f'car{cidx}_rmse_m']=float(np.sqrt(sr[f'car{cidx}_mse_m2'])) if sr[f'car{cidx}_mse_m2'] is not None else None
  sr['relative_rmse_m']=float(np.sqrt(sr['relative_mse_m2'])) if sr['relative_mse_m2'] is not None else None
  seeds.append(sr)
 csvwrite(out/'SEED_METRICS.csv',seeds)
 summaries=[];den=[]
 for h,c,m in sorted({(r['height_sigma_m'],r['condition'],r['method']) for r in rows}):
  selected=[r for r in rows if (r['height_sigma_m'],r['condition'],r['method'])==(h,c,m)]
  sr=[r for r in seeds if (r['height_sigma_m'],r['condition'],r['method'])==(h,c,m)]
  den.append(dict(height_sigma_m=h,condition=c,method=m,planned=len(selected),finite=sum(r['finite'] for r in selected),accepted=sum(r['accepted'] for r in selected),failed=sum(not r['accepted'] for r in selected),unavailable=sum(not r['finite'] for r in selected),planned_seed_clusters=len(sr),complete_finite_clusters=sum(r['complete_finite'] for r in sr),all_accepted_clusters=sum(r['all_accepted'] for r in sr)))
  for subset,key in [('all_finite','complete_finite'),('all_accepted','all_accepted'),('paired_with_M0_accepted','all_paired_accepted')]:
   use=[r for r in sr if r[key]];s=dict(height_sigma_m=h,condition=c,method=m,subset=subset,planned_seed_clusters=len(sr),used_seed_clusters=len(use))
   for metric in FIELDS+['car1_rmse_m','car2_rmse_m','relative_rmse_m','car1_benefit_m2','car2_benefit_m2']:
    v=[r[metric] for r in use if r[metric] is not None];s[metric+'_mean']=float(np.mean(v)) if v else None
   summaries.append(s)
 csvwrite(out/'DENOMINATORS.csv',den);csvwrite(out/'SUMMARY.csv',summaries)
 idx={(r['seed'],r['height_sigma_m'],r['condition'],r['method']):r for r in seeds};comparisons=[]
 for r in seeds:
  if r['method']=='M3':
   other=idx[(r['seed'],r['height_sigma_m'],r['condition'],'M2')]
   comparisons.append(compare(r,other,'M3_minus_M2',r['method']))
  if r['height_sigma_m']>0:
   other=idx[(r['seed'],0.,r['condition'],r['method'])]
   comparisons.append(compare(r,other,'height_minus_zero',r['method']))
 csvwrite(out/'PAIRED_SEED_COMPARISONS.csv',comparisons);cs=[]
 for contrast,h,c,m in sorted({(r['contrast'],r['height_sigma_m'],r['condition'],r['method']) for r in comparisons}):
  selected=[r for r in comparisons if (r['contrast'],r['height_sigma_m'],r['condition'],r['method'])==(contrast,h,c,m)]
  for subset,key in [('all_finite','both_complete_finite'),('both_accepted','both_all_accepted')]:
   use=[r for r in selected if r[key]];s=dict(contrast=contrast,height_sigma_m=h,condition=c,method=m,subset=subset,planned_seed_clusters=len(selected),used_seed_clusters=len(use))
   for metric in ['car1_mse_delta_m2','car2_mse_delta_m2','relative_mse_delta_m2','car1_cov_trace_delta_m2','car2_cov_trace_delta_m2']:
    v=[r[metric] for r in use if r[metric] is not None]
    for stat,fun in [('mean',np.mean),('median',np.median),('min',np.min),('max',np.max)]:s[metric+'_'+stat]=float(fun(v)) if v else None
   cs.append(s)
 csvwrite(out/'COMPARISON_SUMMARY.csv',cs)
 return seeds,comparisons,den

def compare(a,b,label,method):
 d=dict(seed=a['seed'],height_sigma_m=a['height_sigma_m'],condition=a['condition'],method=method,contrast=label,both_complete_finite=a['complete_finite'] and b['complete_finite'],both_all_accepted=a['all_accepted'] and b['all_accepted'])
 for prefix in ['car1','car2','relative']:
  k=prefix+'_mse_m2';d[prefix+'_mse_delta_m2']=a[k]-b[k] if a[k] is not None and b[k] is not None else None
 for c in [1,2]:
  k=f'car{c}_cov_trace_m2';d[f'car{c}_cov_trace_delta_m2']=a[k]-b[k] if a[k] is not None and b[k] is not None else None
 return d
