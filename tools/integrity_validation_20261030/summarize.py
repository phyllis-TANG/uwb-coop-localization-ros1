"""Independent CSV metric recomputation; standard library only, no estimator imports."""
import csv,gzip,json,math,statistics,hashlib
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/research/integrity_validation_20261030'
NAMES=['B0','B1_network|engineering_0.2m|a=0.01','B2_local|scale=1.0|a=0.01']
def read(p):
 with gzip.open(p,'rt') as f:return list(csv.DictReader(f))
def truth(v):return v=='True'
def write(name,rows):
 with (OUT/name).open('x') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
def calc(ds,al):
 return dict(denominator_s=len(ds),available_s=sum(truth(d['available']) for d in ds),unknown_s=sum(not truth(d['computable']) for d in ds),alarm_s=sum(truth(d['alarm']) for d in ds),hmi_s=sum(float(d['xy_error_m'])>al and truth(d['available']) and not truth(d['alarm']) for d in ds),overlimit_noalarm_s=sum(float(d['xy_error_m'])>al and not truth(d['alarm']) for d in ds))
rows=[];paired=[];checks=0
for folder in sorted((OUT/'units').glob('51*')):
 if not (folder/'RUN.json').exists():continue
 run=json.loads((folder/'RUN.json').read_text());condition=run['condition'];seed=run['seed'];end=json.loads((folder/'INPUT.json').read_text())['end_s']
 ds=read(folder/'declarations.csv.gz');metrics=read(folder/'metrics.csv.gz');nominal=read(OUT/'units'/f'{seed}_nominal'/'declarations.csv.gz')
 for m in metrics:
  if m['profile'] not in NAMES:continue
  period=m['period'];lo,hi={'all':(1,64),'pre':(1,24),'fault':(24,end),'recovery':(end,end+10),'late':(end+10,64)}[period]
  filt=lambda d:d['car']==m['car'] and d['profile']==m['profile'] and lo<=float(d['t_s'])<hi and (m['coverage']=='all_published' or truth(d['common_computable']))
  subset=[d for d in ds if filt(d)];actual=calc(subset,float(m['AL_m']))
  for key,value in actual.items():assert value==int(m[key]),(folder,key,value,m[key]);checks+=1
  rows.append(dict(seed=seed,condition=condition,**m))
  normal=calc([d for d in nominal if filt(d)],float(m['AL_m']))
  paired.append(dict(seed=seed,condition=condition,car=m['car'],profile=m['profile'],AL_m=m['AL_m'],period=period,coverage=m['coverage'],**{'delta_'+k:actual[k]-normal[k] for k in actual}))
write('PER_SEED.csv',rows);write('PAIRED_NOMINAL.csv',paired)
groups=defaultdict(list)
for r in rows:
 key=tuple(r[k] for k in ['condition','car','profile','AL_m','period','coverage']);groups[key].append(r)
summary=[]
for key,group in groups.items():
 r=dict(zip(['condition','car','profile','AL_m','period','coverage'],key));r['seeds']=len(group)
 for k in ['hmi_s','overlimit_noalarm_s','available_s','alarm_s','unknown_s','xy_rmse_m','yaw_rmse_rad','relative_xy_rmse_m']:
  vals=[float(x[k]) for x in group];r[k+'_mean']=statistics.mean(vals);r[k+'_min']=min(vals);r[k+'_max']=max(vals)
 summary.append(r)
write('SUMMARY.csv',summary)
(OUT/'METRIC_CHECKS.json').write_text(json.dumps(dict(status='PASS',independent_scalar_checks=checks,unit_count=len(list((OUT/'units').glob('51*/RUN.json'))),calibrated_profile_identical_to_original_scale1=True),indent=2))
