"""Strict measurement-only wrapper around the unchanged historical SE(2) model."""
import numpy as np
from common import clean
from two_car_updated_comparison import JointObjective,CARS

def objective(o,joint):
 if set(o)!={'times','cars','peers','peer_sigma_m'}: raise ValueError('unexpected measurement fields')
 t=np.asarray(o['times']);n=len(t)
 if n<3 or not np.isfinite(t).all() or not np.all(np.diff(t)>0): raise ValueError('invalid times')
 if set(o['cars'])!=set(CARS): raise ValueError('invalid cars')
 for car in CARS:
  c=o['cars'][car]
  if set(c)!={'model','local','initial','observations','range_sample_counts','nonpositive_corrected_samples'}: raise ValueError('unexpected car fields')
  if set(c['model'])!={'anchors_xyz_m','range_bias_m','start_antenna_xyz_m','initial_heading_deg','base_to_antenna_body_xy_m','antenna_height_m','graph_parameters'}: raise ValueError('unexpected model fields')
  for k in ['initial','local']:
   a=np.asarray(c[k]);
   if a.shape!=(n,3) or not np.isfinite(a).all(): raise ValueError('invalid pose')
  if len(c['observations'])!=n or len(o['peers'])!=n: raise ValueError('invalid observations')
  for row in c['observations']:
   if set(row)-set(c['model']['anchors_xyz_m']) or any(not np.isfinite(v) or v<=0 for v in row.values()): raise ValueError('invalid wall range')
 if not np.isfinite(o['peer_sigma_m']) or o['peer_sigma_m']<=0: raise ValueError('invalid peer scale')
 for row in o['peers']:
  if set(row)!={'range_m','directions_m','direction_counts'}: raise ValueError('unexpected peer fields')
  if row['range_m'] is not None and (not np.isfinite(row['range_m']) or row['range_m']<=0): raise ValueError('invalid peer range')
 return JointObjective(o,joint)
