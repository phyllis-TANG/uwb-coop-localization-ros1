"""Development-only tests of bounded workers and interrupted-run inventory."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from common import write,read,sha,digest,TOOL
from tests import fixture,settings,TH
from runtime import inspect_unit,identity,plans
from geometry import evaluate
from core import solve
class Tests(unittest.TestCase):
 def job(self,method='P4'):
  c=dict(id='development_pipeline',group='main',model=fixture(),evaluation=dict(truth=['0']*5,noise=['0']*9));s=settings(method);s.update(total_seconds=10,memory_bytes=1024**3)
  j=dict(id=c['id']+'_'+method,case=c,method=method,settings=s);lock={'a_sha':None};j.update(identity=identity(j,'DEVELOPMENT_ONLY',lock),source_lock=lock,development=True,thresholds=TH,remaining_seconds=8);return j
 def test_25_full_worker(self):
  for method in ('J5','P4','N4'):
   with tempfile.TemporaryDirectory() as td:
    d=Path(td);j=self.job(method);write(d/'job.json',j);p=subprocess.run([sys.executable,str(TOOL/'worker.py'),'--job',str(d/'job.json'),'--out',td],capture_output=True,text=True,timeout=12);self.assertEqual(p.returncode,0,p.stderr)
    w=read(d/(j['id']+'.worker.json'));self.assertEqual(w['status'],'DEVELOPMENT_COMPLETE',w);self.assertEqual(w['record_sha256'],sha(d/(j['id']+'.result.json.gz')))
 def test_26_unknown_attempt(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);j=self.job();write(d/(j['id']+'.attempt.json'),{'identity':j['identity']})
   with self.assertRaisesRegex(RuntimeError,'UNCERTAIN_ATTEMPT_NO_AUTORETRY'):inspect_unit(d,j,j['identity'])
 def test_27_receipt_identity(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);j=self.job();write(d/(j['id']+'.receipt.json'),{'identity':{}})
   with self.assertRaisesRegex(RuntimeError,'IDENTITY_MISMATCH'):inspect_unit(d,j,j['identity'])
 def test_28_receipt_corruption(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);j=self.job();write(d/(j['id']+'.receipt.json'),{'identity':j['identity'],'record_sha256':'wrong'})
   with self.assertRaisesRegex(RuntimeError,'CORRUPT_RESULT'):inspect_unit(d,j,j['identity'])
 def test_29_outside_truth_qualification(self):
  m=fixture();s=settings();r=solve(m,'P4',s,TH);e=evaluate(m,'P4',s,r,{'truth':['100','0','0','0','0'],'noise':['0']*9});self.assertFalse(e['truth_in_declared_domain']);self.assertTrue(e['noise_event']['holds'])
 def test_30_hard_full_budget(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);j=self.job();j['remaining_seconds']=.00001;write(d/'job.json',j);p=subprocess.run([sys.executable,str(TOOL/'worker.py'),'--job',str(d/'job.json'),'--out',td],capture_output=True,text=True,timeout=5)
   w=d/(j['id']+'.worker.json')
   if w.exists():self.assertNotEqual(read(w)['status'],'DEVELOPMENT_COMPLETE')
   else:self.assertNotEqual(p.returncode,0)
 def test_31_plan_counts(self):
  cs=[dict(id='dev'+str(i),group='main' if i<12 else 'special') for i in range(16)];ins={'thresholds':TH,'deterministic':cs,'random':[dict(id='r'+str(i)) for i in range(120)]}
  self.assertEqual(len(plans(ins,'deterministic')),44);self.assertEqual(len(plans(ins,'random')),240)
if __name__=='__main__':unittest.main(verbosity=2)
