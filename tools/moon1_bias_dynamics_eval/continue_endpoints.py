"""Exactly one frozen continuation of 11 failures and 11 deterministic controls."""
import argparse
from bridge import *
from engine import once,lock

def run(cases,out,freeze):
 assert git('rev-parse','HEAD')==freeze and not git('status','--porcelain')
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 cfg=read(DOC/'CONTINUATION.json');case=read(cases);names=case['failures']+case['controls'];assert len(names)==len(set(names))==22
 write(out/'FREEZE.json',dict(commit=freeze,settings=cfg,cases=case,source_sha256=sources(),argv=sys.argv,python=sys.version,case_sha256=filehash(cases)))
 obs=unpack(OLD/'results/measurements.json.gz');fits=unpack(OLD/'results/estimates.json.gz');rows=[]
 with lock(out/'RUN_LOCK'):
  for name in names:
   uid,method=name.split('-');old=fits[name];q=np.array(old['estimate']);new=once(obs[uid],method,q,cfg['settings'],out/name,'CONTINUE')
   delta=np.array(new['estimate'])-q if new['estimate'] is not None else np.full(len(q),np.nan)
   rows.append(dict(id=name,group='old_failure' if name in case['failures'] else 'accepted_control',old_status=old['status'],new_status=new['status'],old_cost=old['cost'],new_cost=new.get('cost'),cost_drop=old['cost']-new['cost'] if 'cost' in new else None,old_gradient_inf=old['gradient_inf'],new_gradient_inf=new.get('gradient_inf'),old_scaled_gradient_inf=old['scaled_gradient_inf'],new_scaled_gradient_inf=new.get('scaled_gradient_inf'),xy_component_change_m=float(max(abs(delta[:24]))),xy_vector_change_m=float(max(np.linalg.norm(delta[:24].reshape(-1,2),axis=1))),bias_change_m=float(delta[-1]) if method=='M2' else None,scipy_status=new.get('scipy_status'),nfev=new.get('nfev'),optimizer_calls=new['optimizer_calls']))
 csvwrite(out/'CONTINUATION.csv',rows);write(out/'RUN.json',dict(completed=22,optimizer_calls=22,formal_runs=0,source_sha256=sources()))
 print('Completed 22 continuations, no retries')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--cases',required=True);p.add_argument('--out',required=True);p.add_argument('--freeze',required=True);a=p.parse_args();run(a.cases,a.out,a.freeze)
