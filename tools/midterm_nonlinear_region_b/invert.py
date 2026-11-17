"""Whole-domain box inversion. Only certified lower bounds discard boxes."""
import time
from collections import deque,Counter
from interval import D,LO,HI,point,add,sub,square,sqrt,divpos,decode,encode

def objective(box,model):
 total=point('0')
 if model.get('affine'):
  predictions=[]
  for row,offset in zip(model['A'],model['offset']):
   from interval import mul
   z=point(offset)
   for a,x in zip(row,box):z=add(z,mul(point(a),x))
   predictions.append(z)
 else:
  predictions=[]
  for k,a in enumerate(model['anchors']):
   dist=sqrt(add(square(sub(box[0],point(a[0]))),square(sub(box[1],point(a[1])))))
   if k==model['affected_index']:
    dist=add(dist,box[2] if model['unknown_bias'] else point(model['known_bias']))
   predictions.append(dist)
 for h,y,s in zip(predictions,model['observations'],model['sigma']):
  r=divpos(sub((D(y[0]),D(y[1])),h),point(s))
  total=add(total,square(r))
 return total

def bisect(box,tolerance):
 widths=[HI.divide(HI.subtract(b,a),D(t)) for (a,b),t in zip(box,tolerance)]
 j=max(range(len(box)),key=lambda k:(widths[k],-k))
 a,b=box[j];m=LO.divide(LO.add(a,b),D(2))
 if not a<m<b:raise ArithmeticError('no representable split')
 l=list(box);r=list(box);l[j]=(a,m);r[j]=(m,b)
 return j,m,tuple(l),tuple(r)

def solve(model,settings,clock=time.monotonic,bound=objective):
 box=decode(model['domain']);q=D(settings['q']);tol=settings['tolerance'][:len(box)]
 queue=deque([('',box)]);nodes=[];n=0;start=clock();termination='RESOLUTION_COMPLETE';failure=None
 while queue:
  if n>=settings['max_boxes']:termination='BOX_BUDGET';break
  if clock()-start>=settings['max_seconds']:termination='TIME_BUDGET';break
  path,b=queue.popleft();n+=1
  try:
   lo,hi=bound(b,model)
   if not lo.is_finite() or not hi.is_finite() or lo>hi:raise ArithmeticError('invalid interval bound')
   if lo>q:status='OUTSIDE'
   elif hi<=q:status='INSIDE'
   elif all(HI.subtract(v,u)<=D(t) for (u,v),t in zip(b,tol)):status='UNDECIDED'
   else:
    j,m,l,r=bisect(b,tol);queue.extend([(path+'0',l),(path+'1',r)])
    nodes.append(dict(path=path,box=encode(b),status='SPLIT',lower=str(lo),upper=str(hi),axis=j,mid=str(m)));continue
   nodes.append(dict(path=path,box=encode(b),status=status,lower=str(lo),upper=str(hi)))
  except (ArithmeticError,ValueError) as e:
   nodes.append(dict(path=path,box=encode(b),status='NUMERICAL_UNDECIDED',error=repr(e)))
   termination='NUMERICAL_FAILURE';failure=repr(e);break
 for path,b in queue:nodes.append(dict(path=path,box=encode(b),status='PENDING'))
 elapsed=clock()-start
 kept=[z for z in nodes if z['status'] not in ['OUTSIDE','SPLIT']]
 return dict(nodes=nodes,processed=n,elapsed_seconds=elapsed,termination=termination,failure=failure,
             counts=dict(Counter(z['status'] for z in nodes)),empty_proved=not kept,
             boundary_contact=any(any(a==u or b==v for (a,b),(u,v) in zip(decode(z['box']),box)) for z in kept))
