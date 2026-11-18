"""All-old-record equality check for B parsing/projection reuse; zero search."""
import argparse,copy,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,canonical,sha,DOC
from runtime import plans
from certificate import audit as old_audit
from geometry import audit_projection as old_projection_audit
from checker_v2 import b_fast

def rejected(fn):
 try:fn()
 except (AssertionError,ValueError,KeyError):return True
 return False

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--limit',type=int,default=44);args=ap.parse_args();out=args.root/'b_comparison';out.mkdir(exist_ok=True);source=args.root/'old_delivery';plan=plans(read(DOC/'INPUTS.json.gz'),'deterministic');count=0
 for item in plan:
  unit=item['id'];dest=out/(unit+'.json')
  if dest.exists():continue
  if count>=args.limit:break
  record=read(source/'raw'/(unit+'.result.json.gz'));cert=read(source/'certificates'/(unit+'.json'));case=record['case'];method=record['method'];s=record['settings'];r=record['result'];t=time.monotonic();b=b_fast.audit(case['model'],method,s,r);bt=time.monotonic()-t;assert b==record['certificate_b'];t=time.monotonic();p=b_fast.projections(case['model'],r);b_fast.audit_projection(case['model'],r,p);pt=time.monotonic()-t;assert p==record['projections'];t=time.monotonic();c=b_fast.make_certificate(case,method,s,r,p,cost=cert['cost']);ct=time.monotonic()-t;assert canonical(c)==canonical(cert)
  write(dest,dict(id=unit,group=case['group'],method=method,nodes=len(r['nodes']),b_check_seconds=bt,projection_with_audit_seconds=pt,certificate_conversion_seconds=ct,b_conclusion_equal=True,b_regions_equal=True,a_certificate_canonical_equal=True,queue_equal=c['queue']==cert['queue'],search_calls=0));count+=1;print(unit,'PASS',flush=True)
 # Small corruption cases use preserved forced-budget certificate, not formal search.
 rr=read(source/'raw/forced_budget_P4.result.json.gz');m=rr['case']['model'];s=rr['settings'];r=rr['result'];tests=[]
 for kind in ['queue_missing','count_wrong','root_changed','duplicate_node']:
  bad=copy.deepcopy(r)
  if kind=='queue_missing':bad['queue']=[]
  elif kind=='count_wrong':bad['processed']+=1
  elif kind=='root_changed':bad['nodes'][0]['box'][0][0]='-999'
  else:bad['nodes'].append(copy.deepcopy(bad['nodes'][0]))
  assert rejected(lambda:old_audit(m,'P4',s,bad)) and rejected(lambda:b_fast.audit(m,'P4',s,bad));tests.append(kind)
 pp=copy.deepcopy(rr['projections']);pp['p']['rectangles']=[];assert rejected(lambda:old_projection_audit(m,r,pp)) and rejected(lambda:b_fast.audit_projection(m,r,pp));tests.append('projection_rectangles_missing')
 rows=[read(out/(j['id']+'.json')) for j in plan if (out/(j['id']+'.json')).exists()];write(out/'PROGRESS.json',dict(planned=44,completed=len(rows),failed=0,unexecuted=[j['id'] for j in plan if not (out/(j['id']+'.json')).exists()],rows=rows,corruption_tests=tests,b_fast_sha256=sha(Path(__file__).parent/'b_fast.py'),search_calls=0));print('B comparison',len(rows),'/44; corruptions rejected',len(tests))
if __name__=='__main__':main()
