"""Bounded single method; unchanged search, separate A/B checks and full I/O cost."""
import time
START=time.monotonic()
import argparse,resource,signal,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,sha
from core import solve
from geometry import evaluate
from checker_v2 import b_fast
from checker_v2.a_loader import load_a
class BudgetExpired(Exception):pass
def expired(*_):raise BudgetExpired('FULL_PIPELINE_BUDGET')
def run(jobfile,out):
 out=Path(out);t=time.monotonic();job=read(jobfile);parse_seconds=time.monotonic()-t;s=job['settings'];unit=job['id'];case=job['case'];method=job['method'];dest=out/(unit+'.result.json.gz');certdest=out/(unit+'.certificate.json.gz')
 resource.setrlimit(resource.RLIMIT_AS,(s['memory_bytes'],s['memory_bytes']));signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(.01,job['remaining_seconds']-(time.monotonic()-START)))
 record=dict(identity=job['identity'],case=case,method=method,settings=s,status='STARTED');costs=dict(input_parse=parse_seconds,source_load=0.,search=0.,certificate_b=0.,projection=0.,certificate_conversion=0.,certificate_a=0.,evaluation=0.,compressed_io=0.);status='FAILED';error=None
 def checkpoint():
  t=time.monotonic();write(dest,record);costs['compressed_io']+=time.monotonic()-t
 try:
  t=time.monotonic();_,a=load_a(job['source_lock']);costs['source_load']=time.monotonic()-t
  t=time.monotonic();r=solve(case['model'],method,s,job['thresholds']);costs['search']=time.monotonic()-t;record['result']=r;record['status']='SEARCH_SAVED_UNCERTIFIED';checkpoint()
  t=time.monotonic();record['certificate_b']=b_fast.audit(case['model'],method,s,r);costs['certificate_b']=time.monotonic()-t
  t=time.monotonic();p=b_fast.projections(case['model'],r);b_fast.audit_projection(case['model'],r,p);record['projections']=p;costs['projection']=time.monotonic()-t
  t=time.monotonic();cert=b_fast.make_certificate(case,method,s,r,p);costs['certificate_conversion']=time.monotonic()-t
  t=time.monotonic();validation=a.check(case['a_input'],cert);costs['certificate_a']=time.monotonic()-t;assert validation['certificate_valid'];record['certificate_a']=dict(status='PASS',checker_sha256=job['source_lock']['files']['tools/midterm_dual_robot_contract_a/checker_v2.py'],validation=validation)
  t=time.monotonic();ev=evaluate(case['model'],method,s,r,case['evaluation']);record['evaluation']=ev;costs['evaluation']=time.monotonic()-t
  if ev['truth_in_declared_domain'] and ev['noise_event'] and ev['noise_event']['holds']:assert ev['finite_joint_outer_contains']
  if ev['truth_in_declared_domain'] and ev['exact_joint_position_feasibility']=='FEASIBLE_PROVED':assert ev['finite_joint_outer_contains']
  if ev.get('simultaneous_mirror') and ev['noise_event'] and ev['noise_event']['holds']:assert ev['simultaneous_mirror']['finite_joint_outer_contains']
  if case['id']=='empty_in_domain':assert r['empty_proved']
  if case['id']=='forced_budget':assert r['queue']
  t=time.monotonic();write(certdest,cert);costs['compressed_io']+=time.monotonic()-t;record['status']=status='COMPLETED';checkpoint()
 except Exception as e:
  error=type(e).__name__+': '+str(e);status='TOTAL_BUDGET' if isinstance(e,BudgetExpired) else 'MEMORY_FAILURE' if isinstance(e,MemoryError) else 'FAILED'
 finally:signal.setitimer(signal.ITIMER_REAL,0)
 write(out/(unit+'.worker.json'),dict(identity=job['identity'],status=status,error=error,costs=costs,worker_seconds=time.monotonic()-START,record_sha256=sha(dest) if dest.exists() else None,certificate_sha256=sha(certdest) if certdest.exists() else None,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
 print(unit,status,error,flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();run(args.job,args.out)
