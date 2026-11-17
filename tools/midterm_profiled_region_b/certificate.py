"""Independent exact-rational exclusion certificates; no search import."""
from fractions import Fraction as F
from common import OC,projected

def rational_profile(box,m):
 z=F(0),F(0)
 for j,a in enumerate(m['anchors']):
  d=OC.root(OC.plus(OC.sq(OC.minus(box[0],OC.point(a[0]))),OC.sq(OC.minus(box[1],OC.point(a[1])))))
  l,u=map(F,m['observations'][j])
  if j==m['affected_index']:
   blo,bhi=map(F,m['bias_interval']);l-=bhi;u-=blo
  # Independent distance-to-interval clipping; convex endpoint maximum.
  g=lambda t:max(l-t,t-u,F(0))**2
  lower=F(0) if d[0]<=u and d[1]>=l else min(g(t) for t in d)
  upper=max(g(t) for t in d);sig=F(m['sigma'][j])
  z=z[0]+lower/sig**2,z[1]+upper/sig**2
 return z

def audit(m,s,r,method):
 if method=='OLD':return OC.audit(m,s,r)
 m=projected(m);nodes={n['path']:n for n in r['nodes']};assert len(nodes)==len(r['nodes'])
 assert OC.unpack(nodes['']['box'])==OC.unpack(m['domain'])
 seen=set();stack=[''];q=F(s['q']);certs=0
 while stack:
  path=stack.pop();assert path not in seen;seen.add(path);n=nodes[path];b=OC.unpack(n['box'])
  if n['status']=='SPLIT':
   j=n['axis'];mid=F(n['mid']);assert b[j][0]<mid<b[j][1]
   for v in (0,1):
    child=list(b);child[j]=(b[j][0],mid) if v==0 else (mid,b[j][1]);cp=path+str(v)
    assert OC.unpack(nodes[cp]['box'])==tuple(child);stack.append(cp)
  elif n['status'] in ('OUTSIDE','INSIDE'):
   l,u=rational_profile(b,m);assert l>q if n['status']=='OUTSIDE' else u<=q;certs+=1
  else:assert n['status'] in ('UNDECIDED','PENDING','NUMERICAL_UNDECIDED')
 assert seen==set(nodes)
 assert r['empty_proved']==(len(OC.retained(r))==0)
 assert r['processed']==sum(n['status']!='PENDING' for n in nodes.values())
 return dict(status='PASS',nodes=len(nodes),certified_leaves=certs,retained=len(OC.retained(r)))

def xy_contains(r,p):return any(all(a<=F(x)<=b for x,(a,b) in zip(p,OC.unpack(n['box'])[:2])) for n in OC.retained(r))

def bias_reference(position,m,q):
 # Rational enclosures for a point's feasible interval. Independent arithmetic.
 p=tuple(OC.point(x) for x in position);s=F(0),F(0);ds=[]
 for j,a in enumerate(m['anchors']):
  d=OC.root(OC.plus(OC.sq(OC.minus(p[0],OC.point(a[0]))),OC.sq(OC.minus(p[1],OC.point(a[1])))));ds.append(d)
  if j==3:continue
  l,u=map(F,m['observations'][j]);g=lambda x:max(l-x,x-u,F(0))**2
  lo=F(0) if d[0]<=u and d[1]>=l else min(map(g,d));hi=max(map(g,d));sig=F(m['sigma'][j]);s=s[0]+lo/sig**2,s[1]+hi/sig**2
 upper=F(q)-s[0];lower=F(q)-s[1]
 if upper<0:return None,None
 d=ds[3];l,u=map(F,m['observations'][3]);b0,b1=map(F,projected(m)['bias_interval']);sig=F(m['sigma'][3]);rad=OC.root((max(F(0),lower),upper))
 outer=max(b0,l-d[1]-sig*rad[1]),min(b1,u-d[0]+sig*rad[1])
 if outer[0]>outer[1]:return None,None
 inner=None
 if lower>=0:
  inner=max(b0,l-d[0]-sig*rad[0]),min(b1,u-d[1]+sig*rad[0])
  if inner[0]>inner[1]:inner=None
 return outer,inner
