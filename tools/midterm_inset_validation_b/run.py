"""PR116 recovery integration; each P0/P1 at most once, uncertain attempts stop."""
import argparse,fcntl,os,subprocess,time
from common import *
V=module('frozen_validation_core','tools/midterm_simulation_validation/core.py')
def generate(c,q,seed):
 u=V.generate(c['frozen_model'],q,seed);u['obs']['prior_center']=(np.array(u['truth'])[0].ravel()+np.array([0,q['delta_m'],0,0])).tolist();u['obs']['prior_sigma']=q['prior_sigma'];u['input_sha256']=digest(u['obs']);return u

def execute_stage(out,c,item,u,stage,previous=None,solver=None,hook=lambda phase:None):
 ident=stage_identity(c,item,u,stage,previous)
 def call():
  calls=[0]
  def counted(*args,**kw):
   calls[0]+=1;return (V.least_squares if solver is None else solver)(*args,**kw)
  result=V.solve_stage(c['frozen_model'],u,'B2',stage,previous,solver=counted);result['optimizer_invocations']=calls[0];return result
 record=REC.execute(out/'ledger',ident,call,hook=hook)
 payload=record['payload']
 if payload['execution']=='RETURNED':result=payload['value']
 else:
  result=V.blank(stage);result.update(category='WRAPPER_EXCEPTION',exception=payload,optimizer_invocations=None)
 return result,record

def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
def run(out,mode,freeze=None,resume=False):
 c=config();assert versions()==c['versions'];assert all(os.environ.get(k)=='1' for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'])
 if mode=='formal':
  assert git('rev-parse','HEAD')==freeze and not git('status','--porcelain','--untracked-files=no')
  for p,h in read(DOC/'FREEZE_MANIFEST.json')['files'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
  assert read(DOC/'DEVELOPMENT_CHECKS.json')['status']=='PASS'
 if not resume:out.mkdir(parents=True,exist_ok=False)
 with (out/'LOCK').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  meta=dict(mode=mode,freeze=freeze,execution_root=str(ROOT),config=c,config_sha256=digest(c),sources=hashes(),versions=versions(),plan=tasks(c,mode))
  if resume:assert read(out/'RUN.json')==meta
  else:save(out/'RUN.json',meta)
  def event(name,**kw):
   with (out/'EVENTS.jsonl').open('ab') as f:f.write(canonical(dict(event=name,time=time.time(),**kw))+b'\n');f.flush();os.fsync(f.fileno())
  event('RESUME' if resume else 'START');newcalls=0;units=0
  try:
   for item in meta['plan']:
    ip=out/'inputs'/f"{item['id']}.json.gz"
    if ip.exists():u=read(ip);assert u==generate(c,item['condition'],item['seed'])
    else:u=generate(c,item['condition'],item['seed']);save(ip,u)
    # Direct linear gate occurs BEFORE any nonlinear stage for this input.
    lp=out/'linear'/f"{item['id']}.json.gz"
    if lp.exists():lin=read(lp);assert lin['input_sha256']==digest(u)
    else:lin=dict(input_sha256=digest(u),result=affine(u,c));save(lp,lin)
    if not lin['result']['accepted']:raise ArithmeticError('Direct linear gate unavailable')
    previous=None
    for stage in ['P0','P1']:
     result,receipt=execute_stage(out,c,item,u,stage,previous);previous=result
     if receipt['mode']=='EXECUTED':newcalls+=result['optimizer_invocations'] or 0
     event('STAGE_RETURN',unit=item['id'],stage=stage,mode=receipt['mode'],attempt=receipt['attempt_id'])
    units+=1
    if units%100==0:print('units',units,'new optimizer calls',newcalls,flush=True)
   event('COMPLETE',units=units,new_optimizer_calls=newcalls)
  except BaseException as e:event('STOPPED',reason=repr(e),units=units,new_optimizer_calls=newcalls);raise
 return dict(units=units,new_optimizer_calls=newcalls)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['development','formal'],required=True);p.add_argument('--freeze');p.add_argument('--resume',action='store_true');a=p.parse_args();print(run(a.out,a.mode,a.freeze,a.resume))
