"""Development only: frozen B panel, bounded numerical comparisons, controlled priors."""
import argparse, csv, hashlib, importlib.util, itertools, json, time, warnings
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_simulation_s2_v2'
def module(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
B=module('fixed_b',ROOT/'tools/midterm_simulation_s2/prototype.py')
CFG=json.loads((ROOT/'docs/research/midterm_simulation_s2/CONFIG.json').read_text())
def dump(p,x):
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def info(j):
    scale=np.r_[np.ones(24),.1] if j.shape[1]==25 else np.ones(24)
    _,s,v=np.linalg.svd(j*scale,full_matrices=True); rank=int(sum(s>s[0]*1e-8)); ns=v[rank:].T
    out=dict(rank=rank,spectrum=s.tolist(),ranks={str(t):int(sum(s>s[0]*t)) for t in [1e-6,1e-8,1e-10,1e-12]},nullspace_scaled=ns.tolist(),null_residual=float(np.linalg.norm(j@(scale[:,None]*ns))))
    if j.shape[1]==25:
        u,sp,_=np.linalg.svd(j[:,:24],full_matrices=False); k=sum(sp>sp[0]*1e-8); q=j[:,-1]; rem=q-u[:,:k]@(u[:,:k].T@q)
        out.update(bias_null_norm=float(np.linalg.norm(ns[-1])),bias_information=float(rem@rem))
    return out

def alt(obs,method,oracle,protocol,old):
    fun,start,_=B.problem(obs,method,oracle); counts=[0,0]
    def f(x): counts[0]+=1; return fun(x)[0]
    def j(x): counts[1]+=1; return fun(x)[1]
    begin=time.perf_counter(); rec={}; caught=[]
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            fit=least_squares(f,np.array(old['estimate']) if protocol=='P1' else start,jac=j,method='trf' if protocol=='P1' else 'lm',x_scale=np.r_[np.ones(24),.1] if method=='B2' else np.ones(24),max_nfev=100 if protocol=='P1' else 300,ftol=1e-14 if protocol=='P1' else 1e-13,xtol=1e-14 if protocol=='P1' else 1e-13,gtol=1e-14 if protocol=='P1' else 1e-13)
        rec=dict(estimate=fit.x.tolist(),scipy_status=int(fit.status),scipy_success=bool(fit.success),message=fit.message,nfev=fit.nfev,njev=fit.njev,optimality=float(fit.optimality))
    except Exception as e: rec=dict(estimate=None,scipy_status=None,scipy_success=False,message=repr(e),nfev=None,njev=None)
    rec.update(elapsed_s=time.perf_counter()-begin,warning_messages=[str(w.message) for w in caught],residual_calls=counts[0],jacobian_calls=counts[1]); return rec

def enrich(unit,method,protocol,rec,old):
    obs=unit['obs']; fun,_,receipt=B.problem(obs,method,np.array(unit['oracle']) if method=='B3' else None)
    row=dict(unit=unit['id'],panel=unit['panel'],geometry=unit['geometry'],motion=unit['motion'],kind=obs['kind'],bias=unit['bias'],profile=unit['profile'],seed=26011601,method=method,protocol=protocol,input_sha256=B.digest(receipt),scipy_status=rec.get('scipy_status'),scipy_success=rec.get('scipy_success',False),nfev=rec.get('nfev'),njev=rec.get('njev'),elapsed_s=rec['elapsed_s'],warning_count=len(rec.get('warning_messages',[])),exception=rec.get('estimate') is None)
    if rec.get('estimate') is None:
        row.update(finite=False,accepted=False,hit_limit=False); return row,rec
    x=np.array(rec['estimate']); r,j=fun(x); grad=j.T@r; scale=np.r_[np.ones(24),.1] if method=='B2' else np.ones(24)
    finite=bool(np.all(np.isfinite(np.r_[x,r,j.ravel(),grad])))
    cost=float(r@r/2); err=x[:24].reshape(6,2,2)-np.array(unit['truth']); mse=np.mean(np.sum(err**2,axis=2),axis=0)
    delta=x-np.array(old['estimate']); posdelta=float(np.max(np.linalg.norm(delta[:24].reshape(-1,2),axis=1))); bd=float(abs(delta[-1])) if method=='B2' else 0.
    c0=old['residual_sum_squares']/2; gain=c0-cost
    row.update(finite=finite,cost=cost,gradient_inf=float(max(abs(grad))),scaled_gradient_inf=float(max(abs(grad*scale))),accepted=bool(rec['scipy_success'] and finite and max(abs(grad))<=1e-5),hit_limit=rec['scipy_status']==0,position_change_max_m=posdelta,bias_change_m=bd,cost_decrease=gain,material_change=bool(gain>1e-6*max(1,c0) or posdelta>.001 or bd>.001),mse_car1=float(mse[0]),mse_car2=float(mse[1]),position_rmse=float(np.sqrt(np.mean(mse))),position_error_failure=bool(np.sqrt(np.mean(mse))>.5),bias_estimate=float(x[-1]) if method=='B2' else None,bias_error=float(x[-1]-unit['bias']) if method=='B2' else None,bias_error_failure=bool(abs(x[-1]-unit['bias'])>.1) if method=='B2' else None,total_nfev=rec['nfev']+(old['nfev'] if protocol=='P1' else 0),total_elapsed_s=rec['elapsed_s']+(old['elapsed_s'] if protocol=='P1' else 0))
    ref=np.r_[np.array(unit['truth']).ravel(),unit['bias']] if method=='B2' else np.array(unit['truth']).ravel(); jr=fun(ref)[1]; data=j[:-4] if obs['prior_sigma'] is not None else j; refdata=jr[:-4] if obs['prior_sigma'] is not None else jr
    rec.update(residual=r.tolist(),gradient=grad.tolist(),scaled_gradient=(grad*scale).tolist(),information=dict(final_total=info(j),final_data=info(data),reference_data=info(refdata)))
    row.update(data_rank=rec['information']['final_data']['rank'],reference_data_rank=rec['information']['reference_data']['rank']); return row,rec

def common():
    units=[]
    for g,m,k,b,p in itertools.product(['good','weak'],['static','turn'],['wall','peer'],[0.,.3],['noisy_unbiased_prior','noisy_biased_prior']):
        obs,t,o,noise=B.generate(g,m,k,b,p,26011601,CFG)
        units.append(dict(id=f'common-{len(units):02}',panel='common',geometry=g,motion=m,bias=b,profile=p,obs=obs,truth=t.tolist(),oracle=o.tolist(),noise=noise,obs_sha256=B.digest(obs)))
    return units

def supplement():
    units=[]
    for g,m in itertools.product(['good','weak','near'],['static','turn']):
        obs,t,o,noise=B.generate('weak' if g=='near' else g,m,'peer',.3,'noisy_unbiased_prior',26011601,CFG)
        if g=='near':
            anchors=np.array(obs['anchors']); anchors[:,1]=[0,.01,-.01,.02]; t[:,:,1]+=np.array([.01,-.01]); clean,_=B.pr97.model(np.r_[t.ravel(),0.],anchors,'peer'); obs['anchors']=anchors.tolist(); obs['ranges']=(clean+np.array(noise['range'])+o).tolist()
        center=np.array([1.2,1.25,1.8,1.8] if g=='good' else [1.2,.25,1.8,-.2]); obs['start']=np.vstack([center,center+np.cumsum(np.array(obs['movement']).reshape(5,4),axis=0)]).ravel().tolist()
        variants=[('none',None,0),('survey_weak',.5,0),('survey_strong',.05,0),('center_plus_weak',.5,1)]
        if m=='static': variants.append(('center_plus_strong',.05,1))
        for name,sigma,shift in variants:
            ob=dict(obs,prior_sigma=sigma,prior_center=(center+shift*np.array([.3,-.3,-.3,.3])).tolist())
            units.append(dict(id=f'supplement-{len(units):02}',panel='supplement',geometry=g,motion=m,bias=.3,profile=name,obs=ob,truth=t.tolist(),oracle=o.tolist(),noise=noise,obs_sha256=B.digest(ob)))
    return units

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--stage',choices=['original','alternatives','supplement'],required=True); args=ap.parse_args(); out=args.out; out.mkdir(parents=True,exist_ok=True)
    result_name='original_results.json' if args.stage=='original' else args.stage+'_results.json'
    if (out/result_name).exists(): raise FileExistsError('Use a new output directory; existing evidence is immutable')
    if args.stage=='original':
        units=common(); dump(out/'common_inputs.json',units); rows=[]; full=[]
        for unit in units:
            for method in B.METHODS:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always'); old=B.solve(unit['obs'],method,CFG,np.array(unit['oracle']) if method=='B3' else None)
                old['warning_messages']=[str(w.message) for w in caught]; raw=dict(old); row,rec=enrich(unit,method,'P0',dict(old),old); rows.append(row); full.append(dict(unit=unit['id'],method=method,original=raw,diagnostics=rec))
        dump(out/'original_results.json',full); dump(out/'original_rows.json',rows)
    else:
        units=json.loads((out/'common_inputs.json').read_text()) if args.stage=='alternatives' else supplement()
        if args.stage=='supplement': dump(out/'supplement_inputs.json',units)
        originals={(r['unit'],r['method']):r['original'] for r in json.loads((out/'original_results.json').read_text())} if args.stage=='alternatives' else {}
        rows=[]; full=[]
        for unit in units:
            for method in B.METHODS:
                oracle=np.array(unit['oracle']) if method=='B3' else None
                if args.stage=='supplement':
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always'); old=B.solve(unit['obs'],method,CFG,oracle)
                    old['warning_messages']=[str(w.message) for w in caught]
                    row,rec=enrich(unit,method,'P0',dict(old),old); rows.append(row); full.append(dict(unit=unit['id'],method=method,protocol='P0',result=rec))
                else: old=originals[unit['id'],method]
                for protocol in (['P1','P2'] if args.stage=='alternatives' else ['P1']):
                    rec=alt(unit['obs'],method,oracle,protocol,old); row,rec=enrich(unit,method,protocol,rec,old); rows.append(row); full.append(dict(unit=unit['id'],method=method,protocol=protocol,result=rec))
        dump(out/(args.stage+'_results.json'),full); dump(out/(args.stage+'_rows.json'),rows)
    print(json.dumps(dict(stage=args.stage,rows=len(rows),accepted=sum(r['accepted'] for r in rows),warnings=sum(r['warning_count'] for r in rows),formal_runs=0)))
if __name__=='__main__': main()
