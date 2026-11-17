"""Certified projections and pointwise evaluation; never used to guide search."""
from fractions import Fraction as F
from itertools import product
from certificate import unpack,retained,root,bound,bias_at,contains

def encode(b):return [[str(a),str(z)] for a,z in b]
def projections(m,r):
 kept=retained(r);out={}
 for car,offset in [('p',0),('s',2)]:
  rects=sorted(set(unpack(n['box'])[offset:offset+2] for n in kept))
  inner=sorted(set(unpack(n['box'])[offset:offset+2] for n in kept if n['status']=='INSIDE'))
  unresolved=sorted(set(unpack(n['box'])[offset:offset+2] for n in kept if n['status']!='INSIDE'))
  if not rects:
   out[car]=dict(rectangles=[],inside_rectangles=[],unresolved_rectangles=[],hull=None,center=None,radius_upper_m=None,area_upper_m2='0',feasible_area_lower_m2='0',span_m=None,boundary_contact=False,branch_evidence={});continue
  hull=tuple((min(b[j][0] for b in rects),max(b[j][1] for b in rects)) for j in range(2));center=tuple((a+b)/2 for a,b in hull)
  area=lambda b:(b[0][1]-b[0][0])*(b[1][1]-b[1][0])
  area_upper=min(sum(map(area,rects)),area(hull))
  rad2=max(sum(max((v-center[j])**2 for v in b[j]) for j in range(2)) for b in rects)
  boundary=any(any(b[j][k]==F(m['domain'][offset+j][k]) for j in range(2) for k in (0,1)) for b in rects)
  evidence={}
  for label,test in [('negative_y',lambda b:b[1][0]<0),('positive_y',lambda b:b[1][1]>0)]:
   evidence[label]={'candidate_rectangles':sum(test(b) for b in rects),'certified_inside_rectangles':sum(test(b) for b in inner)}
  out[car]=dict(rectangles=[encode(b) for b in rects],inside_rectangles=[encode(b) for b in inner],unresolved_rectangles=[encode(b) for b in unresolved],hull=encode(hull),center=list(map(str,center)),radius_upper_m=str(root((rad2,rad2))[1]),area_upper_m2=str(area_upper),feasible_area_lower_m2=str(max(map(area,inner),default=F(0))),span_m=[str(b-a) for a,b in hull],boundary_contact=boundary,branch_evidence=evidence)
 return out

def audit_projection(m,r,proj):
 # Exact reconstruction covers every retained leaf, including PENDING.
 assert proj==projections(m,r)
 for car in ('p','s'):
  z=proj[car]
  if not z['rectangles']:continue
  c=list(map(F,z['center']));rr=F(z['radius_upper_m'])**2
  for b in map(unpack,z['rectangles']):
   assert all(sum((x-c[i])**2 for i,x in enumerate(v))<=rr for v in product(*b))
 return {'status':'PASS','cars':2}

def evaluate(m,method,s,r,e):
 pos=e['truth'][:4];box=tuple((F(x),F(x)) for x in pos)
 if method=='N4':
  l,u=bound(box,m,'N4');status='FEASIBLE_PROVED' if u<=F(s['q']) else 'EMPTY_PROVED' if l>F(s['q']) else 'UNKNOWN';bias=None
 else:
  bias=bias_at(pos,m,s['q']);status=bias['status']
 noise=e.get('noise')
 event=None
 if noise is not None:
  total=sum(F(x)**2/F(m['R'][j][j]) for j,x in enumerate(noise[:8 if method=='N4' else 9]));event={'quadratic':str(total),'holds':total<=F(s['q']),'df':s['df']}
 in_domain=all(F(a)<=F(x)<=F(b) for x,(a,b) in zip(pos,m['domain'])) and (method=='N4' or F(m['bias_domain'][0])<=F(e['truth'][4])<=F(m['bias_domain'][1]))
 joint=contains(r,pos)
 cars={car:any(all(a<=F(x)<=b for x,(a,b) in zip(pos[o:o+2],unpack(n['box'])[o:o+2])) for n in retained(r)) for car,o in [('p',0),('s',2)]}
 mirror=None
 if e.get('geometry')=='collinear':
  mirrored=[str(F(pos[0])),str(-F(pos[1])),str(F(pos[2])),str(-F(pos[3]))];mirror={'point':mirrored,'finite_joint_outer_contains':contains(r,mirrored)}
 return dict(simultaneous_mirror=mirror,truth_in_declared_domain=in_domain,noise_event=event,exact_joint_position_feasibility=status,bias_recovery=bias,finite_joint_outer_contains=joint,finite_car_projection_contains=cars)
