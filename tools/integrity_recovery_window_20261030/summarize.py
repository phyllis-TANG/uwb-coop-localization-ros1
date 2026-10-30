"""Independent saved-declaration metrics and paired recovery cost; no online imports."""
import csv,gzip,json,math,hashlib,subprocess
from pathlib import Path
P=Path(__file__).resolve().parents[2]/'docs/research/integrity_recovery_window_20261030'
profiles=['B0','B1_network|engineering_0.2m|a=0.01','B2_local|scale=1.0|a=0.01']
def read(path):
 with gzip.open(path,'rt') as f:return list(csv.DictReader(f))
def write(name,rows):
 with (P/name).open('x') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
def yes(v):return v=='True'
metrics=[];source=[];checks=0
for condition in ['nominal','wall_long']:
 ds=read(P/condition/'declarations.csv.gz');saved=read(P/condition/'metrics.csv.gz')
 for car in ['car1','car2']:
  for profile in profiles:
   for al in [.05,.1,.2]:
    for period,(lo,hi) in {'all':(1,90),'pre':(1,24),'fault':(24,52),'post_fault_active':(52,73),'post_exit':(73,90),'post_fault_total':(52,90)}.items():
     for coverage in ['all_published','common_computable']:
      rows=[r for r in ds if r['car']==car and r['profile']==profile and lo<=float(r['t_s'])<hi and (coverage=='all_published' or yes(r['common_computable']))]
      values=dict(denominator_s=len(rows),hmi_s=sum(float(r['xy_error_m'])>al and yes(r['available']) and not yes(r['alarm']) for r in rows),overlimit_noalarm_s=sum(float(r['xy_error_m'])>al and not yes(r['alarm']) for r in rows),alarm_s=sum(yes(r['alarm']) for r in rows),available_s=sum(yes(r['available']) for r in rows),unknown_s=sum(not yes(r['computable']) for r in rows))
      if period!='post_fault_total':
       old=next(r for r in saved if r['car']==car and r['profile']==profile and float(r['AL_m'])==al and r['period']==period and r['coverage']==coverage)
       for k,v in values.items():assert v==int(old[k]);checks+=1
      values['alarm_while_within_AL_s']=sum(yes(r['alarm']) and float(r['xy_error_m'])<=al for r in rows)
      metrics.append(dict(condition=condition,car=car,profile=profile,AL_m=al,period=period,coverage=coverage,**values))
 for line in gzip.open(P/condition/'monitor.jsonl.gz','rt'):
  r=json.loads(line)
  for group,tests in r['monitor']['ss'].items():
   for i,s in enumerate(tests):
    c=s.get('covariance');d=s.get('delta_xy_m');cross=s.get('cross_covariance')
    source.append(dict(condition=condition,t_s=r['state_time_s'],car=f'car{i+1}',source_group=group,computable=s['computable'],delta_x_m=d[0] if d else None,delta_y_m=d[1] if d else None,separation_m=s.get('separation_m'),cov_xx=c[0][0] if c else None,cov_xy=c[0][1] if c else None,cov_yy=c[1][1] if c else None,cross_covariance_json=json.dumps(cross),full_covariance_json=json.dumps(s.get('full_covariance')),subset_covariance_json=json.dumps(s.get('subset_covariance')),statistic=s['statistic'],threshold=-2*math.log(.01/3),source_test_exceeds=bool(s['computable'] and s['statistic']>-2*math.log(.01/3))))
write('METRICS.csv',metrics);write('SOURCE_GROUPS.csv',source)
paired=[]
for r in metrics:
 if r['condition']!='wall_long':continue
 n=next(n for n in metrics if n['condition']=='nominal' and all(n[k]==r[k] for k in ['car','profile','AL_m','period','coverage']))
 paired.append({k:r[k] for k in ['car','profile','AL_m','period','coverage']}|{'delta_'+k:r[k]-n[k] for k in ['hmi_s','overlimit_noalarm_s','alarm_s','available_s','unknown_s','alarm_while_within_AL_s']})
write('PAIRED.csv',paired)
(P/'METRIC_CHECK.json').write_text(json.dumps(dict(status='PASS',independent_scalar_checks=checks),indent=2))
for r in metrics:
 if r['condition']=='wall_long' and r['profile']==profiles[-1] and r['coverage']=='all_published' and r['period'] in ['post_fault_total','post_exit']:print(r)
