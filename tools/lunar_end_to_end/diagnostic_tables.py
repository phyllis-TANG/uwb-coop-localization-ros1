"""Extra descriptive diagnostics from saved endpoints only."""
import json,csv
from collections import defaultdict
import numpy as np
from inputs import DOC,ART
from deliver import csvwrite
root=ART/'evaluation';records=[];wg=defaultdict(list);covs=[]
meta={r['id']:r for r in json.loads((DOC/'INPUT_MANIFEST.json').read_text())}
for task in json.loads((root/'RUN_PLAN.json').read_text()):
 r=json.loads((root/'results'/f"{task['key']}.json").read_text());o=json.loads((root/'observations'/f"{task['input_id']}.json").read_text());m=meta[task['input_id']];q=np.array(r['q']);xyz=np.dstack([q[:24].reshape(6,2,2),o['heights']]);a=np.array(o['anchors']);y=np.array(o['ranges']);ar=np.linalg.norm(xyz[:,:,None,:]-a,axis=3)-y[:,:8].reshape(6,2,4);bias=np.zeros(6)
 if len(q)>24:bias+=q[24]
 if len(q)>25:bias+=q[25]*(np.array(o['times_s'])-.5)
 pr=np.linalg.norm(xyz[:,1]-xyz[:,0],axis=1)+bias-y[:,8];keep=np.array(o['peer_mask']);diag=np.array(r['covariance_diagonal']);weak=np.array(r['weak_direction_scaled'])
 for c in range(2):
  records.append(dict(key=task['key'],method=task['method'],car=c+1,anchor_residual_rms_m=float(np.sqrt(np.mean(ar[:,c]**2))),peer_postfit_residual_rms_m=float(np.sqrt(np.mean(pr[keep]**2))) if task['method']!='M0' else None,peer_used=task['method']!='M0',state=r['state']))
  covs.append(dict(key=task['key'],window=m['window'],peer=m['peer'],motion=m['motion'],sensitivity=m['sensitivity'],method=task['method'],car=c+1,mean_conditional_xy_cov_trace_m2=float(diag[:24].reshape(6,2,2)[:,c].sum(1).mean()),weak_position_energy=float(np.sum(weak[:24]**2)),weak_bias_energy=float(np.sum(weak[24:]**2)),state=r['state'],interpretation='local model-conditional diagnostic, not protection level'))
  if task['group']=='core':wg[(m['window'],m['peer'],m['motion'],task['method'],c+1)].append(r)
rows=[]
for key,rs in wg.items():
 w,peer,motion,method,c=key
 for subset in ['all_finite','accepted']:
  selected=[r for r in rs if subset=='all_finite' or r['state']=='ACCEPTED'];rows.append(dict(window=w,peer=peer,motion=motion,method=method,car=c,subset=subset,total=10,accepted=sum(r['state']=='ACCEPTED' for r in rs),included=len(selected),mean_rmse_m=float(np.mean([r['metrics']['rmse_m'][c-1] for r in selected])) if selected else None))
csvwrite(DOC/'PER_WINDOW.csv',rows);csvwrite(DOC/'RESIDUALS.csv',records);csvwrite(DOC/'LOCAL_COVARIANCE.csv',covs)
