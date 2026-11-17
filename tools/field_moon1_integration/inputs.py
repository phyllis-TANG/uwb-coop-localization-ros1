"""PR128 portable observation adapter; no evaluation reference is read."""
import gzip,math
import numpy as np
from common import ROOT,SOURCE,read
from two_car_updated_comparison import CARS,TAGS,unique_positive_ranges,build_inputs
OLD=ROOT/'docs/field_tests/two_car_updated_comparison_20261022'
def portable(case):
 source=next(x for x in read(SOURCE/'SOURCES.json') if x['case']==case)
 run={'odom':{c:[] for c in CARS},'uwb':{c:[] for c in CARS},'duration_s':21.0}
 with gzip.open(SOURCE/case/'measurements.jsonl.gz','rt') as f:
  for line in f:
   d=__import__('json').loads(line);car=d['topic'].split('/')[1]
   t=d['receipt_ns']*1e-9-source['bag_origin_ns']*1e-9
   if d['kind']=='odom':
    q=np.asarray(d['quaternion_xyzw'],float);norm=np.linalg.norm(q)
    if not np.isfinite(norm) or not .5<=norm<=1.5: raise ValueError('invalid quaternion')
    x,y,z,w=q/norm;xy=d['position_m'][:2]
    yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
    if not np.isfinite([*xy,yaw]).all(): raise ValueError('invalid odom')
    run['odom'][car].append([t,*xy,yaw])
   elif d['kind']=='uwb':
    if d['tag_id']!=TAGS[car]: raise ValueError('tag identity')
    vals,_=unique_positive_ranges((r['anchor_id'],r['range_m'] if r['range_m'] is not None else float('nan')) for r in d['ranges'])
    run['uwb'][car].append((t,vals))
 for car in CARS:
  if len(run['odom'][car])<2 or np.any(np.diff(np.array(run['odom'][car])[:,0])<=0): raise ValueError('odom order')
 return run

def prepare(case,run=None):
 cfg=read(ROOT/'docs/research/field_moon1_integration/CONFIG.json')
 p=cfg['field_protocol']; model=cfg['model_cases'][case]
 return build_inputs(portable(case) if run is None else run,model,p,cfg['configuration'],cfg['calibrated_biases_m'])
