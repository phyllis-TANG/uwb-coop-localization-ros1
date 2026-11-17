"""Independent explicit-loop readback. Does not import model or scipy optimizer."""
import argparse,hashlib,json,tarfile,tempfile
from pathlib import Path
import numpy as np

def residual(o,method,q):
 x=np.array(q[:24]).reshape(6,2,2);h=o['heights'];r=[];range_r=[]
 for t in range(6):
  for c in range(2):
   for k,a in enumerate(o['anchors']):
    pred=sum((x[t,c,d]-a[d])**2 for d in range(2))+(h[t][c]-a[2])**2
    v=(np.sqrt(pred)-o['ranges'][t][4*c+k])/o['sigma_range'];r.append(v);range_r.append(v)
  if method!='M0' and o['peer_mask'][t]:
   v=np.sqrt(sum((x[t,1,d]-x[t,0,d])**2 for d in range(2))+(h[t][1]-h[t][0])**2)
   if len(q)>24:v+=q[24]
   if len(q)>25:v+=q[25]*(o['times_s'][t]-.5)
   v=(v-o['ranges'][t][8])/o['sigma_range'];r.append(v);range_r.append(v)
 for t in range(5):
  for c in range(2):
   for d in range(2):r.append((x[t+1,c,d]-x[t,c,d]-o['increments'][t][c][d])/o['sigma_motion'])
 for c in range(2):
  for d in range(2):r.append((x[0,c,d]-o['prior'][c][d])/o['sigma_prior'])
 return np.array(r),np.array(range_r)
def jacobian(o,method,q):
 # Independently assemble from central differences; absolute step selected for 0..260 m states.
 q=np.array(q);j=[]
 for k in range(len(q)):
  step=1e-4;v=np.zeros(len(q));v[k]=step;j.append((residual(o,method,q+v)[0]-residual(o,method,q-v)[0])/(2*step))
 return np.array(j).T

def metrics(o,ref,method,q):
 xyz=np.dstack([np.array(q[:24]).reshape(6,2,2),np.array(o['heights'])]);err=np.linalg.norm(xyz-np.array(ref['xyz']),axis=2);r,rr=residual(o,method,q)
 return dict(rmse_m=np.sqrt((err**2).mean(0)).tolist(),p50_m=np.quantile(err,.5,axis=0).tolist(),p95_m=np.quantile(err,.95,axis=0).tolist(),max_m=err.max(0).tolist(),error_m=err.tolist(),range_residual_rms_m=float(np.sqrt(np.mean(rr**2))*o['sigma_range']),cost=float(r@r/2),bias0_m=float(q[24]) if len(q)>24 else None,bias_slope_m_s=float(q[25]) if len(q)>25 else None)
def verify(root):
 manifest=json.loads((root/'MANIFEST.json').read_text());bad=[]
 for name,h in manifest.items():
  p=root/name
  if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:bad.append(name)
 if bad:raise AssertionError(f'Hash failures {bad}')
 identities=json.loads((root/'INPUT_MANIFEST.json').read_text())
 for ident in identities:
  for folder,field in [('observations','observation_digest'),('references','reference_digest')]:
   value=json.loads((root/folder/(ident['id']+'.json')).read_text());h=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
   if h!=ident[field]:raise AssertionError('Frozen input identity mismatch')
 plan=json.loads((root/'RUN_PLAN.json').read_text());progress=json.loads((root/'PROGRESS.json').read_text());stats={s:0 for s in ['ACCEPTED','NOT_STATIONARY','BUDGET_EXHAUSTED','RANK_DEFICIENT','NONFINITE','FAILED','INTERRUPTED','UNEXECUTED']};maxcost=0.;maxgrad=0.;rows=[];calls=0
 for task in plan:
  key=task['key'];p=root/'results'/f'{key}.json';attempt=root/'attempts'/f'{key}.json'
  if not p.exists():
   stats['INTERRUPTED' if attempt.exists() else 'UNEXECUTED']+=1
   ep=root/'endpoints'/f'{key}.json'
   if ep.exists():
    er=json.loads(ep.read_text());calls+=er.get('optimizer_calls_started',len(er.get('stages',[])))
   continue
  result=json.loads(p.read_text());state=result['state'];stats[state]+=1;calls+=result.get('optimizer_calls_started',len(result.get('stages',[])))
  if 'q' not in result:continue
  o=json.loads((root/'observations'/f"{task['input_id']}.json").read_text());ref=json.loads((root/'references'/f"{task['input_id']}.json").read_text());q=np.array(result['q']);m=metrics(o,ref,task['method'],q);maxcost=max(maxcost,abs(m['cost']-result['cost']))
  for name in ['rmse_m','p95_m','max_m']:
   if not np.allclose(m[name],result['metrics'][name],rtol=1e-11,atol=1e-11):raise AssertionError((key,name))
  r,_=residual(o,task['method'],q);j=jacobian(o,task['method'],q);grad=float(np.max(abs(j.T@r)));sc=np.r_[np.ones(24),np.full(len(q)-24,.1)];sv=np.linalg.svd(j*sc,compute_uv=False);rank=int(sum(sv>sv[0]*1e-8));maxgrad=max(maxgrad,abs(grad-result['gradient_inf']))
  # Near the acceptance boundary use a stated difference tolerance, never silently reclassify.
  if rank!=result['rank'] or (state=='ACCEPTED' and (grad>1.01e-5 or not np.isfinite(q).all())):raise AssertionError((key,grad,state))
  last=result['stages'][-1];recomputed='BUDGET_EXHAUSTED' if last['status']==0 else 'NOT_STATIONARY' if not last['success'] or grad>1e-5 else 'RANK_DEFICIENT' if rank!=len(q) else 'ACCEPTED'
  if recomputed!=state and abs(grad-1e-5)>1e-7:raise AssertionError((key,'state',recomputed,state))
  if abs(m['cost']-result['cost'])>1e-8:raise AssertionError((key,'cost'))
  rows.append(dict(key=key,**m))
 if stats!=progress['statuses'] or calls!=progress['optimizer_calls']:raise AssertionError('Ledger counts differ')
 return dict(passed=True,hashes_checked=len(manifest),planned=len(plan),states=stats,optimizer_calls=calls,metrics_recomputed=len(rows),max_cost_difference=maxcost,max_gradient_difference=maxgrad,checker='explicit residual loops and finite-difference Jacobian; no optimizer import/call')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('archive');ap.add_argument('--output');args=ap.parse_args()
 with tempfile.TemporaryDirectory() as tmp:
  with tarfile.open(args.archive) as tar:
   for member in tar.getmembers():
    if not member.isfile() or member.name.startswith('/') or '..' in Path(member.name).parts:raise ValueError('Unsafe archive member')
   tar.extractall(tmp)
  result=verify(Path(tmp))
 s=json.dumps(result,indent=2);print(s)
 if args.output:Path(args.output).write_text(s+'\n')
if __name__=='__main__':main()
