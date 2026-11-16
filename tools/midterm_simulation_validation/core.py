"""Frozen objective adapter, configuration-driven generation and total failure records."""
import copy
import hashlib
import importlib.util
import itertools
import json
import time
import warnings
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'docs/research/midterm_simulation_validation'
_spec = importlib.util.spec_from_file_location('fixed_objective', ROOT/'tools/midterm_simulation_s2/prototype.py')
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

def clean(v):
    if isinstance(v, dict): return {k:clean(x) for k,x in v.items()}
    if isinstance(v, (list,tuple,np.ndarray)): return [clean(x) for x in v]
    if isinstance(v, (np.bool_,bool)): return bool(v)
    if isinstance(v, (np.integer,int)): return int(v)
    if isinstance(v, (np.floating,float)): return float(v) if np.isfinite(v) else None
    return v

def canonical(x):
    return json.dumps(clean(x),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def digest(x): return hashlib.sha256(canonical(x)).hexdigest()

def load_config(path=DOC/'CONFIG.json'):
    c=json.loads(Path(path).read_text())
    if c['epochs']!=6 or c['methods']!=['B0','B1','B2','B3']: raise ValueError('Frozen model supports six epochs and these four methods only')
    if c['priors']['bias_prior'] is not None or c['solver']['loss']!='linear': raise ValueError('No bias prior or robust objective allowed')
    if c['initialization']['rule']!='fixed_survey_then_integrate_observed_global_displacements' or c['initialization']['position_jitter_m']!=0: raise ValueError('Unsupported initialization rule')
    if c['noise']['rng']!='PCG64' or c['noise']['seed_sequence']!='[observation_seed, stream_id]': raise ValueError('Unsupported RNG contract')
    if not c['acceptance']['require_scipy_success'] or not c['acceptance']['require_finite_state_residual_jacobian_cost_gradient']: raise ValueError('Frozen finite/success policy required')
    if c['statistics']['unit']!='seed': raise ValueError('Independent unit must be seed')
    for k in ['range_sigma_m','motion_sigma_m']:
        if c['noise'][k]<=0: raise ValueError('sigma must be positive')
    if len(set(c['seeds']['formal']))!=len(c['seeds']['formal']): raise ValueError('Duplicate formal seeds')
    return c

def conditions(c):
    out=[]
    for group in c['matrix']:
        for g,m,k,b in itertools.product(group['geometries'],group['motions'],group['kinds'],group['biases_m']):
            if k not in ['wall','peer']: raise ValueError('Unknown affected link')
            out.append(dict(id=f'c{len(out):02}',panel=group['panel'],geometry=g,motion=m,kind=k,bias_m=b,prior=group['prior']))
    return out

def generate(c,condition,seed):
    geo=c['geometries'][condition['geometry']]; motion=c['motions'][condition['motion']]
    t=np.linspace(*c['time_interval'],c['epochs']);truth=np.tile(np.array(geo['initial_positions'],float),(c['epochs'],1,1))
    if motion['type']=='common_sinusoidal':
        truth[:,:,0]+=(motion['x_amplitude_m']*np.sin(motion['angle_radians']*t))[:,None]
        truth[:,:,1]+=(motion['y_amplitude_m']*(1-np.cos(motion['angle_radians']*t)))[:,None]
    elif motion['type']!='static': raise ValueError('Unsupported motion')
    anchors=np.array(geo['anchors'],float); z=np.r_[truth.ravel(),0.]
    ranges=B.pr97.model(z,anchors,condition['kind'])[0]; mv=B.pr97.movement(z)[0]
    noise={}
    for name,size in [('range',len(ranges)),('motion',len(mv))]:
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,c['noise'][name+'_stream']])))
        noise[name]=rng.normal(0,c['noise'][name+'_sigma_m'],size)
    oracle=condition['bias_m']*B.active(condition['kind']); mv=mv+noise['motion'];center=np.array(geo['survey'],float)
    start=np.vstack([center,center+np.cumsum(mv.reshape(-1,4),axis=0)]).ravel()
    prior=condition['prior'];sigma=None
    if prior=='survey_core': sigma=c['priors']['core_sigma_m']
    elif prior in ['survey_strong','shifted_strong']: sigma=c['priors']['strong_sigma_m']
    elif prior!='none': raise ValueError('Unknown prior')
    if prior=='shifted_strong':center=center+np.array(c['priors']['center_delta_m'])
    obs=dict(anchors=anchors.tolist(),ranges=(ranges+noise['range']+oracle).tolist(),movement=mv.tolist(),prior_center=center.tolist(),start=start.tolist(),kind=condition['kind'],prior_sigma=sigma,range_sigma=c['noise']['range_sigma_m'],motion_sigma=c['noise']['motion_sigma_m'])
    return clean(dict(condition=condition,seed=seed,obs=obs,truth=truth,oracle=oracle,noise=noise,input_sha256=digest(obs)))

def objective(c,obs,method,oracle=None):
    fun,start,receipt=B.problem(obs,method,oracle)
    if method=='B2':start[-1]=c['initialization']['bias_m'];receipt['start']=start.tolist()
    return fun,start,receipt

def scales(c,method):
    return np.r_[np.full(24,c['solver']['position_scale_m']),c['solver']['bias_scale_m']] if method=='B2' else np.full(24,c['solver']['position_scale_m'])

def information(c,j,method):
    result=dict(status='UNAVAILABLE',rank=None,singular_values=None,covariance=None,error=None)
    if not np.all(np.isfinite(j)):result['status']='NONFINITE_INFORMATION';return result
    try:
        scale=scales(c,method);_,s,vt=np.linalg.svd(j*scale,full_matrices=False)
        if not np.all(np.isfinite(s)):result['status']='NONFINITE_INFORMATION';return result
        rank=int(sum(s>s[0]*c['information']['rank_relative_tolerance']))
        result.update(rank=rank,singular_values=s.tolist(),status='RANK_DEFICIENT')
        if rank==j.shape[1]:
            with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
                cov=scale[:,None]*((vt.T/s**2)@vt)*scale[None,:]
            if np.all(np.isfinite(cov)): result.update(status='FINITE_LOCAL_INVERSE',covariance=cov.tolist())
            else: result['status']='NONFINITE_COVARIANCE'
    except Exception as exc: result.update(status='INFORMATION_EXCEPTION',error=repr(exc))
    return result

def blank(stage):
    return dict(stage=stage,execution='UNAVAILABLE',category='UNAVAILABLE',termination=None,scipy_status=None,scipy_success=False,message=None,exception=None,warnings=[],nfev=None,njev=None,elapsed_s=0.,residual_calls=0,jacobian_calls=0,estimate=None,residual=None,jacobian=None,gradient=None,scaled_gradient=None,cost=None,gradient_inf=None,scaled_gradient_inf=None,finite_state=False,finite_residual=False,finite_jacobian=False,finite_cost=False,finite_gradient=False,endpoint_valid=False,usable_estimate=False,accepted=False,hit_budget=False,position_mse=[None,None],position_rmse=[None,None],position_rmse_joint=None,position_error_exceeds=None,position_error_exceeds_by_car=[None,None],bias_estimate=None,bias_error=None,bias_error_exceeds=None,information=dict(status='UNAVAILABLE',rank=None,singular_values=None,covariance=None,error=None),changes=dict(position_max_m=None,bias_abs_m=None,cost_decrease=None),solver_input_sha256=None)

def evaluate(c,unit,method,stage,x,result):
    """Offline metrics are never used to choose a solver result or starting point."""
    out=copy.deepcopy(result);x=np.asarray(x,dtype=float);n=25 if method=='B2' else 24
    out['estimate']=clean(x)
    out['finite_state']=bool(x.shape==(n,) and np.all(np.isfinite(x)))
    if not out['finite_state']:
        out.update(execution='NONFINITE',category='NONFINITE');out['information']['status']='NONFINITE_INFORMATION';return out
    err=x[:24].reshape(6,2,2)-np.array(unit['truth'])
    with np.errstate(over='ignore',invalid='ignore'):
        mse=np.mean(np.sum(err**2,axis=2),axis=0)
    out['usable_estimate']=bool(np.all(np.isfinite(mse)))
    if out['usable_estimate']:
        joint=float(np.sqrt(np.mean(mse)));out.update(position_mse=mse.tolist(),position_rmse=np.sqrt(mse).tolist(),position_rmse_joint=joint,position_error_exceeds=joint>c['statistics']['position_rmse_threshold_m'],position_error_exceeds_by_car=(np.sqrt(mse)>c['statistics']['position_rmse_threshold_m']).tolist())
        if method=='B2':out.update(bias_estimate=float(x[-1]),bias_error=float(x[-1]-unit['condition']['bias_m']),bias_error_exceeds=bool(abs(x[-1]-unit['condition']['bias_m'])>c['statistics']['absolute_bias_error_threshold_m']))
    fun,_,_=objective(c,unit['obs'],method,np.array(unit['oracle']) if method=='B3' else None)
    r,j=fun(x)
    with np.errstate(over='ignore',invalid='ignore'):
        cost=float(.5*(r@r));gradient=j.T@r;scaled=gradient*scales(c,method)
    out.update(residual=clean(r),jacobian=clean(j),gradient=clean(gradient),scaled_gradient=clean(scaled),cost=clean(cost),gradient_inf=clean(np.max(np.abs(gradient))),scaled_gradient_inf=clean(np.max(np.abs(scaled))),finite_residual=bool(np.all(np.isfinite(r))),finite_jacobian=bool(np.all(np.isfinite(j))),finite_cost=bool(np.isfinite(cost)),finite_gradient=bool(np.all(np.isfinite(np.r_[gradient,scaled]))))
    out['endpoint_valid']=all(out[k] for k in ['finite_state','finite_residual','finite_jacobian','finite_cost','finite_gradient'])
    out['accepted']=bool(out['endpoint_valid'] and out['scipy_success'] and out['gradient_inf']<=c['acceptance']['physical_gradient_inf_max'])
    out['execution']='FINITE' if out['endpoint_valid'] else 'NONFINITE'
    out['category']='ACCEPTED' if out['accepted'] else 'NONFINITE' if not out['endpoint_valid'] else 'BUDGET_EXHAUSTED' if out['hit_budget'] else 'NOT_STATIONARY' if out['gradient_inf']>c['acceptance']['physical_gradient_inf_max'] else 'SOLVER_STOP_FAILURE'
    out['information']=information(c,j,method)
    return out

def solve_stage(c,unit,method,stage,previous=None,solver=least_squares):
    out=blank(stage);begin=time.perf_counter();caught=[]
    if stage=='P1' and (previous is None or not previous['endpoint_valid']):
        out.update(execution='SKIPPED',category='SKIPPED_INVALID_P0',message='P0 has no finite valid endpoint; no solver call');return out
    counts=[0,0]
    try:
        fun,start,receipt=objective(c,unit['obs'],method,np.array(unit['oracle']) if method=='B3' else None)
        out['solver_input_sha256']=digest(receipt)
        if stage=='P1':start=np.array(previous['estimate'])
        def f(x): counts[0]+=1;return fun(x)[0]
        def jac(x): counts[1]+=1;return fun(x)[1]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            fit=solver(f,start,jac=jac,x_scale=scales(c,method),loss=c['solver']['loss'],**c['solver'][stage])
            out.update(scipy_status=int(fit.status),scipy_success=bool(fit.success),message=str(fit.message),nfev=int(fit.nfev),njev=clean(fit.njev),hit_budget=int(fit.status)==0,termination={-1:'IMPROPER_INPUT',0:'BUDGET',1:'GTOL',2:'FTOL',3:'XTOL',4:'FTOL_AND_XTOL'}.get(int(fit.status),'OTHER'))
            out=evaluate(c,unit,method,stage,fit.x,out)
        if stage=='P1' and out['usable_estimate']:
            dx=np.array(out['estimate'])-np.array(previous['estimate']);out['changes']=dict(position_max_m=float(np.max(np.linalg.norm(dx[:24].reshape(-1,2),axis=1))),bias_abs_m=float(abs(dx[-1])) if method=='B2' else None,cost_decrease=previous['cost']-out['cost'] if out['cost'] is not None else None)
    except Exception as exc:
        out.update(execution='EXCEPTION',category='EXCEPTION',exception=repr(exc),message=repr(exc),accepted=False,endpoint_valid=False)
    out.update(elapsed_s=time.perf_counter()-begin,residual_calls=counts[0],jacobian_calls=counts[1],warnings=[dict(category=w.category.__name__,message=str(w.message)) for w in caught])
    return clean(out)

def independent_residual(unit,method,x):
    obs=unit['obs'];pts=np.array(x[:24]).reshape(6,2,2);anchors=np.array(obs['anchors']);y=np.array(obs['ranges']);r=[]
    if method=='B3':y=y-np.array(unit['oracle'])
    for t in range(6):
        for car in range(2):
            for k,a in enumerate(anchors):
                pred=np.sqrt(sum((pts[t,car]-a)**2))
                if method=='B2' and obs['kind']=='wall' and car==0 and k==0:pred+=x[-1]
                r.append((pred-y[9*t+4*car+k])/obs['range_sigma'])
        if method!='B0':
            pred=np.sqrt(sum((pts[t,1]-pts[t,0])**2))+(x[-1] if method=='B2' and obs['kind']=='peer' else 0)
            r.append((pred-y[9*t+8])/obs['range_sigma'])
    r.extend((np.diff(pts.reshape(6,4),axis=0).ravel()-obs['movement'])/obs['motion_sigma'])
    if obs['prior_sigma'] is not None:r.extend((np.array(x[:4])-obs['prior_center'])/obs['prior_sigma'])
    return np.array(r)
