"""Optimizer-free readback, portable archive, propagation comparisons and seed-paired summaries."""
import argparse,collections,csv,math
from model import *
def writecsv(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with p.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(clean(rows))
def usable(r):return bool(r.get('usable_estimate') and r.get('estimate') is not None and np.isfinite(r['estimate']).all())
def verify(u,m,r):
 if not usable(r):return 0
 x=np.array(r['estimate']);rr,j=M.objective(u,m,x)
 assert np.allclose(rr@rr/2,r['cost'],atol=2e-9,rtol=1e-10)
 assert np.allclose(max(abs(j.T@rr)),r['gradient_inf'],atol=2e-8,rtol=1e-7)
 if 'residual' in r:assert np.allclose(rr,r['residual'],atol=1e-10,rtol=0)
 e=x[:24].reshape(6,2,2)-u['truth'];assert np.allclose(np.mean(np.sum(e*e,axis=2),axis=0),r['position_mse'],atol=1e-10,rtol=0)
 return 1

def pairs_raw(out):
 c=config();src=source_units();meta=read(out/'RUN.json');assert meta['config_sha256']==digest(c) and meta['plan']==plans(c)
 yield dict(type='META',value=meta)
 for q in meta['plan']:
  old=src[q['source']];u=read(out/'inputs'/f"{q['id']}.json.gz");assert u==clean(perturb(old['input'],q['delta']))
  for m in c['methods']:
   stages=[read(out/'stages'/q['id']/f'{m}-{s}.json.gz') for s in ['P0','P1']]
   for st in stages:assert st['input_sha256']==digest(u)
   yield dict(type='PAIR',value=dict(study='new',q=q,method=m,base_input=old['input'],target_input=u,base=old['results'][m]['P1'],target=stages[1]['result'],P0=stages[0]['result']))
 for g,offset in [('good',0),('weak',12),('near',24)]:
  for sig,idx in [(.5,6),(.05,9)]:
   for seed in range(281117001,281117101):
    b=src[f'p{offset+idx:02}-s{seed}'];t=src[f'p{offset+idx+1:02}-s{seed}'];delta=np.array(t['input']['obs']['prior_center'])-b['input']['obs']['prior_center'];q=dict(id=f'reuse-{g}-{sig}-s{seed}',geometry=g,sigma=sig,axis='survey_vector',amplitude=float(np.linalg.norm(delta)),delta=delta.tolist(),seed=seed)
    for m in c['methods']:yield dict(type='PAIR',value=dict(study='reuse',q=q,method=m,base_input=b['input'],target_input=t['input'],base=b['results'][m]['P1'],target=t['results'][m]['P1']))
def streams(p):
 with gzip.open(p,'rt') as f:
  for l in f:yield json.loads(l)
def rows_for(v):
 q=v['q'];m=v['method'];b=v['base'];t=v['target'];u=v['base_input'];ut=v['target_input'];delta=np.array(q['delta']);out=[]
 # ONLY center may differ; prior bookkeeping is not objective input.
 ob=copy.deepcopy(u['obs']);ot=copy.deepcopy(ut['obs']);ob.pop('prior_center');ot.pop('prior_center');assert ob==ot
 common=dict(study=v['study'],id=q['id'],seed=q['seed'],geometry=q['geometry'],sigma=q['sigma'],axis=q['axis'],amplitude=q['amplitude'],method=m,base_accepted=b['accepted'],target_accepted=t['accepted'],base_category=b['category'],target_category=t['category'],base_gradient=b['gradient_inf'],target_gradient=t['gradient_inf'],usable_pair=usable(b) and usable(t))
 if not common['usable_pair']:
  return [dict(**common,car=car,view=view,status='UNAVAILABLE_PAIR') for car in [1,2] for view in ['endpoint_GN','endpoint_exact','truth_GN']]
 x=np.array(b['estimate']);y=np.array(t['estimate']);dx=y-x;actual=dx[:24].reshape(6,2,2);err0=x[:24].reshape(6,2,2)-u['truth'];err1=y[:24].reshape(6,2,2)-ut['truth']
 for name,point,exact in [('endpoint_GN',x,False),('endpoint_exact',x,True),('truth_GN',M.reference(u,m),False)]:
  z=transfer(u,m,point,exact);T=z['T']
  for car in range(2):
   a=actual[:,car];norm=np.linalg.norm(a);e=err1[:,car];e0=err0[:,car];r=dict(**common,car=car+1,view=name,status=z['status'],hessian_min=z['min_eigenvalue'],hessian_condition=z['condition_number'],actual_shift_rms=float(norm/np.sqrt(6)),base_mse=float(np.mean(np.sum(e0*e0,axis=1))),target_mse=float(np.mean(np.sum(e*e,axis=1))),base_mean_x=float(e0[:,0].mean()),base_mean_y=float(e0[:,1].mean()),target_mean_x=float(e[:,0].mean()),target_mean_y=float(e[:,1].mean()),actual_shift_x=float(a[:,0].mean()),actual_shift_y=float(a[:,1].mean()))
   if T is not None:
    pred=(T@delta)[:24].reshape(6,2,2)[:,car];er=pred-a;rel=np.linalg.norm(er)/max(norm,config()['analysis']['relative_denominator_floor_m']*np.sqrt(6));den=np.linalg.norm(pred)*norm;angle=float(np.degrees(np.arccos(np.clip(np.sum(pred*a)/den,-1,1)))) if den>1e-20 else None
    block=np.vstack([T[4*t+2*car:4*t+2*car+2] for t in range(6)]);ball=.05*np.linalg.svd(block,compute_uv=False)[0]/np.sqrt(6)
    r.update(predicted_shift_rms=float(np.linalg.norm(pred)/np.sqrt(6)),prediction_error_rms=float(np.linalg.norm(er)/np.sqrt(6)),relative_error=float(rel),angle_deg=angle,predicted_shift_x=float(pred[:,0].mean()),predicted_shift_y=float(pred[:,1].mean()),assumed_ball_rms_bound_m=float(ball),agreement=bool(rel<=.1 and angle is not None and angle<=5))
   out.append(r)
 return out

def analyze(iterator,dest,archive=False):
 dest.mkdir(parents=True,exist_ok=False);rows=[];failures=[];counts=collections.Counter();pack=gzip.open(dest/'EVIDENCE.jsonl.gz','wt') if archive else None;met=None
 try:
  for entry in iterator:
   if pack:pack.write(canonical(entry).decode()+'\n')
   if entry['type']=='META':met=entry['value'];continue
   v=entry['value'];m=v['method'];study=v['study'];counts[study+'_method_pairs']+=1
   for label in ['base','target']:
    counts[study+'_verified_estimates']+=verify(v[label+'_input'],m,v[label]);counts[study+'_'+label+'_accepted']+=int(v[label]['accepted']);counts[study+'_'+label+'_unavailable']+=int(not usable(v[label]))
   if study=='new':
    verify(v['target_input'],m,v['P0'])
    for s in ['P0','target']:
     rr=v[s];counts['new_stages']+=1;counts['new_optimizer_calls']+=int(rr['execution']!='SKIPPED');counts['new_warning_count']+=len(rr['warnings']);counts['new_budget_stages']+=int(rr['hit_budget'])
   if not v['target']['accepted']:failures.append(dict(study=study,id=v['q']['id'],method=m,category=v['target']['category'],gradient=v['target']['gradient_inf'],usable=usable(v['target'])))
   rows.extend(rows_for(v))
 finally:
  if pack:pack.close()
 assert counts['new_method_pairs']==960 and counts['reuse_method_pairs']==1200
 writecsv(dest/'PER_PAIR.csv',rows);writecsv(dest/'FAILURES.csv',failures);groups=collections.defaultdict(list)
 for r in rows:groups[tuple(r[k] for k in ['study','geometry','sigma','axis','amplitude','method','car','view'])].append(r)
 summaries=[];rng=np.random.default_rng(config()['analysis']['bootstrap_seed'])
 for key,rs in sorted(groups.items(),key=lambda x:str(x[0])):
  z=dict(zip(['study','geometry','sigma','axis','amplitude','method','car','view'],key));z.update(planned=len(rs),usable=sum(r['usable_pair'] for r in rs),accepted_pairs=sum(r['base_accepted'] and r['target_accepted'] for r in rs),propagation_available=sum(r['status']=='AVAILABLE' for r in rs))
  for k in ['base_mse','target_mse','actual_shift_rms','prediction_error_rms','relative_error','angle_deg','base_mean_x','base_mean_y','target_mean_x','target_mean_y','actual_shift_x','actual_shift_y','predicted_shift_x','predicted_shift_y']:
   a=np.array([r[k] for r in rs if r.get(k) is not None]);z[k+'_mean']=float(a.mean()) if len(a) else None
   if k in ['relative_error','angle_deg']:z[k+'_p95']=float(np.quantile(a,.95)) if len(a) else None
  av=[r for r in rs if r.get('agreement') is not None];z['agreement_n']=sum(r['agreement'] for r in av);z['agreement_denominator']=len(rs)
  diff=np.array([r['target_mse']-r['base_mse'] for r in rs if 'target_mse' in r]);z['mse_change_mean']=float(diff.mean()) if len(diff) else None
  if len(diff)>=.9*len(rs) and len(diff)>=10:
   boot=diff[rng.integers(0,len(diff),(2000,len(diff)))].mean(axis=1);z['mse_change_ci_low'],z['mse_change_ci_high']=np.quantile(boot,[.025,.975]).tolist()
  summaries.append(z)
 writecsv(dest/'SUMMARY.csv',summaries);save(dest/'COUNTS.json',dict(counts));save(dest/'READBACK.json',dict(status='PASS',optimizer_calls=0,checks=['input pairing (only prior center differs)','all available cost/gradient/MSE reconstructed','new P0/P1 and old endpoints','full 960+1200 pair denominators'],freeze=met['freeze']))
 return dict(counts)
if __name__=='__main__':
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--run',type=Path);g.add_argument('--archive',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(analyze(pairs_raw(a.run) if a.run else streams(a.archive),a.out,archive=bool(a.run)))
