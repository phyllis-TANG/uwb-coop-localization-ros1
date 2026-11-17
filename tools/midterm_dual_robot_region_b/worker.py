"""One bounded method run. Atomic raw checkpoint precedes certification."""
import argparse,resource,signal,time,traceback
from common import *
from core import solve
from certificate import audit
from geometry import projections,audit_projection,evaluate
from runtime import a_check
class FullBudget(Exception):pass
def expired(*_):raise FullBudget('FULL_PIPELINE_BUDGET')
def run(job,out):
 start=time.monotonic();s=job['settings'];method=job['method'];case=job['case'];unit=job['id'];out=Path(out)
 resource.setrlimit(resource.RLIMIT_AS,(s['memory_bytes'],s['memory_bytes']))
 signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,job['remaining_seconds'])
 record=dict(identity=job['identity'],case=case,method=method,settings=s,status='STARTED');costs=dict(search=0.,certificate_b=0.,certificate_a=0.,projection=0.,evaluation=0.,compressed_io=0.)
 dest=out/(unit+'.result.json.gz');status='FAILED';error=None
 def checkpoint():
  t=time.monotonic();write(dest,record);costs['compressed_io']+=time.monotonic()-t
 try:
  t=time.monotonic();r=solve(case['model'],method,s,job['thresholds']);costs['search']=time.monotonic()-t;record['result']=r;record['status']='SEARCH_SAVED_UNCERTIFIED';checkpoint()
  t=time.monotonic();record['certificate_b']=audit(case['model'],method,s,r);costs['certificate_b']=time.monotonic()-t
  t=time.monotonic();p=projections(case['model'],r);audit_projection(case['model'],r,p);record['projections']=p;costs['projection']=time.monotonic()-t
  t=time.monotonic()
  if job.get('development'):record['certificate_a']={'status':'NOT_APPLICABLE_DEVELOPMENT'}
  else:
   record['certificate_a']=a_check(case,method,s,r,p,job['source_lock'])
   if record['certificate_a'].get('status')!='PASS':raise RuntimeError('A_CERTIFICATE_NOT_PASS')
  costs['certificate_a']=time.monotonic()-t
  t=time.monotonic();record['evaluation']=evaluate(case['model'],method,s,r,case['evaluation']);costs['evaluation']=time.monotonic()-t
  ev=record['evaluation']
  if ev['truth_in_declared_domain'] and ev['noise_event'] and ev['noise_event']['holds'] and not ev['finite_joint_outer_contains']:raise AssertionError('NOISE_EVENT_TRUE_POSITION_EXCLUDED')
  if ev['truth_in_declared_domain'] and ev['exact_joint_position_feasibility']=='FEASIBLE_PROVED' and not ev['finite_joint_outer_contains']:raise AssertionError('EXACT_FEASIBLE_POSITION_EXCLUDED')
  status='DEVELOPMENT_COMPLETE' if job.get('development') else 'COMPLETED';record['status']=status;checkpoint()
 except (Exception,MemoryError) as e:
  error=type(e).__name__+': '+str(e);status='TOTAL_BUDGET' if isinstance(e,FullBudget) else 'MEMORY_FAILURE' if isinstance(e,MemoryError) else 'FAILED'
  # Do not overwrite a valid raw checkpoint when interrupted during checking.
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
 row=dict(identity=job['identity'],status=status,error=error,costs=costs,worker_seconds=time.monotonic()-start,record_sha256=sha(dest) if dest.exists() else None,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
 write(out/(unit+'.worker.json'),row);print(json.dumps(dict(id=unit,status=status,error=error)),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--job',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();run(read(a.job),a.out)
