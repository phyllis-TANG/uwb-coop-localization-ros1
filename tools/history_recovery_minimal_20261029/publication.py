"""Post-processing algebra only; never feeds the graph or claims posterior covariance."""
import math
import numpy as np

def antennas(pose,config):
 a=[]
 for i,c in enumerate(('car1','car2')):
  x,y,w=pose[3*i:3*i+3];lx,ly=config['models'][c]['base_to_antenna_body_xy_m']
  a.append([x+math.cos(w)*lx-math.sin(w)*ly,y+math.sin(w)*lx+math.cos(w)*ly])
 return np.array(a)

def publish(row,reference,config,budgets):
 p=row['pose'];q=reference['pose']
 if not reference['accepted_graph'] or q is None or not np.isfinite(q).all():return dict(pose=q,mode='unknown',budget_certified=False,covariance=None)
 if not row['accepted_graph'] or p is None or not np.isfinite(p).all():return dict(pose=q,mode='reference_fallback',budget_certified=True,covariance=None)
 x=np.array(p,float);a=antennas(x,config);b=antennas(q,config);d=a-b
 for i,limit in enumerate(budgets):
  if limit<0:raise ValueError('Negative budget')
  n=np.linalg.norm(d[i]);target=b[i]+d[i]*min(1.,limit/n) if n else b[i]
  x[3*i:3*i+2]+=target-a[i]
 return dict(pose=x.tolist(),mode='post_clip',budget_certified=True,covariance=None)
