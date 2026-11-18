"""All-bag observations. Reference/endpoints never enter the adapter."""
import copy
from fcommon import *
from inputs import portable
from two_car_updated_comparison import build_inputs

def make(case,raw=None):
 cfg=read(ROOT/'docs/research/field_moon1_integration/CONFIG.json')
 run=portable(case) if raw is None else copy.deepcopy(raw)
 # Last integer grid point must have an odom bracket in BOTH cars and UWB support.
 stop=min(run['odom'][c][-1][0] for c in CARS)
 run['duration_s']=float(np.floor(stop))
 # build_inputs takes 1..floor(duration)-1; preserve a one-second tail margin.
 model=cfg['model_cases'].get(case)
 if model is None:
  # Used only for the historical builder. Replaced below by observed wall geometry.
  model={'start_antenna_xyz_m':{'car1':[0,0,.17],'car2':[1,0,.20]},'initial_heading_deg':{'car1':0,'car2':0}}
 o=clean(build_inputs(run,model,cfg['field_protocol'],cfg['configuration'],cfg['calibrated_biases_m']))
 # For all bags, generate a deterministic no-truth initialization from wall ranges.
 # Linear sphere differences determine XY; a rigid Procrustes fit aligns local odom.
 for car in CARS:
  c=o['cars'][car];m=c['model'];points=[];valid=[]
  for i,row in enumerate(c['observations']):
   keys=sorted(row)
   if len(keys)<3:continue
   anchors=np.array([m['anchors_xyz_m'][k] for k in keys]);r=np.array([row[k]-m['range_bias_m'][k] for k in keys])
   xy=anchors[:,:2];z=(m['antenna_height_m']-anchors[:,2])**2
   A=2*(xy[1:]-xy[0]);b=r[0]**2-r[1:]**2+np.sum(xy[1:]**2,axis=1)-xy[0]@xy[0]+z[1:]-z[0]
   if np.linalg.matrix_rank(A)<2:continue
   points.append(np.linalg.lstsq(A,b,rcond=None)[0]);valid.append(i)
  if len(points)<3:raise ValueError('INSUFFICIENT_WALL_INITIALIZATION')
  local=np.array(c['local']);lever=np.array(m['base_to_antenna_body_xy_m'])
  la=local[:,:2]+np.array([rotation(y)@lever for y in local[:,2]])
  a=la[valid];b=np.array(points);ac=a-a.mean(0);bc=b-b.mean(0)
  if np.linalg.norm(ac)<1e-8:angle=0.
  else:angle=float(np.arctan2(np.sum(ac[:,0]*bc[:,1]-ac[:,1]*bc[:,0]),np.sum(ac*bc)))
  shift=b.mean(0)-a.mean(0)@rotation(angle).T
  initial=np.column_stack((local[:,:2]@rotation(angle).T+shift,local[:,2]+angle))
  c['initial']=initial.tolist()
 return o
