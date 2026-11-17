"""Finite paired exploration; stage-durable exclusive results; existing failures are completed."""
import argparse,fcntl,os,platform,subprocess,time
from pathlib import Path
import numpy as np,scipy
from model import *
V=load_module('prior_frozen_core','tools/midterm_simulation_validation/core.py')
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
def hashes():
 paths=list((ROOT/'tools/midterm_prior_propagation_b').glob('*.py'))+[ROOT/x for x in ['tools/midterm_prior_mechanism_b/math_model.py','tools/midterm_simulation_validation/core.py','tools/midterm_simulation_s2/prototype.py','tools/midterm_simulation_phase1/identifiability.py']]
 paths+=list((ROOT/'docs/research/midterm_prior_mechanism_b/results').glob('EVIDENCE-*.jsonl.gz'))
 return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
def event(out,kind,**kw):
 with (out/'EVENTS.jsonl').open('ab') as f:f.write(canonical(dict(event=kind,time=time.time(),**kw))+b'\n');f.flush();os.fsync(f.fileno())
def run(out,freeze,resume=False):
 c=config();head=git('rev-parse','HEAD');assert head==freeze and not git('status','--porcelain','--untracked-files=no')
 assert all(os.environ.get(k)=='1' for k in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'])
 vers=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__);assert vers==c['versions']
 if not resume:out.mkdir(parents=True,exist_ok=False)
 with (out/'LOCK').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  meta=dict(freeze=freeze,config=c,config_sha256=digest(c),sources=hashes(),versions=vers,plan=plans(c))
  if resume:assert read(out/'RUN.json')==meta
  else:save(out/'RUN.json',meta)
  event(out,'RESUME' if resume else 'START');src=source_units();calls=0
  try:
   for i,q in enumerate(meta['plan']):
    u=perturb(src[q['source']]['input'],q['delta']);ip=out/'inputs'/f"{q['id']}.json.gz"
    if ip.exists():assert read(ip)==clean(u)
    else:save(ip,u)
    for m in c['methods']:
     previous=None
     for stage in ['P0','P1']:
      p=out/'stages'/q['id']/f'{m}-{stage}.json.gz'
      if p.exists():
       record=read(p);assert record['input_sha256']==digest(u);previous=record['result'];continue
      event(out,'STAGE_START',unit=q['id'],method=m,stage=stage)
      result=V.solve_stage(c['frozen_model'],u,m,stage,previous)
      save(p,dict(unit=q['id'],method=m,stage=stage,input_sha256=digest(u),result=result));previous=result;calls+=int(result['execution']!='SKIPPED')
      event(out,'STAGE_DONE',unit=q['id'],method=m,stage=stage,category=result['category'])
    if (i+1)%80==0:print('persisted units',i+1,'new optimizer calls',calls,flush=True)
   event(out,'COMPLETE',units=len(meta['plan']),new_optimizer_calls=calls)
  except BaseException as exc:event(out,'INTERRUPTED',reason=repr(exc));raise
 return dict(units=len(meta['plan']),new_optimizer_calls=calls)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--freeze',required=True);p.add_argument('--resume',action='store_true');a=p.parse_args();print(run(a.out,a.freeze,a.resume))
