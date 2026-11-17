"""Post-run descriptive accepted subsets and explicit base/target failure inventory. No optimizer."""
import argparse,csv,collections
from model import *
from analyze import streams,writecsv,usable

def main(archive,rows,out):
 out.mkdir(parents=True,exist_ok=False);fail=[];unique=set();elapsed=[]
 for z in streams(archive):
  if z['type']!='PAIR':continue
  v=z['value']
  for role in ['base','target']:
   r=v[role]
   if not r['accepted']:
    key=(v['study'],v['q']['id'],v['method'],role)
    fail.append(dict(study=key[0],id=key[1],method=key[2],role=role,category=r['category'],usable=usable(r),gradient=r['gradient_inf']))
  if v['study']=='new':elapsed.extend([v['P0']['elapsed_s'],v['target']['elapsed_s']])
 writecsv(out/'ALL_ENDPOINT_FAILURES.csv',fail)
 with rows.open() as f:data=list(csv.DictReader(f))
 groups=collections.defaultdict(list)
 for r in data:groups[tuple(r[k] for k in ['study','geometry','sigma','axis','amplitude','method','car','view'])].append(r)
 result=[]
 for key,rs in groups.items():
  acc=[r for r in rs if r['base_accepted']=='True' and r['target_accepted']=='True'];z=dict(zip(['study','geometry','sigma','axis','amplitude','method','car','view'],key));z.update(planned=len(rs),accepted_pairs=len(acc))
  for k in ['relative_error','prediction_error_rms','angle_deg','target_mse','base_mse','target_mean_x','target_mean_y']:
   x=[float(r[k]) for r in acc if r.get(k)];z[k+'_accepted_mean']=float(np.mean(x)) if x else None
  result.append(z)
 writecsv(out/'ACCEPTED_PAIR_SUMMARY.csv',result);save(out/'RESOURCE_COUNTS.json',dict(sum_solver_elapsed_s=sum(elapsed),stages=len(elapsed),maximum_stage_elapsed_s=max(elapsed),note='Solver elapsed only; not wall-clock total; repeated bases in failure table are comparison occurrences'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--rows',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.archive,a.rows,a.out)
