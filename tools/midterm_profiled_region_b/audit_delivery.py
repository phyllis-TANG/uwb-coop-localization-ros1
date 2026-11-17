"""Post-freeze independent counters/timing/summary audit, no search or tuning."""
import argparse,csv,collections,math
from common import *
def audit(root,analysis):
 report={};summ=list(csv.DictReader((analysis/'SUMMARY.csv').open()))
 for stage in ['deterministic','random']:
  p=root/stage;meta=read(p/'RUN.json');planned=read(DOC/'INPUTS.json.gz')[stage];rows=[];nodes=collections.Counter();costs=collections.Counter();feasible=collections.defaultdict(collections.Counter)
  wall={r['id']:r['wall_seconds'] for r in map(json.loads,(p/'WALL_COSTS.jsonl').read_text().splitlines())}
  for f in p.glob('*.receipt.json'):
   r=read(f);v=read(p/(r['id']+'.json.gz'));counts=collections.Counter(n['status'] for n in v['result']['nodes']);assert dict(counts)==v['result']['counts'];nodes.update(counts)
   assert r['processed']==sum(count for k,count in counts.items() if k!='PENDING')
   assert r['pending']==counts['PENDING'] and r['undecided']==counts['UNDECIDED'] and r['inside']==counts['INSIDE']
   assert wall[r['id']]>=r['total_seconds']
   parts=sum(r[k] or 0 for k in ['search_seconds','load_seconds','certificate_seconds','metrics_evaluation_seconds','result_io_seconds']);assert r['total_seconds']>=parts
   for k in ['search_seconds','certificate_seconds','metrics_evaluation_seconds','result_io_seconds']:costs[k]+=r[k] or 0
   costs['method_wall_seconds']+=wall[r['id']];rows.append(r)
   if r['method']=='PROFILED':feasible[r['condition']][v['evaluation']['bias_reconstruction_at_truth_xy']['status']]+=1
  for s in [x for x in summ if x['stage']==stage]:
   rs=[r for r in rows if r['condition']==s['condition'] and r['method']==s['method']];assert len(rs)==int(s['executed']);assert sum(r['truth_contained'] for r in rs)==int(s['truth_contained']);assert sum(r['empty'] for r in rs)==int(s['empty'])
   assert int(s['planned'])==sum(c['condition']==s['condition'] for c in planned)
   assert math.isclose(sum(wall[r['id']] for r in rs)/len(rs),float(s['mean_wall']),rel_tol=1e-12)
  report[stage]=dict(planned=2*len(planned),records=len(rows),nodes=dict(nodes),costs=dict(costs),pointwise_bias_feasibility=dict(feasible),stage_elapsed=read(p/'STATUS.json')['elapsed_including_io_seconds'])
 return dict(status='PASS',stages=report,search_calls=0,optimizer_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--analysis',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();z=audit(a.results,a.analysis);write(a.out,z);print(json.dumps(z))
