"""Zero-search independent revalidation of identity, tree, A checker and projections."""
import argparse,time
from common import *
from runtime import *
from certificate import audit
from geometry import audit_projection,evaluate

def verify(out,freeze):
 begin=time.monotonic();lock,inputs=formal_context(freeze);meta=read(out/'RUN.json');plan=plans(inputs,meta['stage']);assert meta['freeze_sha']==freeze and meta['plan_sha256']==digest(plan)
 rows=[];nodes=0;uncertain=[]
 for job in plan:
  expected=identity(job,freeze,lock)
  try:row=inspect_unit(out,job,expected)
  except RuntimeError as e:uncertain.append(str(e));continue
  if row is None:continue
  if row['status']=='COMPLETED':
   record=read(out/(job['id']+'.result.json.gz'));assert record['identity']==expected and record['case']==job['case'] and record['settings']==job['settings']
   m=job['case']['model'];method=job['method'];s=job['settings'];r=record['result'];p=record['projections']
   z=audit(m,method,s,r);assert z==record['certificate_b'];nodes+=z['nodes'];audit_projection(m,r,p)
   az=a_check(job['case'],method,s,r,p,lock);assert az['status']=='PASS'
   assert evaluate(m,method,s,r,job['case']['evaluation'])==record['evaluation']
  rows.append(row)
 ids={r['identity']['id'] for r in rows};missing=[j['id'] for j in plan if j['id'] not in ids];status=read(out/'STATUS.json');assert status['executed']==len(rows) and set(status['unexecuted'])==set(missing)
 return dict(status='PASS' if not uncertain and all(r['status']=='COMPLETED' for r in rows) and not missing else 'INCOMPLETE_OR_FAILURES_PRESERVED',planned=len(plan),executed=len(rows),completed=sum(r['status']=='COMPLETED' for r in rows),unexecuted=missing,uncertain=uncertain,nodes_checked=nodes,search_calls=0,optimizer_calls=0,seconds=time.monotonic()-begin,freeze_sha=freeze,a_sha=lock['a_sha'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--freeze',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();z=verify(a.results,a.freeze);write(a.out,z);print(json.dumps(z))
