"""Independent exact rational checker. Does not import solver or its bound."""
from fractions import Fraction as F
from math import isqrt
from collections import Counter

def unpack(box):return tuple(tuple(map(F,x)) for x in box)
def point(x):return F(x),F(x)
def plus(a,b):return a[0]+b[0],a[1]+b[1]
def minus(a,b):return a[0]-b[1],a[1]-b[0]
def square(a):return (F(0) if a[0]<=0<=a[1] else min(x*x for x in a),max(x*x for x in a))
def root(a):
 scale=10**45;out=[]
 for i,x in enumerate(a):
  assert x>=0;k=isqrt(x.numerator*scale*scale//x.denominator)
  if i and k*k*x.denominator!=x.numerator*scale*scale:k+=1
  out.append(F(k,scale))
 return tuple(out)
def distance(a,b):return root(plus(square(minus(a[0],b[0])),square(minus(a[1],b[1]))))
def distance_to_interval(d,l,u):
 g=lambda x:max(l-x,x-u,F(0))**2
 return (F(0) if d[0]<=u and d[1]>=l else min(map(g,d)),max(map(g,d)))
class RationalEvaluator:
 def __init__(self,m,method):
  from functools import lru_cache
  self.m=m;self.method=method
  anchors=[tuple(point(x) for x in a) for a in m['anchors']]
  obs=[tuple(map(F,y)) for y in m['observations']];v=[F(m['R'][j][j]) for j in range(9)]
  @lru_cache(maxsize=8192)
  def anchor_sum(part,offset):
   low=high=F(0)
   for k,a in enumerate(anchors):
    j=offset+k;l,u=obs[j];term=distance_to_interval(distance(part,a),l,u)
    low+=term[0]/v[j];high+=term[1]/v[j]
   return low,high
  self.anchor_sum=anchor_sum;self.obs=obs;self.v=v
 def __call__(self,box):
  lo,hi=plus(self.anchor_sum(box[:2],0),self.anchor_sum(box[2:4],4))
  if self.method=='N4':return lo,hi
  d=distance(box[:2],box[2:4]);l,u=self.obs[8]
  if self.method=='J5':term=square(minus((l,u),plus(d,box[4])))
  else:
   l-=F(self.m['bias_domain'][1]);u-=F(self.m['bias_domain'][0]);term=distance_to_interval(d,l,u)
  return lo+term[0]/self.v[8],hi+term[1]/self.v[8]
def bound(box,m,method):return RationalEvaluator(m,method)(box)

def retained(r):return [n for n in r['nodes'] if n['status'] not in ('OUTSIDE','SPLIT')]
def audit(m,method,s,r):
 assert method in ('J5','P4','N4');dim=5 if method=='J5' else 4
 assert r['dimension']==dim
 nodes={n['path']:n for n in r['nodes']};assert len(nodes)==len(r['nodes'])
 domain=unpack(m['domain']+([m['bias_domain']] if method=='J5' else []));assert unpack(nodes['']['box'])==domain
 q=F(s['q']);stack=[''];seen=set();certs=0;evaluate_bound=RationalEvaluator(m,method)
 while stack:
  path=stack.pop();assert path not in seen;seen.add(path);n=nodes[path];b=unpack(n['box']);assert len(b)==dim and all(a<=z for a,z in b)
  if n['status']=='SPLIT':
   j=n['axis'];mid=F(n['mid']);assert 0<=j<dim and b[j][0]<mid<b[j][1]
   for side in (0,1):
    child=list(b);child[j]=(b[j][0],mid) if side==0 else (mid,b[j][1]);cp=path+str(side)
    assert unpack(nodes[cp]['box'])==tuple(child);stack.append(cp)
  elif n['status'] in ('OUTSIDE','INSIDE'):
   lo,hi=evaluate_bound(b);assert lo>q if n['status']=='OUTSIDE' else hi<=q;certs+=1
  else:assert n['status'] in ('PENDING','UNDECIDED','NUMERICAL_UNDECIDED')
 assert seen==set(nodes)
 assert sorted(r['queue'])==sorted(n['path'] for n in nodes.values() if n['status']=='PENDING')
 assert r['counts']==dict(Counter(n['status'] for n in nodes.values()))
 assert r['processed']==sum(n['status']!='PENDING' for n in nodes.values())
 assert r['empty_proved']==(len(retained(r))==0)
 return dict(status='PASS',nodes=len(nodes),certified_leaves=certs,retained=len(retained(r)))

def contains(r,pos):
 assert len(pos)==4
 return any(all(a<=F(x)<=b for x,(a,b) in zip(pos,unpack(n['box'])[:4])) for n in retained(r))
def bias_at(pos,m,q):
 """All feasible b at one fixed joint position, inner/outer rational bounds."""
 p=tuple(point(x) for x in pos);lo,hi=bound(p,m,'N4');Llo=F(q)-hi;Lhi=F(q)-lo
 if Lhi<0:return dict(status='EMPTY_PROVED',outer=None,inner=None)
 rad=root((max(F(0),Llo)*F(m['R'][8][8]),Lhi*F(m['R'][8][8])))
 d=distance(p[:2],p[2:4]);l,u=map(F,m['observations'][8]);b0,b1=map(F,m['bias_domain'])
 outer=max(b0,l-d[1]-rad[1]),min(b1,u-d[0]+rad[1])
 if outer[0]>outer[1]:return dict(status='EMPTY_PROVED',outer=None,inner=None)
 inner=None
 if Llo>=0:
  z=max(b0,l-d[0]-rad[0]),min(b1,u-d[1]+rad[0])
  if z[0]<=z[1]:inner=list(map(str,z))
 return dict(status='FEASIBLE_PROVED' if inner is not None else 'UNKNOWN',outer=list(map(str,outer)),inner=inner)
