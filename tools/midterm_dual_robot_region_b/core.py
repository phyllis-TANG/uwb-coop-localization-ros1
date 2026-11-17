"""Dimension-general certified box search. No evaluation truth is accepted."""
import resource,time
from collections import deque,Counter
from common import I,validate
D=I.D

def distance(a,b):return I.sqrt(I.add(I.square(I.sub(a[0],b[0])),I.square(I.sub(a[1],b[1]))))
def gap(t,l,u):
 lo=max(D(0),I.LO.subtract(l[0],t[1]),I.LO.subtract(t[0],u[1]))
 hi=max(D(0),I.HI.subtract(l[1],t[0]),I.HI.subtract(t[1],u[0]))
 return I.LO.multiply(lo,lo),I.HI.multiply(hi,hi)
def predictions(box,m):
 a=[tuple(I.point(x) for x in v) for v in m['anchors']]
 return [distance(box[o:o+2],v) for o in (0,2) for v in a]+[distance(box[:2],box[2:4])]
class BoundEvaluator:
 def __init__(self,m,method):
  from functools import lru_cache
  self.m=m;self.method=method
  anchors=[tuple(I.point(x) for x in a) for a in m['anchors']]
  obs=[tuple(map(I.point,y)) for y in m['observations']]
  variances=[I.point(m['R'][j][j]) for j in range(9)]
  @lru_cache(maxsize=8192)
  def anchor_sum(part,offset):
   total=I.point('0')
   for k,a in enumerate(anchors):
    j=offset+k;d=distance(part,a);l,u=obs[j]
    total=I.add(total,I.divpos(gap(d,l,u),variances[j]))
   return total
  self.anchor_sum=anchor_sum;self.obs=obs;self.variances=variances
 def __call__(self,box):
  total=I.add(self.anchor_sum(box[:2],0),self.anchor_sum(box[2:4],4))
  if self.method=='N4':return total
  d=distance(box[:2],box[2:4]);l,u=self.obs[8]
  if self.method=='J5':term=I.square(I.sub((l[0],u[1]),I.add(d,box[4])))
  else:
   l=I.sub(l,I.point(self.m['bias_domain'][1]));u=I.sub(u,I.point(self.m['bias_domain'][0]));term=gap(d,l,u)
  return I.add(total,I.divpos(term,self.variances[8]))
def objective(box,m,method):return BoundEvaluator(m,method)(box)

def split(box,tol):
 w=[I.HI.divide(I.HI.subtract(b,a),D(t)) for (a,b),t in zip(box,tol)]
 j=max(range(len(box)),key=lambda k:(w[k],-k));a,b=box[j];mid=I.LO.divide(I.LO.add(a,b),D(2))
 if not a<mid<b:raise ArithmeticError('no representable split')
 left=list(box);right=list(box);left[j]=(a,mid);right[j]=(mid,b)
 return j,mid,tuple(left),tuple(right)
def solve(m,method,s,thresholds,clock=time.monotonic):
 validate(m,method,s,thresholds)
 domain=m['domain']+([m['bias_domain']] if method=='J5' else [])
 box=I.decode(domain);q=D(s['q']);tol=s['tolerance'][:len(box)]
 queue=deque([('',box)]);nodes=[];n=0;start=clock();termination='RESOLUTION_COMPLETE';failure=None;evaluate_bound=BoundEvaluator(m,method)
 while queue:
  if n>=s['max_boxes']:termination='BOX_BUDGET';break
  if clock()-start>=s['max_seconds']:termination='TIME_BUDGET';break
  if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>650*1024:termination='MEMORY_BUDGET';break
  path,b=queue.popleft();n+=1
  try:
   lo,hi=evaluate_bound(b)
   if not lo.is_finite() or not hi.is_finite() or lo>hi:raise ArithmeticError('invalid bound')
   if lo>q:status='OUTSIDE'
   elif hi<=q:status='INSIDE'
   elif all(I.HI.subtract(v,u)<=D(t) for (u,v),t in zip(b,tol)):status='UNDECIDED'
   else:
    j,mid,left,right=split(b,tol);queue.extend([(path+'0',left),(path+'1',right)])
    nodes.append(dict(path=path,box=I.encode(b),status='SPLIT',lower=str(lo),upper=str(hi),axis=j,mid=str(mid)));continue
   nodes.append(dict(path=path,box=I.encode(b),status=status,lower=str(lo),upper=str(hi)))
  except (ArithmeticError,ValueError) as e:
   failure=repr(e);termination='NUMERICAL_FAILURE';nodes.append(dict(path=path,box=I.encode(b),status='NUMERICAL_UNDECIDED',error=failure));break
 pending=[p for p,b in queue]
 for path,b in queue:nodes.append(dict(path=path,box=I.encode(b),status='PENDING'))
 kept=[n for n in nodes if n['status'] not in ('OUTSIDE','SPLIT')]
 return dict(nodes=nodes,processed=n,search_seconds=clock()-start,termination=termination,failure=failure,counts=dict(Counter(n['status'] for n in nodes)),queue=pending,empty_proved=not kept,dimension=len(box))
