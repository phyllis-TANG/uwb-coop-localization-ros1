"""One-shot frozen v2 execution. All writes and checks count in the original gate."""
import argparse,fcntl,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,sha,digest,canonical,DOC,ROOT
from runtime import plans,identity,utc,inspect_unit
V2DOC=DOC/'checker_v2'
def context(freeze):
 f=read(V2DOC/'FREEZE.json');assert f['freeze_sha']==freeze
 for p,h in f['files'].items():
  if sha(ROOT/p)!=h:raise RuntimeError('Frozen B file changed: '+p)
  import hashlib
  if hashlib.sha256(subprocess.check_output(['git','show',freeze+':'+p])).hexdigest()!=h:raise RuntimeError('Freeze commit mismatch: '+p)
 lock=read(V2DOC/'A_SOURCE_LOCK.json')
 for p,h in lock['files'].items():
  if sha(Path(lock['source_root'])/p)!=h:raise RuntimeError('Frozen A file changed: '+p)
 for name in ['B_COMPARISON.json','A_COMPARISON.json']:
  check=read(V2DOC/name);assert check['completed']==44 and check['failed']==0 and not check['unexecuted']
 return lock,read(DOC/'INPUTS.json.gz')
def run(stage,out,freeze,limit):
 lock,inputs=context(freeze);plan=plans(inputs,stage);out.mkdir(exist_ok=True,parents=True)
 if stage=='random':
  gate=read(V2DOC/'GATE.json');assert gate['status']=='PASS' and gate['freeze_sha']==freeze
 with (out/'LOCK').open('a') as stream:
  fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);meta=out/'RUN.json'
  if not meta.exists():write(meta,dict(stage=stage,freeze_sha=freeze,a_sha=lock['a_sha'],plan_sha256=digest(plan),planned=len(plan),start_epoch=time.time()))
  run=read(meta);assert run['freeze_sha']==freeze and run['plan_sha256']==digest(plan);count=0;blocked=None;stage_deadline=run['start_epoch']+7200 if stage=='random' else float('inf')
  for item in plan:
   expected=identity(item,freeze,lock)
   try:old=inspect_unit(out,item,expected)
   except RuntimeError as e:blocked=str(e);break
   if old:
    if old['status']!='COMPLETED':blocked='PREVIOUS_FAILURE_PRESERVED:'+item['id'];break
    continue
   if count>=limit:break
   if stage=='random' and time.time()-run['start_epoch']>=7200:blocked='RANDOM_STAGE_TOTAL_BUDGET';break
   unit=item['id'];start=time.monotonic();write(out/(unit+'.attempt.json'),dict(identity=expected,started_utc=utc(),started_epoch=time.time()));job=dict(item,identity=expected,source_lock=lock,thresholds=inputs['thresholds'],remaining_seconds=max(.01,min(item['settings']['total_seconds']-(time.monotonic()-start)-.5,stage_deadline-time.time()-.5)));jobpath=out/(unit+'.job.json');write(jobpath,job)
   with (out/(unit+'.log')).open('xb') as log:
    try:proc=subprocess.run([sys.executable,str(Path(__file__).parent/'worker_v2.py'),'--job',str(jobpath),'--out',str(out)],stdout=log,stderr=subprocess.STDOUT,timeout=max(.01,min(item['settings']['total_seconds']-(time.monotonic()-start),stage_deadline-time.time())))
    except subprocess.TimeoutExpired:proc=None
   worker=out/(unit+'.worker.json');result=out/(unit+'.result.json.gz');row=read(worker) if worker.exists() else dict(identity=expected,status='HARD_INTERRUPTION',error='NO_WORKER_RECEIPT',record_sha256=sha(result) if result.exists() else None,costs={});row.update(total_wall_seconds=time.monotonic()-start,returncode=proc.returncode if proc else None,completed_utc=utc())
   if row['total_wall_seconds']>item['settings']['total_seconds']:row.update(status='TOTAL_BUDGET',error='FULL_WALL_LIMIT_EXCEEDED')
   write(out/(unit+'.receipt.json'),row)
   wall=time.monotonic()-start
   if wall>item['settings']['total_seconds'] or time.time()>stage_deadline:
    row.update(status='TOTAL_BUDGET',error='RECEIPT_INCLUSIVE_LIMIT_EXCEEDED');write(out/(unit+'.receipt.json'),row);wall=time.monotonic()-start
   with (out/'WALL_COSTS.jsonl').open('ab') as ledger:ledger.write(canonical(dict(id=unit,wall_seconds=wall))+b'\n');ledger.flush();os.fsync(ledger.fileno())
   count+=1;update(out,plan,freeze,lock,blocked);print(stage,unit,row['status'],round(wall,4),flush=True)
   if row['status']!='COMPLETED':blocked='METHOD_FAILURE_STOP:'+unit;break
  return update(out,plan,freeze,lock,blocked)
def update(out,plan,freeze,lock,blocked):
 rows=[read(out/(p['id']+'.receipt.json')) for p in plan if (out/(p['id']+'.receipt.json')).exists()];done={r['identity']['id'] for r in rows};unknown=[p['id'] for p in plan if p['id'] not in done and (out/(p['id']+'.attempt.json')).exists()];s=dict(planned=len(plan),executed=len(rows)+len(unknown),completed=sum(r['status']=='COMPLETED' for r in rows),failed=[r['identity']['id'] for r in rows if r['status']!='COMPLETED'],interrupted=unknown,unexecuted=[p['id'] for p in plan if p['id'] not in done and p['id'] not in unknown],freeze_sha=freeze,a_sha=lock['a_sha'],blocked=blocked);write(out/'PROGRESS.json',s);return s
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['deterministic','random'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--freeze',required=True);p.add_argument('--limit',type=int,default=6);a=p.parse_args();print(run(a.stage,a.out,a.freeze,a.limit))
