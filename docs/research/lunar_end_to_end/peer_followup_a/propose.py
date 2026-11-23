"""Numerical N4 boundary points; only independent rational checks count as proof."""
import json
import sys
from fractions import Fraction as F
from common import PILOT,HERE,CFG,obs
sys.path.insert(0,str(PILOT))
import run as pilot
import numpy as np
from scipy.optimize import minimize


def propose(rec):
    model=pilot.model_for(rec,'anchor_only')
    score=pilot.float_model(model,'N4')
    x0=np.array([float(F(v)) for xy in rec['center'] for v in xy])
    x0=minimize(score,x0,jac=True,method='BFGS').x
    h=np.array(list(map(lambda v:float(F(v)),rec['heights'])))
    viable={'type':'ineq','fun':lambda x:26-1e-6-score(x)[0],'jac':lambda x:-score(x)[1]}
    pts=[]
    for sign in (-1,1):
        def objective(x):
            d=x[:2]-x[2:]
            dist=np.sqrt(d@d+(h[0]-h[1])**2)
            return sign*dist,sign*np.r_[d,-d]/dist
        r=minimize(objective,x0,method='SLSQP',jac=True,constraints=[viable],options={'ftol':1e-12,'maxiter':200})
        pts.append(pilot.strings(r.x))
    return pts

if __name__=='__main__':
    (HERE/'exclusion_candidates.json').write_text(json.dumps({k:propose(obs(k)) for k in CFG['inputs']},indent=2)+'\n')
