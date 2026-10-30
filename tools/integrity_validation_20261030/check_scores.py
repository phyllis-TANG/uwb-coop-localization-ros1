"""Independent 2x2 covariance score and threshold readback; stdlib only."""
import json,gzip,math
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'docs/research/integrity_validation_20261030';count=0
for f in sorted((p/'units').glob('*/scores.json.gz')):
 rows=json.load(gzip.open(f,'rt'))
 for row in rows:
  m=row['monitor']
  for tests in m['ss'].values():
   for s in tests:
    if not s['computable']:continue
    c=s['covariance'];x,y=s['delta_xy_m'];a,b=c[0];d=c[1][1];q=(d*x*x-2*b*x*y+a*y*y)/(a*d-b*b)
    assert math.isclose(q,s['statistic'],rel_tol=1e-8,abs_tol=1e-8);count+=1
  for name,pair in m['declarations'].items():
   local=[]
   for i,car in enumerate(['car1','car2']):
    if name=='B0':ready=m['b0']['state'] in ['accepted','rejected'];alarm=ready and m['b0']['engineering_q']>3
    elif name.startswith('B1'):
     _,noise,a=name.split('|');s=m['b1'][noise][car];ready=s['computable'];alarm=ready and s['statistic']>-2*math.log(float(a.split('=')[1]))
    else:
     _,sc,a=name.split('|');scale=float(sc.split('=')[1]);alpha=float(a.split('=')[1]);ts=[v[i] for v in m['ss'].values()];ready=all(s['computable'] for s in ts);alarm=any(s['computable'] and s['statistic']/scale**2>-2*math.log(alpha/3) for s in ts)
    ready=ready and row['accepted'];local.append(dict(computable=ready,alarm=bool(ready and alarm),available=bool(ready and not alarm)))
   if '_network|' in name:
    ready=all(x['computable'] for x in local);alarm=any(x['alarm'] for x in local);local=[dict(computable=ready,alarm=alarm,available=ready and not alarm)]*2
   for got,want in zip(pair,local):
    for k,v in want.items():assert got[k]==v,(f,name,k);count+=1
(p/'SCORE_CHECKS.json').write_text(json.dumps(dict(status='PASS',scalar_checks=count,files=len(list((p/'units').glob('*/scores.json.gz')))),indent=2))
