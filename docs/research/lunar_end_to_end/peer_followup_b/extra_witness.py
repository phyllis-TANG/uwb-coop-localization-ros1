"""Seek anchor-admissible states with extreme peer slant for undecided comparisons."""
import json
import numpy as np
from scipy.optimize import minimize
from experiment import OUT, pilot

for path in sorted((OUT/'observations').glob('*.json')):
    rec=json.loads(path.read_text())
    model=pilot.model_for(rec,'anchor_only')
    evaluate=pilot.float_model(model,'N4')
    x0=np.array([float(pilot.F(v)) for pair in rec['center'] for v in pair])
    start=minimize(evaluate,x0,jac=True).x
    constraint=dict(type='ineq',fun=lambda x:26-1e-6-evaluate(x)[0],jac=lambda x:-evaluate(x)[1])
    candidates=[]
    for sign in (-1,1):
        def objective(x):
            delta=x[:2]-x[2:]
            return sign*(delta@delta),sign*2*np.r_[delta,-delta]
        x=minimize(objective,start,jac=True,method='SLSQP',constraints=[constraint],
                   options=dict(maxiter=100,ftol=1e-12)).x
        candidates.append(pilot.strings(x))
    pilot.save('slant_candidates/'+rec['id']+'.json',candidates)
