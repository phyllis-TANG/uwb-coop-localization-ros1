"""Bounded one-pass experiment, durable per-stage attempts, no automatic retry."""
import argparse,time,importlib.metadata
from bridge import *
from inputs import tracks,make,verify
from engine import lock

def run(out,mode,acceptance,freeze):
 if mode=='explore':
  assert git('rev-parse','HEAD')==freeze and not git('status','--porcelain'),'exact clean freeze required'
  a=read(acceptance);assert a['passed'] and a['source_sha256']==sources()
 cfg=read(DOC/'CONFIG.json');tt,asset=tracks();settings=read(DOC/'SOLVER.json')
 out=Path(out);out.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
 with lock(out/'RUN_LOCK'):
  seeds=cfg['seeds'] if mode=='explore' else [cfg['development_seed']];windows=range(3) if mode=='explore' else [cfg['development_window']]
  plan=[]
  for w in windows:
   for seed in seeds:
    for condition in cfg['conditions']:plan.append(dict(id=f'u{len(plan):03}',window=w,seed=seed,condition=condition['id']))
  assert len(plan)*3==(360 if mode=='explore' else 12)
  write(out/'FREEZE.json',dict(commit=git('rev-parse','HEAD'),source_sha256=sources(),config=cfg,solver=settings,input_source=asset,mode=mode,argv=sys.argv,python=sys.version,packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','matplotlib']},acceptance_sha256=filehash(acceptance) if acceptance else None))
  write(out/'PLAN.json',plan);commands=[]
  for item in plan:
   cond=next(c for c in cfg['conditions'] if c['id']==item['condition']);o,r=make(tt[item['window']],cfg,cond,item['seed']);verify(o,r)
   measurement=out/'measurements'/(item['id']+'.json');write(measurement,o);write(out/'reference'/(item['id']+'.json'),r)
   for method in cfg['methods']:
    name=item['id']+'-'+method;target=out/'estimates'/name
    cmd=[sys.executable,str(ROOT/'tools/moon1_bias_dynamics_eval/worker.py'),'--measurement',str(measurement),'--method',method,'--config',str(DOC/'SOLVER.json'),'--out',str(target)]
    write(out/'dispatch'/(name+'.attempt.json'),dict(command=cmd,identity=item['id'],method=method,measurement_sha256=filehash(measurement),config_sha256=filehash(DOC/'SOLVER.json'),commit=git('rev-parse','HEAD')))
    result=subprocess.run(cmd,capture_output=True,text=True,cwd=ROOT)
    record=dict(id=name,command=cmd,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    write(out/'dispatch'/(name+'.result.json'),record);commands.append(record)
    if result.returncode or not (target/'FINAL.json').exists():
     write(out/'failures'/(name+'.json'),dict(status='PROCESS_FAILURE',optimizer_calls_reserved=len(list(target.glob('*.attempt.json'))),automatic_retry=False))
  attempts=list((out/'estimates').rglob('*.attempt.json'));results=list((out/'estimates').rglob('*.result.json'));count=len(attempts)
  assert count<=720 if mode=='explore' else count<=24
  write(out/'RUN.json',dict(mode=mode,planned_methods=len(plan)*3,dispatched_methods=len(commands),final_records=len(list((out/'estimates').rglob('FINAL.json'))),reserved_calls=count,completed_calls=len(results),orphan_attempts=count-len(results),elapsed_s=time.perf_counter()-start,formal_runs=0,source_unchanged=sources()==read(out/'FREEZE.json')['source_sha256']))
  print('Completed',mode,len(commands),'methods',count,'calls')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--mode',choices=['smoke','explore'],required=True);p.add_argument('--acceptance');p.add_argument('--freeze');a=p.parse_args();run(a.out,a.mode,a.acceptance,a.freeze)
