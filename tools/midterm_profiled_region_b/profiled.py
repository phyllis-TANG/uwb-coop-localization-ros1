"""Exact existential profile, evaluated by outward interval extensions."""
from common import I,OLD,projected
D=I.D

def distance_interval(box,anchor):
 return I.sqrt(I.add(I.square(I.sub(box[0],I.point(anchor[0]))),I.square(I.sub(box[1],I.point(anchor[1])))))
def gap_squared(t,l,u):
 # l and u enclose the exact endpoints of the target interval.
 lo=max(D(0),I.LO.subtract(l[0],t[1]),I.LO.subtract(t[0],u[1]))
 hi=max(D(0),I.HI.subtract(l[1],t[0]),I.HI.subtract(t[1],u[0]))
 return I.LO.multiply(lo,lo),I.HI.multiply(hi,hi)
def bound(box,m):
 z=I.point('0')
 for j,a in enumerate(m['anchors']):
  t=distance_interval(box,a);l=I.point(m['observations'][j][0]);u=I.point(m['observations'][j][1])
  if j==m['affected_index']:
   l=I.sub(l,I.point(m['bias_interval'][1]));u=I.sub(u,I.point(m['bias_interval'][0]))
  z=I.add(z,I.divpos(gap_squared(t,l,u),I.square(I.point(m['sigma'][j]))))
 return z

def solve(m,settings,**kwargs):return OLD.solve(projected(m),settings,bound=bound,**kwargs)

def recover_bias(position,m,q='9.488'):
 """Certified outer/inner bounds for feasible b at ONE exact position, not box hull."""
 p=tuple(I.point(x) for x in position);s=I.point('0');d4=None
 for j,a in enumerate(m['anchors']):
  d=distance_interval(p,a)
  if j==m['affected_index']:d4=d;continue
  s=I.add(s,I.divpos(gap_squared(d,I.point(m['observations'][j][0]),I.point(m['observations'][j][1])),I.square(I.point(m['sigma'][j]))))
 rem=I.sub(I.point(q),s);B=projected(m)['bias_interval'];B=list(map(D,B))
 if rem[1]<0:return dict(status='EMPTY_PROVED',outer=None,inner=None)
 rhi=I.HI.multiply(D(m['sigma'][3]),I.root_bound(rem[1],True))
 lo=max(B[0],I.LO.subtract(I.LO.subtract(D(m['observations'][3][0]),d4[1]),rhi))
 hi=min(B[1],I.HI.add(I.HI.subtract(D(m['observations'][3][1]),d4[0]),rhi))
 if lo>hi:return dict(status='EMPTY_PROVED',outer=None,inner=None)
 inner=None
 if rem[0]>=0:
  rlo=I.LO.multiply(D(m['sigma'][3]),I.root_bound(rem[0]))
  il=max(B[0],I.HI.subtract(I.HI.subtract(D(m['observations'][3][0]),d4[0]),rlo))
  ih=min(B[1],I.LO.add(I.LO.subtract(D(m['observations'][3][1]),d4[1]),rlo))
  if il<=ih:inner=[str(il),str(ih)]
 return dict(status='FEASIBLE_PROVED' if inner is not None else 'UNDECIDED',outer=[str(lo),str(hi)],inner=inner)
