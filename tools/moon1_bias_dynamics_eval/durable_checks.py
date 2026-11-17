"""Fake optimizers only; ensure attempted stages can never auto-rerun."""
import argparse,subprocess
from types import SimpleNamespace
from bridge import *
from engine import once,lock

def run(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 o=unpack(OLD/'results/measurements.json.gz')['u000'];_,start,_=problem(o,'M1');cfg=read(DOC/'CONTINUATION.json')['settings'];calls=[]
 def fake(f,x,**kw):calls.append(1);return SimpleNamespace(x=x,success=True,status=1,message='FAKE',nfev=1,njev=1)
 result=once(o,'M1',start,cfg,out/'fake','P0',optimizer=fake)
 try:once(o,'M1',start,cfg,out/'fake','P0',optimizer=fake);raise AssertionError('reran')
 except RuntimeError as e:assert 'ATTEMPT_EXISTS' in str(e)
 class Crash(BaseException):pass
 def crash(*a,**k):raise Crash()
 try:once(o,'M1',start,cfg,out/'crash','P0',optimizer=crash)
 except Crash:pass
 assert (out/'crash/P0.attempt.json').exists() and not (out/'crash/P0.result.json').exists()
 try:once(o,'M1',start,cfg,out/'crash','P0',optimizer=fake);raise AssertionError('crash retried')
 except RuntimeError as e:assert 'ATTEMPT_EXISTS' in str(e)
 with lock(out/'testlock'):
  p=subprocess.run([sys.executable,'-c','import fcntl,sys; f=open(sys.argv[1],"a"); fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)',str(out/'testlock')],capture_output=True,text=True)
  assert p.returncode!=0 and 'BlockingIOError' in p.stderr
 assert len(calls)==1
 write(out/'CHECKS.json',dict(passed=True,duplicate_refused=True,orphan_attempt_refused=True,concurrent_lock_refused=True,fake_invocations=2,actual_optimizer_calls=0,source_sha256=sources(),argv=sys.argv))
 print('PASS durability; zero actual optimizer calls')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();run(a.out)
