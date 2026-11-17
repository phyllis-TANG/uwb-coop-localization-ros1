"""Counted fake solvers only; crash boundaries and actual two-process lock conflict."""
import argparse,json,multiprocessing as mp,tempfile
from pathlib import Path
from recovery import *
class Crash(BaseException):pass

def worker(root,i,entered,release,q):
 def fake():entered.set();assert release.wait(10);return {'category':'OK'}
 try:q.put(execute(root,i,fake)['mode'])
 except BaseException as e:q.put(type(e).__name__)

def tests():
 checks=[]
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);source=Path(__file__);i=identity('unit','B2','P1',{'obs':[1,2]},{'sigma':.04},[source])
  for phase in ['before_attempt','after_attempt','after_call','after_result','after_done']:
   count=[0];d=root/phase
   def fake():count[0]+=1;return {'category':'OK'}
   def hook(p):
    if p==phase:raise Crash(p)
   try:execute(d,i,fake,hook);raise AssertionError('missing crash')
   except Crash:pass
   before=count[0]
   if phase in ['after_attempt','after_call']:
    for _ in range(2):
     try:execute(d,i,fake);raise AssertionError('unsafe retry')
     except UncertainExecution:pass
    assert count[0]==before;assert (stage_path(d,i)/'UNCERTAIN.json').exists();mode='EXECUTION_UNCERTAIN'
   else:
    out=execute(d,i,fake);mode=out['mode'];assert count[0]==1
    snap={p.name:p.read_bytes() for p in stage_path(d,i).glob('*.json')}
    assert execute(d,i,fake)['mode']=='RESTORED' and count[0]==1
    assert snap=={p.name:p.read_bytes() for p in stage_path(d,i).glob('*.json')}
   checks.append(dict(case=phase,calls_before_recovery=before,calls_after_recovery=count[0],mode=mode))
  for failure in ['returned_failure','exception']:
   count=[0]
   def bad():
    count[0]+=1
    if failure=='exception':raise ValueError('intentional')
    return {'category':'FAILED','estimate':None}
   a=execute(root/failure,i,bad);b=execute(root/failure,i,bad);assert a['payload']==b['payload'] and count[0]==1;checks.append(dict(case=failure,calls=1,mode=b['mode']))
  d=root/'identity';execute(d,i,lambda:{'ok':1})
  for field in ['input_sha256','config_sha256','code_sha256']:
   changed=dict(i);changed[field]='f'*64
   try:execute(d,changed,lambda:(_ for _ in ()).throw(AssertionError('called')));raise AssertionError('accepted mismatch')
   except IdentityMismatch:checks.append(dict(case='mismatch_'+field,called=False))
  rp=stage_path(d,i)/'RESULT.json';r=read(rp);r['identity']['stage']='P0';rp.write_bytes(canonical(r))
  try:execute(d,i,lambda:None);raise AssertionError('accepted stage tamper')
  except IdentityMismatch:checks.append(dict(case='result_stage_identity',called=False))
  ctx=mp.get_context('spawn');entered=ctx.Event();release=ctx.Event();q=ctx.Queue();d=root/'concurrent';proc=ctx.Process(target=worker,args=(d,i,entered,release,q));proc.start();assert entered.wait(10)
  try:
   try:execute(d,i,lambda:(_ for _ in ()).throw(AssertionError('second call')));raise AssertionError('no conflict')
   except ConcurrentExecution:checks.append(dict(case='two_process_conflict',second_solver_called=False))
  finally:release.set();proc.join(10)
  assert proc.exitcode==0 and q.get(timeout=3)=='EXECUTED';assert execute(d,i,lambda:None)['mode']=='RESTORED'
 return dict(status='PASS',checks=checks,real_optimizer_calls=0,formal_runs=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();z=tests();a.out.parent.mkdir(parents=True,exist_ok=True)
 with a.out.open('x') as f:json.dump(z,f,indent=2)
 print(json.dumps(z))
