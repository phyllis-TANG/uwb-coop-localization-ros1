"""Find candidate anchor-feasible endpoints of the inter-car slant interval."""
import json
from fractions import Fraction as F
from scipy.optimize import minimize
from run import OUT, pilot, np


def candidates(rec):
    model = pilot.model_for(rec,'anchor_only')
    evaluate = pilot.float_model(model,'N4')
    x0 = [float(F(x)) for row in rec['center'] for x in row]
    constraint = dict(type='ineq',fun=lambda x:26-1e-6-evaluate(x)[0],
                      jac=lambda x:-evaluate(x)[1])
    for sign in (-1,1):
        def objective(x):
            delta = x[:2]-x[2:]
            return sign*(delta@delta), sign*2*np.r_[delta,-delta]
        fit = minimize(objective,x0,jac=True,constraints=[constraint],method='SLSQP',
                       options=dict(ftol=1e-12,maxiter=200))
        yield pilot.strings(fit.x)


if __name__=='__main__':
    for path in sorted((OUT/'observations').glob('*.json')):
        pilot.save('peer_witnesses/'+path.name,list(candidates(json.loads(path.read_text()))))
