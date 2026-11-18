"""Zero-search timing decomposition of preserved PR133 certificates.
Old recorded search/full-wall timings are retained, never replaced by these checks.
"""
import argparse,csv,sys,time,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,sha,digest,DOC
from runtime import plans
from certificate import audit
from geometry import projections,audit_projection
from a_bridge import make_certificate,a_module

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--limit',type=int,default=6);args=p.parse_args();source=args.root/'old_delivery';out=args.root/'old_cost_decomposition';out.mkdir(exist_ok=True);inputs=read(DOC/'INPUTS.json.gz');plan=plans(inputs,'deterministic');lock=read(DOC/'SOURCE_LOCK.json');a=a_module(lock['source_root']);done=0
 for item in plan:
  unit=item['id'];dest=out/(unit+'.json')
  if dest.exists():continue
  if done>=args.limit:break
  start=time.monotonic();raw=source/'raw'/(unit+'.result.json.gz');certpath=source/'certificates'/(unit+'.json');t=time.monotonic();record=read(raw);cert=read(certpath);parse=time.monotonic()-t
  old=read(source/'raw'/(unit+'.receipt.json'));r=record['result'];case=record['case'];method=record['method'];s=record['settings']
  t=time.monotonic();b=audit(case['model'],method,s,r);bt=time.monotonic()-t;assert b==record['certificate_b']
  t=time.monotonic();proj=projections(case['model'],r);audit_projection(case['model'],r,proj);pt=time.monotonic()-t;assert proj==record['projections']
  t=time.monotonic();converted=make_certificate(case,method,s,r,proj);ct=time.monotonic()-t
  # Historical archive conversion records different cost metadata, never scientific geometry.
  assert {k:v for k,v in converted.items() if k!='cost'}=={k:v for k,v in cert.items() if k!='cost'}
  t=time.monotonic();av=a.check(case['a_input'],cert);at=time.monotonic()-t;assert av==record['certificate_a']['validation'] and av['certificate_valid']
  t=time.monotonic();write(out/(unit+'.io_probe.json.gz'),record);io=time.monotonic()-t;assert sha(out/(unit+'.io_probe.json.gz'))==sha(raw)
  row=dict(id=unit,group=case['group'],method=method,old_search_seconds=old['costs']['search'],old_full_wall_seconds=old['total_wall_seconds'],old_costs=old['costs'],nodes=len(r['nodes']),retained=b['retained'],parse_seconds=parse,b_check_seconds=bt,a_check_seconds=at,certificate_conversion_seconds=ct,projection_with_audit_seconds=pt,write_seconds=io,zero_search_profile_wall_seconds=time.monotonic()-start,b_matches=True,a_matches=True,queue_digest=digest(cert['queue']),b_projection_digest=digest(proj),a_projection_digest=digest(cert['projections']),source_record_sha256=sha(raw),source_certificate_sha256=sha(certpath),search_calls=0)
  write(dest,row);done+=1;print(unit,'PASS',round(row['zero_search_profile_wall_seconds'],3),flush=True)
 rows=[read(out/(x['id']+'.json')) for x in plan if (out/(x['id']+'.json')).exists()];report=dict(planned=44,completed=len(rows),failed=0,unexecuted=[x['id'] for x in plan if not (out/(x['id']+'.json')).exists()],search_calls=0,rows=rows)
 write(out/'PROGRESS.json',report);print('Completed',len(rows),'/44',flush=True)
if __name__=='__main__':main()
