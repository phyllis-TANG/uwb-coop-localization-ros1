"""Independent batch square-root least squares at the exported linearizations."""
import json
import sys
from statistics import NormalDist
import numpy as np

data=json.load(open(sys.argv[1]))
steps=data['history']
n=len(steps)
M=[]
rhs=[]
columns=[]
for i,step in enumerate(steps):
    sl=slice(13*i,13*i+13)
    H=np.asarray(step['H'])
    # x_i - x_previous = odometry; first attached to the exported first prior.
    motion=np.zeros((13,13*n))
    motion[:,sl]=np.eye(13)
    if i:
        motion[:,13*i-13:13*i]=-np.eye(13)
    sd=np.sqrt(np.diag(data['Q'] if i else step['prior_cov']))
    M.extend(motion/sd[:,None])
    rhs.extend((np.r_[step['u'],np.zeros(9)] if i else step['prior'])/sd)
    design=np.zeros((9,13*n))
    design[:,sl]=H
    columns.extend(range(len(M),len(M)+9))
    M.extend(design/.04)
    rhs.extend((np.asarray(step['innovation'])+H@step['prior'])/.04)
U,s,Vt=np.linalg.svd(M,full_matrices=False)
inv=(Vt.T/s)@U.T
car=inv[-13:-11]
cov=car@car.T
xy=car@rhs
bias=.02*np.abs(car[:,columns]/.04).sum(axis=1)
errors={}
for key,v in data['cars'][0]['variants'].items():
    k=NormalDist().inv_cdf(1-v['axis_alpha']/2)
    bound=bias if key=='history_preallocated' else .02*np.abs(car[:,columns[-9:]]/.04).sum(axis=1)
    result=float(np.linalg.norm(bound+k*np.sqrt(np.diag(cov))))
    errors[key]=result-v['HCPL']
    assert abs(errors[key])<1e-12
np.testing.assert_allclose(xy,data['cars'][0]['published_antenna_xy'],atol=1e-12,rtol=0)
print(json.dumps(dict(xy=xy.tolist(),bias=bias.tolist(),covariance=cov.tolist(),HCPL_difference_m=errors),indent=2))
