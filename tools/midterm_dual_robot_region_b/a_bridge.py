"""Exact-format adapter to immutable A checker; no A pruning code in B search."""
from functools import lru_cache
from fractions import Fraction as F
from math import isqrt
from common import load_module,Path,read,sha,digest
from certificate import unpack
MODE={'J5':'5d','P4':'4d','N4':'no_peer'}
@lru_cache(maxsize=1)
def a_module(source_root):return load_module('dual_a_locked_core',Path(source_root)/'tools/midterm_dual_robot_contract_a/core.py')
def root30(x):
 scale=10**30;k=isqrt(x.numerator*scale*scale//x.denominator);lo=F(k,scale)
 return lo,lo if lo*lo==x else F(k+1,scale)
def protocol_projections(nodes):
 kept=[n for n in nodes if n['kind'] in ('INSIDE','UNDECIDED','PENDING')];out={}
 for car,o in [('p',0),('s',2)]:
  rects=[dict(leaf=n['id'],box=n['box'][o:o+2]) for n in kept]
  if not rects:out[car]=dict(rectangles=[],center=None,radius=None,radius_squared=None,area_upper='0');continue
  bs=[unpack(r['box']) for r in rects];lo=[min(b[j][0] for b in bs) for j in range(2)];hi=[max(b[j][1] for b in bs) for j in range(2)];c=[(a+z)/2 for a,z in zip(lo,hi)]
  rad2=max(sum(max((v-c[j])**2 for v in b[j]) for j in range(2)) for b in bs)
  area=min((hi[0]-lo[0])*(hi[1]-lo[1]),sum((b[0][1]-b[0][0])*(b[1][1]-b[1][0]) for b in bs))
  out[car]=dict(rectangles=rects,center=list(map(str,c)),radius=str(root30(rad2)[1]),radius_squared=str(rad2),area_upper=str(area))
 return out

def protocol_recovery(x,point):
 # Independent point-distance derivation at A's exact declared sqrt precision.
 vals=list(map(F,point));obs=unpack(x['observation_intervals']);variance=list(map(F,x['noise_model']['variance']));lo=hi=F(0)
 for o in (0,2):
  for k in range(4):
   anchor=list(map(F,x['anchor_map'][f'a{k}']));d=root30(sum((vals[o+j]-anchor[j])**2 for j in range(2)));j=o*2+k;l,u=obs[j]
   gap=lambda z:max(l-z,z-u,F(0));lower=max(F(0),l-d[1],d[0]-u);upper=max(map(gap,d));lo+=lower**2/variance[j];hi+=upper**2/variance[j]
 q=F(x['threshold_certificate']['tau']);b0,b1=map(F,x['domains'][4]);l,u=obs[8];d=root30(sum((vals[j]-vals[j+2])**2 for j in range(2)))
 def clip(a,b):
  a=max(a,b0);b=min(b,b1);return None if a>b else list(map(str,(a,b)))
 if q<lo:return dict(outer=None,inner=None,status='EMPTY_PROVED')
 ro=root30(variance[8]*(q-lo))[1];outer=clip(l-d[1]-ro,u-d[0]+ro);inner=None
 if q>=hi:
  ri=root30(variance[8]*(q-hi))[0];inner=clip(l-d[0]-ri,u-d[1]+ri)
 return dict(outer=outer,inner=inner,status='EMPTY_PROVED' if outer is None else 'FEASIBLE_PROVED' if inner is not None else 'UNDECIDED')

def make_certificate(case,method,settings,result,projection,cost=None):
 x=case['a_input'];nodes=[]
 for n in result['nodes']:
  if n['status']=='NUMERICAL_UNDECIDED':raise RuntimeError('A_SCHEMA_NUMERICAL_STATE_UNSUPPORTED')
  z=dict(id=n['path'],box=n['box'],kind=n['status'])
  if n['status']=='SPLIT':z.update(axis=n['axis'],cut=n['mid'],children=[n['path']+'0',n['path']+'1'])
  nodes.append(z)
 mode=MODE[method];count={k:sum(n['kind']==k for n in nodes) for k in ('SPLIT','OUTSIDE','INSIDE','UNDECIDED','PENDING')};keep=[n for n in nodes if n['kind'] not in ('SPLIT','OUTSIDE')]
 contact=any(any(F(a)==F(c) or F(b)==F(d) for (a,b),(c,d) in zip(n['box'],x['domains'])) for n in keep)
 ap=protocol_projections(nodes);rec=[]
 if method=='P4' and keep:
  pos=ap['p']['center']+ap['s']['center'];rec=[dict(point=pos,result=protocol_recovery(x,pos))]
 threshold=dict(x['threshold_certificate'])
 if method=='N4':threshold.update(id='DUAL-A-V1-CHI2-8-CHERNOFF',dimension=8,tau='24')
 if cost is None:cost=dict(processed_nodes=result['processed'],search_seconds=str(result['search_seconds']),certificate_write_seconds='0',peak_rss_bytes='0',distance_evaluations=result.get('distance_evaluations',0))
 return dict(schema_version='DUAL-A-V1',input_hash=x['input_hash'],source_commit=x['source_commit'],mode=mode,measurement_ids=x['measurement_ids'][:8 if method=='N4' else 9],threshold_certificate=threshold,root='',nodes=nodes,queue=result['queue'],projections=ap,counts=count,status='EMPTY_IN_DECLARED_DOMAIN' if not keep else 'BUDGET_OUTER' if result['queue'] else 'OUTER_CERTIFIED',domain_contact=contact,internal_semantics={'J5':'forall_state_exists_observation','P4':'forall_position_exists_bias_and_observation','N4':'forall_position_exists_observation'}[method],bias_recovery=rec,cost=cost)
def audit_a(case,method,settings,result,projection,lock):
 a=a_module(lock['source_root']);cert=make_certificate(case,method,settings,result,projection);z=a.check(case['a_input'],cert)
 return dict(status='PASS' if z['certificate_valid'] else 'FAIL',checker_sha256=lock['files']['tools/midterm_dual_robot_contract_a/core.py'],validation=z)
