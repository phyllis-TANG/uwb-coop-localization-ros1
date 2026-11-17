"""Prior-center adapter; frozen nonlinear objective; separate truth-linearized SVD diagnostic."""
import importlib.util,itertools,time, warnings
import numpy as np
from io_utils import ROOT,DOC,read,digest
from math_model import linear_components
spec=importlib.util.spec_from_file_location('frozen_validation_core',ROOT/'tools/midterm_simulation_validation/core.py');V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V)
def config():return read(DOC/'CONFIG.json')
def conditions(c):
    x=c['matrix'];return [dict(id=f'p{i:02}',geometry=g,motion='static',kind='peer',bias_m=b,prior_sigma=s,mechanism=k,prior='survey_core' if s==.5 else 'survey_strong') for i,(g,b,s,k) in enumerate(itertools.product(x['geometries'],x['biases_m'],x['prior_sigmas_m'],x['mechanisms']))]
def generate(c,q,seed):
    u=V.generate(c,q,seed);o=u['obs'];o['prior_sigma']=q['prior_sigma'];truth=np.array(u['truth'])[0].ravel();z=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,c['prior_stream']]))).normal(size=4)
    if q['mechanism']=='fixed_correct':o['prior_center']=truth.tolist()
    elif q['mechanism']=='random_correct':o['prior_center']=(truth+q['prior_sigma']*z).tolist()
    u['prior_standard_noise']=z.tolist() if q['mechanism']=='random_correct' else None;u['input_sha256']=digest(o);return u

def solve(c,u,m,stage,previous=None,solver=None):
    if stage!='LINEAR':return V.solve_stage(c,u,m,stage,previous,**({} if solver is None else dict(solver=solver)))
    out=V.blank('LINEAR');begin=time.perf_counter();out['linear_solver']='scaled_SVD_direct_at_truth';out['analytic_mean']=None;out['analytic_covariance']=None;out['reference']=None;out['linear_rank']=None
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always');x,r,j,a,mu=linear_components(u,m,c);out['linear_rank']=a['rank'];out['reference']=x.tolist()
            if a['gain'] is None:out.update(category=a['status'],execution='UNAVAILABLE',information=dict(status=a['status'],rank=a['rank'],singular_values=a['singular_values'],covariance=None,error=None))
            else:
                # One SVD direct solution, no nonlinear optimizer and no truth-selected branch.
                delta=a['gain']@(-r);estimate=x+delta;rr=r+j@delta;g=j.T@rr;out.update(estimate=estimate.tolist(),residual=rr.tolist(),jacobian=j.tolist(),gradient=g.tolist(),gradient_inf=float(max(abs(g))),cost=float(rr@rr/2),endpoint_valid=True,usable_estimate=True,finite_state=True,finite_residual=True,finite_jacobian=True,finite_cost=True,finite_gradient=True,execution='FINITE',accepted=bool(max(abs(g))<=c['linear']['normal_equation_inf_tolerance']),analytic_mean=mu.tolist(),analytic_covariance=a['mechanism_noise'].tolist(),information=dict(status=a['status'],rank=a['rank'],singular_values=a['singular_values'],covariance=a['curvature'].tolist(),error=None))
                out['category']='DIRECT_ACCEPTED' if out['accepted'] else 'DIRECT_NORMAL_RESIDUAL_FAILURE';out['termination']='SVD_DIRECT';e=delta[:24].reshape(6,2,2);ms=np.mean(np.sum(e*e,axis=-1),axis=0);out['position_mse']=ms.tolist();out['position_rmse']=np.sqrt(ms).tolist()
                if m=='B2':out.update(bias_estimate=float(estimate[-1]),bias_error=float(delta[-1]))
            out['warnings']=[dict(category=w.category.__name__,message=str(w.message)) for w in caught]
    except Exception as exc:out.update(category='EXCEPTION',execution='EXCEPTION',exception=repr(exc),usable_estimate=False,endpoint_valid=False,accepted=False)
    out['elapsed_s']=time.perf_counter()-begin;return V.clean(out)
