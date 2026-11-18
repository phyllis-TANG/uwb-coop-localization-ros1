"""Small synthetic worker integration; never uses formal inputs or timing gate."""
import argparse,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,sha,DOC
from bridge_tests import fixture
from prepare import convert
from runtime import identity,inspect_unit
from checker_v2.a_loader import load_a

def main():
 lock=read(DOC/'checker_v2/A_SOURCE_LOCK.json');a_old,a=load_a(lock);rows=[]
 for method in ['J5','P4','N4']:
  with tempfile.TemporaryDirectory() as td:
   out=Path(td);x=fixture();case=dict(id='DEVELOPMENT_V2',group='development',a_input=x,model=convert(x),evaluation=dict(truth=['0']*5,noise=['0']*9));s=dict(df=8 if method=='N4' else 9,q='24' if method=='N4' else '26',tolerance=['.05']*5,max_boxes=40,max_seconds=2,total_seconds=10,memory_bytes=1024**3);job=dict(id='DEVELOPMENT_V2_'+method,case=case,method=method,settings=s);job.update(identity=identity(job,'DEVELOPMENT_ONLY',lock),source_lock=lock,thresholds={'8':'24','9':'26'},remaining_seconds=9);write(out/'job.json',job)
   proc=subprocess.run([sys.executable,str(Path(__file__).parent/'worker_v2.py'),'--job',str(out/'job.json'),'--out',str(out)],capture_output=True,text=True,timeout=11);assert proc.returncode==0,proc.stderr;row=read(out/(job['id']+'.worker.json'));assert row['status']=='COMPLETED',row;r=read(out/(job['id']+'.result.json.gz'));c=read(out/(job['id']+'.certificate.json.gz'));assert a_old.check(x,c)==a.check(x,c)==r['certificate_a']['validation'];rows.append(row)
   write(out/(job['id']+'.attempt.json'),dict(identity=job['identity']))
   try:inspect_unit(out,job,job['identity']);raise AssertionError('Unknown attempt was accepted')
   except RuntimeError as e:assert 'UNCERTAIN_ATTEMPT' in str(e)
 # Loading A must retain the already imported B locator core object.
 import core
 before=core.solve;load_a(lock);assert core.solve is before
 write(DOC/'checker_v2/DEVELOPMENT.json',dict(status='PASS',formal_search_calls=0,development_search_calls=3,old_new_checks_equal=True,module_name_isolation=True,unknown_attempt_rejected=True,rows=rows));print('Three synthetic integration workers passed; formal search calls=0')
if __name__=='__main__':main()
