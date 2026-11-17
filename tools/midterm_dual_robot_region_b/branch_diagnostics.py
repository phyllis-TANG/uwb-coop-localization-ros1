"""Post-freeze descriptive sign witnesses; no search, no new observations."""
import argparse,csv
from itertools import product
from fractions import Fraction as F
from common import *
from certificate import retained,unpack,bias_at,bound,contains,point
from analyze_delivery import csvwrite

def inspect(results,out):
 inputs=read(DOC/'INPUTS.json.gz');rows=[]
 for c in inputs['deterministic']:
  if c['group']!='main':continue
  truth=list(map(F,c['evaluation']['truth'][:4]));m=c['model']
  for method in ('P4','N4'):
   path=results/'deterministic'/(c['id']+'_'+method+'.result.json.gz')
   if not path.exists():continue
   r=read(path)
   if r.get('status')!='COMPLETED':continue
   for ps,ss in product((1,-1),repeat=2):
    pos=[truth[0],ps*truth[1],truth[2],ss*truth[3]];pos=list(map(str,pos));labels=('+' if ps>0 else '-')+('+' if ss>0 else '-')
    if method=='P4':z=bias_at(pos,m,inputs['thresholds']['9']);status=z['status'];inner=z['inner'];outer=z['outer']
    else:
     lo,hi=bound(tuple(point(x) for x in pos),m,'N4');q=F(inputs['thresholds']['8']);status='FEASIBLE_PROVED' if hi<=q else 'EMPTY_PROVED' if lo>q else 'UNKNOWN';inner=outer=None
    candidates=inside=0
    for n in retained(r['result']):
     b=unpack(n['box']);matches=(b[1][1]>0 if ps>0 else b[1][0]<0) and (b[3][1]>0 if ss>0 else b[3][0]<0)
     candidates+=matches;inside+=matches and n['status']=='INSIDE'
    rows.append(dict(case=c['id'],condition=c['condition'],geometry=c['evaluation']['geometry'],method=method,sign_quadrant=labels,fixed_joint_point=','.join(pos),point_feasibility=status,bias_inner=str(inner),bias_outer=str(outer),finite_joint_hit=contains(r['result'],pos),candidate_joint_boxes=candidates,certified_inside_joint_boxes=inside,interpretation='Sign quadrants are not a proof of topological connected components.'))
 csvwrite(out,rows);print(json.dumps(dict(rows=len(rows),search_calls=0,optimizer_calls=0,post_freeze_descriptive=True)))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();inspect(a.results,a.out)
