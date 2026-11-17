"""Analytic matrix checks and frozen-objective parity on saved development data."""
from common import *
import importlib.util

def run():
    u=read(OLD/'development_fixture/inputs/p00-s26011601.json.gz');checks={}
    # Independent normal-equation solution of full-rank small linear examples.
    a=np.array([[1.,2.],[2.,-.5],[.5,1.]]);p=np.diag([2.,3.])
    for name,l in [('no_prior',np.zeros((0,2))),('prior',p)]:
        j=np.vstack([a,l]);uu,s,v=np.linalg.svd(j,full_matrices=False);k=(v.T/s)@uu.T;h=j.T@j;inv=np.linalg.solve(h,np.eye(2));assert np.allclose(k@k.T,inv);assert np.allclose(k[:,:3]@k[:,:3].T,inv@a.T@a@inv);checks[name]=True
    j=np.zeros((30,24));j[:23,:23]=np.eye(23);z=algebra(j,'B1',SOURCE,'fixed_correct');assert z['rank']==23 and z['curvature'] is None;assert ellipse(np.diag([1.,0.]),np.ones(2),SOURCE)['q'] is None;checks['rank_deficient_unavailable']=True
    # Dynamic original objective import contains optimizer definitions, but never invokes them.
    spec=importlib.util.spec_from_file_location('frozen_parity',ROOT/'tools/midterm_simulation_validation/core.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    maxr=maxj=0.
    for m in CFG['methods']:
        for start in initials(u['obs']['anchors'],u['obs']['start']).values():
            x=np.r_[start,0.] if m=='B2' else np.array(start);r,j=objective(u,m,x);fun,_,_=v.objective(SOURCE,u['obs'],m,np.array(u['oracle']) if m=='B3' else None);rr,jj=fun(x);maxr=max(maxr,float(max(abs(r-rr))));maxj=max(maxj,float(np.max(abs(j-jj))))
    assert maxr<1e-10 and maxj<1e-10;checks.update(max_residual_difference=maxr,max_jacobian_difference=maxj,optimizer_calls=0);print(checks);save(DOC/'DEVELOPMENT_CHECKS.json',checks)
if __name__=='__main__':run()
