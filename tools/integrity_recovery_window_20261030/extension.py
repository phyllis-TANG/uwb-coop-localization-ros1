"""Frozen 64s prefix plus independently seeded normal tail; no solver in precheck."""
import sys,copy,json,hashlib,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/integrity_validation_20261030'))
from experiment import make as old_make, simulate, digest, source_lock
import numpy as np
import scipy
OUT=ROOT/'docs/research/integrity_recovery_window_20261030'
TAIL_SEED=610301

def extend(condition):
 config,events,truth,receipt=old_make(5101,condition)
 old=json.loads((ROOT/f'docs/research/integrity_validation_20261030/units/5101_{condition}/INPUT.json').read_text())
 for key in ['config_sha256','truth_sha256','events_sha256','base_events_sha256']:
  if receipt[key]!=old[key]:raise RuntimeError(f'PREFIX_IDENTITY_FAILED {condition} {key}: actual={receipt[key]} expected={old[key]}')
 prefix=copy.deepcopy(events); original_truth=copy.deepcopy(truth)
 template=json.loads(simulate.CONFIG.read_text());rng=np.random.default_rng(TAIL_SEED);count=520
 # Draw fixed tail arrays per car: Odom then five independent raw range streams.
 draws={car:(rng.normal(size=(count,3))*np.array([.002,.002,.0008]),rng.normal(0,.04,(count,5))) for car in simulate.CARS}
 last={car:copy.deepcopy(next(e for e in reversed(events) if e['kind']=='odom' and e['vehicle_id']==car)) for car in simulate.CARS}
 tails=[]
 for j in range(count):
  i=1281+j;t=i*.05;stamp=simulate.EPOCH_NS+i*simulate.STEP_NS
  antenna={car:simulate.antenna_xyz(simulate.true_pose(t,car,template['models'][car]),template['models'][car]) for car in simulate.CARS}
  distance=float(np.linalg.norm(antenna['car1']-antenna['car2']))
  for ci,car in enumerate(simulate.CARS):
   model=template['models'][car];noise,ranges=draws[car]
   before=simulate.true_pose((i-1)*.05,car,model);after=simulate.true_pose(t,car,model)
   prev=np.array(last[car]['value']['pose']);body=simulate.rotation(-float(before[2]))@(after[:2]-before[:2])
   pose=np.r_[prev[:2]+simulate.rotation(float(prev[2]))@(body+noise[j,:2]),prev[2]+after[2]-before[2]+noise[j,2]]
   values={key:float(np.linalg.norm(antenna[car]-np.asarray(model['anchors_xyz_m'][key]))+ranges[j,k]) for k,key in enumerate(sorted(model['anchors_xyz_m']))}
   values['node_0' if car=='car1' else 'node_1']=distance+float(ranges[j,4])
   for ki,(kind,value) in enumerate([('odom',{'pose':pose.tolist()}),('uwb',values)]):
    e=copy.deepcopy(next(e for e in reversed(prefix) if e['kind']==kind and e['vehicle_id']==car))
    e.update(header_epoch_ns=stamp,receive_epoch_ns=stamp+(10+((7*i+5*(2*ci+ki))%31))*1_000_000,source_observation_id=f'{car}:{kind}:{i}',value=value)
    e['source_file_sha256']=digest(dict(parent=receipt['base_events_sha256'],tail_seed=TAIL_SEED,rule='v1-normal-tail-64.05-to90'))
    tails.append(e)
    if kind=='odom':last[car]=e
 tails.sort(key=lambda e:e['receive_epoch_ns'])
 for k,e in enumerate(tails,start=len(prefix)):e['record_index']=k
 events+=tails
 for t in range(65,91):
  cars={}
  for car in simulate.CARS:
   model=template['models'][car];pose=simulate.true_pose(t,car,model)
   cars[car]=dict(pose=pose.tolist(),antenna_xyz_m=simulate.antenna_xyz(pose,model).tolist())
  truth.append(dict(state_epoch_ns=simulate.EPOCH_NS+t*1_000_000_000,time_s=float(t),cars=cars))
 assert events[:len(prefix)]==prefix and truth[:65]==original_truth
 assert events[len(prefix)]['receive_epoch_ns']>prefix[-1]['receive_epoch_ns']
 return config,events,truth,dict(prefix=receipt,tail_seed=TAIL_SEED,tail_events_sha256=digest(tails),extended_events_sha256=digest(events),extended_truth_sha256=digest(truth),prefix_events=len(prefix))

def precheck():
 results={};pairs=[]
 for condition in ['nominal','wall_long']:
  c,e,t,r=extend(condition);pairs.append((c,e,t,r));results[condition]=r
 a,b=pairs;assert a[0]==b[0] and a[2]==b[2]
 n=a[3]['prefix_events'];assert a[1][n:]==b[1][n:]
 # Independent scalar Odom increment check at every new sample; no reset.
 import math
 rng=np.random.default_rng(TAIL_SEED);count=520
 for car in simulate.CARS:
  noise=rng.normal(size=(count,3))*np.array([.002,.002,.0008]);rng.normal(0,.04,(count,5))
  records=[x for x in a[1] if x['kind']=='odom' and x['vehicle_id']==car and x['header_epoch_ns']>=simulate.EPOCH_NS+64_000_000_000]
  template=json.loads(simulate.CONFIG.read_text())['models'][car]
  for j,(prev,cur) in enumerate(zip(records,records[1:])):
   old_t=(prev['header_epoch_ns']-simulate.EPOCH_NS)/1e9;new_t=(cur['header_epoch_ns']-simulate.EPOCH_NS)/1e9
   # Generator uses i*.05 exactly; retain that floating construction.
   old_t=(1280+j)*.05;new_t=(1281+j)*.05
   p=simulate.true_pose(old_t,car,template);q=simulate.true_pose(new_t,car,template);o=prev['value']['pose'];v=cur['value']['pose']
   dx,dy=q[0]-p[0],q[1]-p[1];bx=math.cos(p[2])*dx+math.sin(p[2])*dy+noise[j,0];by=-math.sin(p[2])*dx+math.cos(p[2])*dy+noise[j,1]
   expected=[o[0]+math.cos(o[2])*bx-math.sin(o[2])*by,o[1]+math.sin(o[2])*bx+math.cos(o[2])*by,o[2]+q[2]-p[2]+noise[j,2]]
   np.testing.assert_allclose(v,expected,rtol=0,atol=1e-14) # preregistered scalar-vs-BLAS check, not old-prefix acceptance.
 result=dict(status='PASS',units=results,tail_pair_exact=True,continuity_steps=1040,scalar_continuity_atol=1e-14,environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),source_sha256=source_lock())
 with (OUT/'PREFIX_CHECK.json').open('x') as f:json.dump(result,f,indent=2)
if __name__=='__main__':
 try:precheck()
 except Exception as e:
  with (OUT/'PREFIX_FAILED.json').open('x') as f:json.dump(dict(error=str(e),estimator_started=False),f,indent=2)
  raise
