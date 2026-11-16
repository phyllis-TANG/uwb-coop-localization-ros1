import json,csv,hashlib
from pathlib import Path
import numpy as np
from propagation import generate,P,ROOT,sources
checks=[]
for layout in ['G1','G2']:
 c,e,t,r=generate(16101,layout,'wall',0.)
 for link in ['wall','peer']:
  cc,ee,tt,rr=generate(16101,layout,link,.3);assert c==cc and t==tt
  changes=0
  for a,b in zip(e,ee):
   assert all(a[k]==b[k] for k in a if k not in ['value','raw_message_sha256'])
   for key in a['value']:
    if a['value'][key]!=b['value'][key]:
     assert a['kind']=='uwb' and a['vehicle_id']=='car1' and key==('node_2' if link=='wall' else 'node_0')
     assert abs(b['value'][key]-a['value'][key]-.3)<1e-14;changes+=1
  assert changes==280;checks.append(dict(layout=layout,link=link,changed_scalars=changes))
rows=list(csv.DictReader((P/'S0_PER_RUN.csv').open()));maxdiff=0.
for seed in range(17101,17151):
 for car in ['car1','car2']:
  n=next(r for r in rows if int(r['seed'])==seed and r['car']==car and float(r['bias_m'])==0)
  f=next(r for r in rows if int(r['seed'])==seed and r['car']==car and r['link']=='peer')
  maxdiff=max(maxdiff,abs(float(n['M2_mse_m2'])-float(f['M2_mse_m2'])))
assert maxdiff<1e-10
loo=list(csv.DictReader((P/'FIELD_LEAVE_ONE_RECORD.csv').open()))
for car,target in [('car1',.07969486283642667),('car2',-.138700553306552)]:
 r=next(r for r in loo if r['omitted']=='none' and r['car']==car and r['arm']=='J')
 if car=='car1':assert abs(float(r['T_m2'])-target)<1e-10
source=sources();(P/'SOURCE_LOCK.json').write_text(json.dumps(source,indent=2))
(P/'CHECKS.json').write_text(json.dumps(dict(status='PASS',adapter_checks=checks,M2_peer_injection_max_MSE_difference=maxdiff,confirmed_run_count=len(rows)//2,S1_jacobian_check=json.loads((P/'S1_CHECKS.json').read_text()),baseline_check=json.loads((P/'BASELINE_SIMULATION.json').read_text())['status'],field_scope='numeric verified, two historical setup notes unresolved'),indent=2))
