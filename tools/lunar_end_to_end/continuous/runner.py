"""Frozen paired runs with attempts, checkpoints, receipts and full denominators."""
import argparse,gzip,json,os,signal,subprocess,time,traceback
from pathlib import Path
import numpy as np
from coverage import DOC,ART,write,sha
from prepare import digest
from estimator import solve
from checker import metrics,audit

def inputs():return json.loads(gzip.decompress((DOC/'INPUTS.json.gz').read_bytes()))
def plan(stage):
 rows=[]
 for r in inputs():
  ref=r['reference'];cond=ref['condition'];seed=ref['seed'];methods=[]
  if stage=='main' and cond!='correlated_optional':methods=['M0','M2','M3']
  if stage=='optional' and cond=='normal':methods=['M3W']
  if stage=='optional' and cond=='correlated_optional':methods=['M3','M3W']
  if seed%2:methods.reverse()
  for method in methods:rows.append(dict(key=f'{cond}_{seed}_{method}',id=r['observation']['id'],method=method,rho=.8 if method=='M3W' else None))
 return rows

def frozen():
 f=json.loads((DOC/'FREEZE.json').read_text())
 for p,h in f['files'].items():assert sha(DOC.parents[3]/p)==h,p
 return f

def run(stage,freeze_sha):
 frozen();assert subprocess.check_output(['git','cat-file','-t',freeze_sha],text=True).strip()=='commit';frozenbytes=subprocess.check_output(['git','show',freeze_sha+':docs/research/lunar_end_to_end/continuous/FREEZE.json']);assert json.loads(frozenbytes)==json.loads((DOC/'FREEZE.json').read_text())
 tasks=plan(stage);lookup={r['observation']['id']:r for r in inputs()};root=ART/'runs';root.mkdir(exist_ok=True)
 if stage=='optional':
  main=json.loads((DOC/'MAIN_READBACK.json').read_text());assert main['checked']==120 and main['status']=='PASS'
 started=time.monotonic();done=[];write(root/f'{stage}_PLAN.json',dict(tasks=tasks,freeze_sha=freeze_sha))
 for task in tasks:
  key=task['key'];r=lookup[task['id']];path=root/(key+'.json');attempt=root/(key+'.attempt.json')
  if path.exists():
   z=json.loads(path.read_text());assert z['input_sha256']==r['input_sha256'] and z['freeze_sha']==freeze_sha;done.append(key);continue
  if attempt.exists():raise RuntimeError('Unclear prior attempt: '+key)
  if time.monotonic()-started>3600:break
  tick=time.monotonic();write(attempt,dict(task=task,input_sha256=r['input_sha256'],freeze_sha=freeze_sha,started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
  def alarm(*_):raise TimeoutError('30 second method budget')
  signal.signal(signal.SIGALRM,alarm);signal.alarm(30)
  try:
   z=solve(r['observation'],'M3' if task['method']=='M3W' else task['method'],task['rho'],lambda x:write(root/(key+'.checkpoint.json'),x));z['metrics']=metrics(r['observation'],r['reference'],z['x'],'M3' if task['method']=='M3W' else task['method'])
  except Exception as e:z=dict(state='FAILED',finite=False,error=type(e).__name__)
  finally:signal.alarm(0)
  z.update(task=task,method='M3' if task['method']=='M3W' else task['method'],rho=task['rho'],input_sha256=r['input_sha256'],freeze_sha=freeze_sha,wall_seconds=time.monotonic()-tick);write(path,z);done.append(key)
  write(DOC/'PROGRESS.json',dict(stage=stage,planned=len(tasks),completed=len(done),current_case=key,last_update_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),freeze_sha=freeze_sha))
  print(stage,len(done),len(tasks),key,z['state'],flush=True)
 write(root/f'{stage}_STATUS.json',dict(planned=len(tasks),completed=len(done),unexecuted=[x['key'] for x in tasks if x['key'] not in done],stage_seconds=time.monotonic()-started))

def readback(stage):
 frozen();lookup={r['observation']['id']:r for r in inputs()};checked=[];missing=[];failed=[];maxcost=maxgrad=0
 for task in plan(stage):
  p=ART/'runs'/(task['key']+'.json')
  if not p.exists():missing.append(task['key']);continue
  r=json.loads(p.read_text());inp=lookup[task['id']];assert r['input_sha256']==inp['input_sha256']==digest(inp['observation'])
  if not r['finite']:failed.append(task['key']);continue
  a=audit(inp['observation'],r);maxcost=max(maxcost,a['cost_error']);maxgrad=max(maxgrad,a['gradient_error']);assert metrics(inp['observation'],inp['reference'],r['x'],r['method'])==r['metrics'];checked.append(task['key'])
 write(DOC/(stage.upper()+'_READBACK.json'),dict(status='PASS' if not missing and not failed else 'INCOMPLETE',checked=len(checked),missing=missing,failed=failed,max_cost_error=maxcost,max_gradient_error=maxgrad,optimizer_calls=0))
 print(stage,'readback',len(checked),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['run','readback']);p.add_argument('stage',choices=['main','optional']);p.add_argument('--freeze');a=p.parse_args()
 if a.action=='run':run(a.stage,a.freeze)
 else:readback(a.stage)
