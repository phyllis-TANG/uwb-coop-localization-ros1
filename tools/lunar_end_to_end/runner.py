"""One writer, durable attempts/endpoints, no replay of already-started methods."""
import argparse,fcntl,json,os,signal,time
from pathlib import Path
from inputs import DOC,ART,atomic,digest
from model import solve
from checker import metrics
STATES=['ACCEPTED','NOT_STATIONARY','BUDGET_EXHAUSTED','RANK_DEFICIENT','NONFINITE','FAILED','INTERRUPTED','UNEXECUTED']
def progress(root,plan):
 statuses={s:0 for s in STATES};calls=0;started=0;finite=0;elapsed=0.;groups={}
 for task in plan:
  key=task['key'];p=root/'results'/f'{key}.json';a=root/'attempts'/f'{key}.json';started+=a.exists()
  if p.exists():
   r=json.loads(p.read_text());s=r['state'];calls+=r.get('optimizer_calls_started',len(r.get('stages',[])));finite+=int(r.get('finite',False));elapsed+=r.get('seconds',0)
  else:
   s='INTERRUPTED' if a.exists() else 'UNEXECUTED'
   endpoint=root/'endpoints'/f'{key}.json'
   if endpoint.exists():er=json.loads(endpoint.read_text());calls+=er.get('optimizer_calls_started',len(er.get('stages',[])))
  statuses[s]+=1;g=groups.setdefault(task['group'],{s:0 for s in STATES});g[s]+=1
 return dict(planned=len(plan),attempted=started,finite_results=finite,statuses=statuses,optimizer_calls=calls,completed_method_seconds=elapsed,groups=groups)
def timeout(signum,frame):raise TimeoutError('30 second per-method hard limit')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=100);ap.add_argument('--root',default=str(ART/'evaluation'));args=ap.parse_args();root=Path(args.root);root.mkdir(exist_ok=True,parents=True)
 lock=(root/'runner.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 freeze=json.loads((DOC/'FREEZE.json').read_text());head=os.popen('git rev-parse HEAD').read().strip()
 if head!=freeze['freeze_sha']:raise RuntimeError('HEAD differs from frozen code')
 for path,h in freeze['files'].items():
  import hashlib
  if hashlib.sha256((DOC.parents[2]/path).read_bytes()).hexdigest()!=h:raise RuntimeError('Frozen file modified: '+path)
 plan=json.loads((root/'RUN_PLAN.json').read_text());identities={x['id']:x for x in json.loads((DOC/'INPUT_MANIFEST.json').read_text())};clock=root/'CLOCK.json'
 if not clock.exists():atomic(clock,dict(start=time.time(),deadline=time.time()+21600-freeze['development_seconds']))
 deadline=json.loads(clock.read_text())['deadline'];count=0
 for task in plan:
  if count>=args.limit or time.time()>=deadline:break
  key=task['key'];attempt=root/'attempts'/f'{key}.json'
  if attempt.exists() or (root/'results'/f'{key}.json').exists():continue
  o=json.loads((root/'observations'/f"{task['input_id']}.json").read_text());ref=json.loads((root/'references'/f"{task['input_id']}.json").read_text())
  identity=identities[task['input_id']]
  if digest(o)!=identity['observation_digest'] or digest(ref)!=identity['reference_digest']:raise RuntimeError('Input identity mismatch')
  atomic(attempt,dict(start=time.time(),pid=os.getpid(),input_sha256=digest(o),freeze_sha=head,method=task['method']));start=time.monotonic()
  try:
   signal.signal(signal.SIGALRM,timeout);signal.alarm(30)
   result=solve(o,task['method'],lambda v:atomic(root/'endpoints'/f'{key}.json',v));result['metrics']=metrics(o,ref,task['method'],result['q'])
  except Exception as e:
   endpoint=root/'endpoints'/f'{key}.json';result=dict(state='FAILED',error=repr(e),optimizer_calls_started=json.loads(endpoint.read_text()).get('optimizer_calls_started',0) if endpoint.exists() else 0,stages=json.loads(endpoint.read_text()).get('stages',[]) if endpoint.exists() else [],seconds=time.monotonic()-start)
  finally:signal.alarm(0)
  atomic(root/'results'/f'{key}.json',dict(**result,key=key,method=task['method'],input_id=task['input_id'],freeze_sha=head));atomic(root/'PROGRESS.json',progress(root,plan));count+=1
 print(json.dumps(progress(root,plan)))
if __name__=='__main__':main()
