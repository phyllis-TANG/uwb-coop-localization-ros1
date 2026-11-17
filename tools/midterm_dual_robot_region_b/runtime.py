"""Immutable input plans, journal identities, budgets and A-source loading."""
import datetime,subprocess
from common import *

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def formal_context(freeze):
 lock=read(DOC/'SOURCE_LOCK.json')
 if lock.get('status')!='LOCKED':raise RuntimeError('A_SOURCE_NOT_LOCKED')
 lock=dict(lock)
 if os.environ.get('DUAL_A_SOURCE_ROOT'):lock['source_root']=os.environ['DUAL_A_SOURCE_ROOT']
 manifest=read(DOC/'FREEZE_MANIFEST.json')
 for p,h in manifest['files'].items():
  if sha(ROOT/p)!=h:raise RuntimeError('FROZEN_FILE_CHANGED:'+p)
 tree=json.loads(subprocess.check_output(['git','show',freeze+':docs/research/midterm_dual_robot_region_b/FREEZE_MANIFEST.json']))
 if tree!=manifest:raise RuntimeError('FREEZE_COMMIT_MANIFEST_MISMATCH')
 for p,h in lock['files'].items():
  if sha(Path(lock['source_root'])/p)!=h:raise RuntimeError('A_SOURCE_HASH_CHANGED:'+p)
 inputs=read(DOC/'INPUTS.json.gz');return lock,inputs

def plans(inputs,stage):
 cases=inputs[stage];out=[]
 for i,c in enumerate(cases):
  if stage=='deterministic':methods=(['J5','P4'] if i%2==0 else ['P4','J5'])+(['N4'] if c['group']=='main' else [])
  elif stage=='random':methods=['P4','N4'] if i%2==0 else ['N4','P4']
  else:raise ValueError('stage')
  for method in methods:
   small=c.get('budget_override',{});boxes=min(50000,small.get('max_boxes',50000));seconds=min(30 if stage=='deterministic' else 5,small.get('max_seconds',30 if stage=='deterministic' else 5))
   df=8 if method=='N4' else 9
   s=dict(df=df,q=inputs['thresholds'][str(df)],tolerance=['.05']*5,max_boxes=boxes,max_seconds=seconds,total_seconds=120 if stage=='deterministic' else 30,memory_bytes=1024**3)
   out.append(dict(id=c['id']+'_'+method,case=c,method=method,settings=s))
 return out

def identity(job,freeze,lock):
 return dict(schema='DUAL-B-RUN-V1',id=job['id'],case_sha256=digest(job['case']),method=job['method'],settings_sha256=digest(job['settings']),freeze_sha=freeze,a_sha=lock['a_sha'])

def a_check(case,method,settings,result,projection,lock):
 # Binding to A's actual published interface is implemented only after READY.
 from a_bridge import audit_a
 return audit_a(case,method,settings,result,projection,lock)

def inspect_unit(directory,job,expected):
 p=Path(directory);unit=job['id'];attempt=p/(unit+'.attempt.json');receipt=p/(unit+'.receipt.json');result=p/(unit+'.result.json.gz')
 if receipt.exists():
  row=read(receipt)
  if row['identity']!=expected:raise RuntimeError('IDENTITY_MISMATCH:'+unit)
  if row.get('record_sha256') and (not result.exists() or sha(result)!=row['record_sha256']):raise RuntimeError('CORRUPT_RESULT:'+unit)
  return row
 if attempt.exists() or result.exists():raise RuntimeError('UNCERTAIN_ATTEMPT_NO_AUTORETRY:'+unit)
 return None
