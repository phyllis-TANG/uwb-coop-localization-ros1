"""Published A v1/v2 comparison on all preserved certificates; no search."""
import argparse,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,digest,DOC
from runtime import plans
from checker_v2.a_loader import load_a

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--lock',type=Path,required=True);ap.add_argument('--limit',type=int,default=44);args=ap.parse_args();lock=read(args.lock);old,new=load_a(lock);out=args.root/'a_comparison';out.mkdir(exist_ok=True);source=args.root/'old_delivery';plan=plans(read(DOC/'INPUTS.json.gz'),'deterministic');done=0
 for item in plan:
  unit=item['id'];dest=out/(unit+'.json')
  if dest.exists():
   if read(dest)['a_sha']!=lock['a_sha']:raise RuntimeError('A identity differs from prior comparison')
   continue
  if done>=args.limit:break
  r=read(source/'raw'/(unit+'.result.json.gz'));c=read(source/'certificates'/(unit+'.json'));before=digest(c);old_receipt=read(args.root/'old_cost_decomposition'/(unit+'.json'));assert old_receipt['a_matches'];t=time.monotonic();result=new.check(r['case']['a_input'],c);elapsed=time.monotonic()-t
  # Old kernel was independently rerun on this exact archive in profile_old.
  assert result==r['certificate_a']['validation'];assert result['certificate_valid'];assert digest(c)==before
  assert digest(c['queue'])==old_receipt['queue_digest'];assert digest(c['projections'])==old_receipt['a_projection_digest']
  write(dest,dict(id=unit,a_sha=lock['a_sha'],new_a_check_seconds=elapsed,old_a_check_seconds=old_receipt['a_check_seconds'],conclusion_equal=True,queue_equal=True,per_car_regions_equal=True,certificate_unchanged=True,nodes=len(c['nodes']),group=item['case']['group'],method=item['method'],search_calls=0));done+=1;print(unit,'A_V2_PASS',flush=True)
 rows=[read(out/(j['id']+'.json')) for j in plan if (out/(j['id']+'.json')).exists()];write(out/'PROGRESS.json',dict(a_sha=lock['a_sha'],planned=44,completed=len(rows),failed=0,unexecuted=[j['id'] for j in plan if not (out/(j['id']+'.json')).exists()],rows=rows,search_calls=0));print('A comparison',len(rows),'/44')
if __name__=='__main__':main()
