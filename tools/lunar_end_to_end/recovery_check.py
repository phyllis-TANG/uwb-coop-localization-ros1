"""Real process kill and signal timeout checks with no optimizer calls."""
import json,subprocess,sys,tempfile,time
from pathlib import Path
from inputs import atomic,DOC
from runner import progress
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)
 script="import time,json,pathlib; p=pathlib.Path(__import__('sys').argv[1]); (p/'attempts').mkdir(); (p/'endpoints').mkdir(); (p/'attempts/killed.json').write_text('{}'); (p/'endpoints/killed.json').write_text(json.dumps({'optimizer_calls_started':1,'stages':[]})); (p/'ready').touch(); time.sleep(30)"
 p=subprocess.Popen([sys.executable,'-c',script,tmp])
 for _ in range(100):
  if (root/'ready').exists():break
  time.sleep(.01)
 assert (root/'ready').exists();p.terminate();p.wait(timeout=2)
 rec=progress(root,[dict(key='killed',group='test'),dict(key='fresh',group='test')]);assert rec['optimizer_calls']==1 and rec['statuses']['INTERRUPTED']==1 and rec['statuses']['UNEXECUTED']==1
 # Exercise the same POSIX alarm mechanism in a subprocess without consuming optimization budget.
 code="import signal,time,sys;sys.path.insert(0,sys.argv[1]);from runner import timeout;signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,.03)\ntry:time.sleep(1)\nexcept TimeoutError:print('EXPECTED_TIMEOUT')"
 ans=subprocess.run([sys.executable,'-c',code,str(Path(__file__).parent)],capture_output=True,text=True);assert ans.returncode==0 and 'EXPECTED_TIMEOUT' in ans.stdout
 atomic(DOC/'RECOVERY_CHECK.json',dict(passed=True,terminated_returncode=p.returncode,ledger=rec,actual_alarm=True,optimizer_calls=0,note='Synthetic worker killed after durable started-call receipt; no actual evaluation task rerun'))
 print('Recovery and actual alarm checks passed')
