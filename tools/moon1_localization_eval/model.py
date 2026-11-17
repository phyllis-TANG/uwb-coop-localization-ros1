"""Measurement-only six-epoch adapter. Height is fixed oracle input, not a state."""
import importlib.util
import numpy as np
from common import ROOT,clean,digest
spec=importlib.util.spec_from_file_location('frozen_xy_backend',ROOT/'tools/midterm_simulation_s2/prototype.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
FIELDS={'schema','frame','units','times_s','anchors_xyz_m','height_mode','heights_m','ranges_m','global_xy_increments_m','motion_sigmas_m','range_sigma_m','prior_center_xy_m','prior_sigma_m','initialization_offset_m','peer_direction'}

def validate(o):
 if set(o)!=FIELDS:raise ValueError('INVALID_SCHEMA missing/extra fields: '+str(sorted(set(o)^FIELDS)))
 if o['schema']!=1 or o['frame']!='moon_map' or o['units']!=['m','s'] or o['height_mode']!='height-oracle_world_vertical_1.16m':raise ValueError('INVALID_IDENTITY')
 if o['peer_direction']!='one_car1_to_car2':raise ValueError('INVALID_DIRECTION')
 shapes={'times_s':(6,),'anchors_xyz_m':(4,3),'heights_m':(6,2),'ranges_m':(54,), 'global_xy_increments_m':(5,2,2),'motion_sigmas_m':(2,), 'prior_center_xy_m':(2,2),'initialization_offset_m':(4,)}
 for k,shape in shapes.items():
  a=np.asarray(o[k],float)
  if a.shape!=shape or not np.isfinite(a).all():raise ValueError('INVALID_OBSERVATION '+k)
 if not np.all(np.diff(o['times_s'])>0):raise ValueError('INVALID_TIME')
 for k in ['range_sigma_m','prior_sigma_m']:
  if not np.isfinite(o[k]) or o[k]<=0:raise ValueError('INVALID_SCALE '+k)
 if np.any(np.array(o['motion_sigmas_m'])<=0) or np.any(np.array(o['ranges_m'])<=0):raise ValueError('INVALID_RANGE_OR_SCALE')
 return o

def prediction(q,anchors,heights):
 pts=np.column_stack((np.asarray(q[:24]).reshape(-1,2),np.asarray(heights).ravel())).reshape(6,2,3)
 n=len(q);values=[];jac=[]
 for t in range(6):
  for c in range(2):
   for anchor in anchors:
    d=pts[t,c]-anchor;r=np.linalg.norm(d)
    if r<=1e-12:raise ValueError('UNDEFINED_COINCIDENT_DISTANCE')
    row=np.zeros(n);row[4*t+2*c:4*t+2*c+2]=d[:2]/r;values.append(r);jac.append(row)
  d=pts[t,1]-pts[t,0];r=np.linalg.norm(d)
  if r<=1e-12:raise ValueError('UNDEFINED_COINCIDENT_PEER')
  row=np.zeros(n);row[4*t:4*t+2]=-d[:2]/r;row[4*t+2:4*t+4]=d[:2]/r
  if n==25:row[-1]=1
  values.append(r+(q[-1] if n==25 else 0));jac.append(row)
 return np.array(values),np.array(jac)

def problem(o,method):
 validate(o)
 if method not in ['M0','M1','M2']:raise ValueError('UNKNOWN_METHOD')
 n=25 if method=='M2' else 24
 keep=np.ones(54,bool)
 if method=='M0':keep[legacy.PEER]=False
 anchors=np.array(o['anchors_xyz_m']);height=np.array(o['heights_m']);y=np.array(o['ranges_m'])[keep]
 motion=np.array(o['global_xy_increments_m']).ravel();sigma=np.tile(np.repeat(o['motion_sigmas_m'],2),5)
 prior=np.zeros((4,n));prior[:,:4]=np.eye(4)
 def evaluate(q):
  q=np.asarray(q,float)
  if q.shape!=(n,) or not np.isfinite(q).all():raise ValueError('INVALID_STATE')
  value,j=prediction(q,anchors,height)
  # Exact unchanged six-epoch global displacement operator from frozen backend.
  mv,mj=legacy.pr97.movement(q if n==25 else np.r_[q,0.])
  return np.r_[(value[keep]-y)/o['range_sigma_m'],(mv-motion)/sigma,(q[:4]-np.array(o['prior_center_xy_m']).ravel())/o['prior_sigma_m']], np.vstack([j[keep]/o['range_sigma_m'],mj[:,:n]/sigma[:,None],prior/o['prior_sigma_m']])
 center=np.array(o['prior_center_xy_m']).ravel()
 start=np.vstack([center,center+np.cumsum(np.array(o['global_xy_increments_m']).reshape(5,4),axis=0)])+np.array(o['initialization_offset_m'])
 start=np.r_[start.ravel(),0.] if n==25 else start.ravel()
 receipt={k:v for k,v in o.items() if k!='ranges_m'};receipt['used_ranges_m']=y.tolist();receipt['method']=method
 return evaluate,start,digest(receipt)

def information(j,tol):
 out=legacy.information(j,tol)
 s=np.array(out['singular_values']);out['condition_scaled']=float(s[0]/s[-1]) if out['rank']==j.shape[1] else None
 out['nullity']=j.shape[1]-out['rank'];return out
