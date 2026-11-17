"""Frozen-stage execution with durable attempts, progress and exact denominators."""
import argparse,fcntl,subprocess,sys,time
from common import *
from runtime import *

def run(stage,out,freeze):
 lock,inputs=formal_context(freeze);plan=plans(inputs,stage);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 if stage=='random':
  gate=read(DOC/'GATE.json')
  if gate.get('status')!='PASS' or gate.get('freeze_sha')!=freeze:raise RuntimeError('RANDOM_GATE_NOT_PASS')
 with (out/'LOCK').open('a') as fd:
  fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  meta=out/'RUN.json'
  if meta.exists():
   old=read(meta)
   if old['freeze_sha']!=freeze or old['plan_sha256']!=digest(plan):raise RuntimeError('STAGE_IDENTITY_MISMATCH')
  else:write(meta,dict(stage=stage,freeze_sha=freeze,a_sha=lock['a_sha'],plan_sha256=digest(plan),planned=len(plan),start_epoch=time.time(),created=utc()))
  start=read(meta)['start_epoch'];rows=[];blocked=None
  def progress(current=None):
   p=dict(schema='DUAL-B-PROGRESS-V1',stage=stage,planned=len(plan),completed=sum(x['status']=='COMPLETED' for x in rows),executed=len(rows),last_updated=utc(),current_case=current,blocked=blocked,freeze_sha=freeze,a_sha=lock['a_sha'])
   write(out/'PROGRESS.json',p);write(DOC/'PROGRESS.json',p)
  progress()
  for item in plan:
   expected=identity(item,freeze,lock)
   try:prior=inspect_unit(out,item,expected)
   except RuntimeError as e:blocked=str(e);break
   if prior is not None:
    rows.append(prior)
    if prior['status']!='COMPLETED':blocked='PREVIOUS_FAILURE_PRESERVED:'+item['id'];break
    continue
   if stage=='random' and time.time()-start>=7200:blocked='RANDOM_STAGE_TOTAL_BUDGET';break
   progress(item['id']);t=time.monotonic();write(out/(item['id']+'.attempt.json'),dict(identity=expected,started=utc(),started_epoch=time.time()))
   job=dict(item,identity=expected,thresholds=inputs['thresholds'],source_lock=lock,remaining_seconds=max(.01,item['settings']['total_seconds']-(time.monotonic()-t)-.5))
   jobfile=out/(item['id']+'.job.json');write(jobfile,job)
   log=out/(item['id']+'.log')
   with log.open('xb') as stream:
    try:proc=subprocess.run([sys.executable,str(TOOL/'worker.py'),'--job',str(jobfile),'--out',str(out)],stdout=stream,stderr=subprocess.STDOUT,timeout=max(.01,item['settings']['total_seconds']-(time.monotonic()-t)))
    except subprocess.TimeoutExpired:proc=None
   worker=out/(item['id']+'.worker.json');result=out/(item['id']+'.result.json.gz')
   if worker.exists():row=read(worker)
   else:row=dict(identity=expected,status='HARD_INTERRUPTION',error='NO_COMPLETE_WORKER_RECEIPT',record_sha256=sha(result) if result.exists() else None,costs={},worker_seconds=None)
   row['total_wall_seconds']=time.monotonic()-t;row['completed_utc']=utc();row['returncode']=proc.returncode if proc else None
   if row['total_wall_seconds']>item['settings']['total_seconds']:
    row['status']='TOTAL_BUDGET';row['error']='FULL_WALL_LIMIT_EXCEEDED'
   write(out/(item['id']+'.receipt.json'),row)
   # Additional wall ledger includes receipt fsync; original method cost is never replaced.
   with (out/'WALL_COSTS.jsonl').open('ab') as f:
    f.write(canonical(dict(id=item['id'],wall_seconds=time.monotonic()-t))+b'\n');f.flush();os.fsync(f.fileno())
   rows.append(row);progress();print(stage,len(rows),'/',len(plan),item['id'],row['status'],flush=True)
   if row['status']!='COMPLETED':blocked='METHOD_FAILURE_STOP:'+item['id'];break
  executed={r['identity']['id'] for r in rows};unrun=[p['id'] for p in plan if p['id'] not in executed]
  status=dict(stage=stage,freeze_sha=freeze,a_sha=lock['a_sha'],planned=len(plan),executed=len(rows),completed=sum(r['status']=='COMPLETED' for r in rows),failures=[r['identity']['id'] for r in rows if r['status']!='COMPLETED'],unexecuted=unrun,blocked=blocked,elapsed_seconds=time.time()-start)
  write(out/'STATUS.json',status);progress();print(json.dumps(status),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['deterministic','random'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--freeze',required=True);a=p.parse_args();run(a.stage,a.out,a.freeze)
