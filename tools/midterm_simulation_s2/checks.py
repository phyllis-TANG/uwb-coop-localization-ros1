"""Independent mathematical identities, fail handling, and source checks."""
import argparse,json
from pathlib import Path
import numpy as np
from prototype import ROOT, pr97, active, generate, problem, solve, information, digest

def check(cfg):
    errors=[]; exact=[]
    for g in cfg['geometries']:
        for m in cfg['motions']:
            a,x=pr97.design(g,m)
            for kind in cfg['links']:
                q=np.r_[x.ravel(),.3]
                values,j=pr97.model(q,a,kind)
                independent=[]
                for t in range(6):
                    for c in range(2):
                        independent.extend([float(np.sqrt(np.dot(x[t,c]-p,x[t,c]-p)))+(.3 if kind=='wall' and c==0 and k==0 else 0) for k,p in enumerate(a)])
                    independent.append(float(np.sqrt(np.dot(x[t,1]-x[t,0],x[t,1]-x[t,0])))+(.3 if kind=='peer' else 0))
                assert np.allclose(values,independent,atol=1e-14,rtol=0)
                fd=np.column_stack([(pr97.model(q+np.eye(25)[i]*1e-6,a,kind)[0]-pr97.model(q-np.eye(25)[i]*1e-6,a,kind)[0])/2e-6 for i in range(25)])
                errors.append(float(np.max(np.abs(j-fd))))
                assert errors[-1]<cfg['tests']['jacobian_abs_tol']
                obs,truth,corr,_=generate(g,m,kind,.3,'noiseless',0,cfg)
                for method in ['B2','B3']:
                    f,_,_=problem(obs,method,corr)
                    target=np.r_[truth.ravel(),.3] if method=='B2' else truth.ravel()
                    assert np.max(np.abs(f(target)[0]))<1e-12
                if g=='good':
                    for method in ['B2','B3']:
                        fit=solve(obs,method,cfg,corr)
                        err=float(np.max(np.abs(np.array(fit['estimate'])[:24]-truth.ravel())))
                        assert fit['success'] and err<cfg['tests']['exact_solution_abs_tol']
                        if method=='B2':assert abs(fit['estimate'][-1]-.3)<1e-6
                        exact.append(dict(motion=m,kind=kind,method=method,max_position_error=err))
    seed=cfg['development_seeds'][0]
    o0,t,c0,n0=generate('good','turn','peer',0.,'noisy_unbiased_prior',seed,cfg)
    o1,t,c1,n1=generate('good','turn','peer',.3,'noisy_unbiased_prior',seed,cfg)
    assert digest(n0)==digest(n1)
    a=solve(o0,'B0',cfg);b=solve(o1,'B0',cfg)
    assert a['input_sha256']==b['input_sha256'] and a['estimate']==b['estimate']
    _,_,r0=problem(o0,'B1');_,_,r1=problem(o1,'B3',c1)
    assert np.allclose(r0['ranges'],r1['ranges'],atol=1e-14,rtol=0)
    # No posterior covariance may be manufactured in a singular truth configuration.
    ow,tw,cw,_=generate('weak','static','wall',.3,'noiseless_no_prior',0,cfg)
    fw,_,_=problem(ow,'B2');inf=information(fw(np.r_[tw.ravel(),.3])[1],cfg['rank_relative_tol'])
    assert inf['rank']==23 and inf['covariance'] is None
    failed=solve(o1,'B2',cfg,max_nfev=1)
    assert failed['status']=='NOT_CONVERGED' and not failed['success'] and failed['estimate'] is not None
    # Deterministic reference/no-prior case starts exactly on the singular manifold.
    ow['start']=tw.ravel().tolist();retained=solve(ow,'B3',cfg,cw)
    assert retained['status']=='CONVERGED_RANK_DEFICIENT' and retained['posterior_information']['covariance'] is None
    return dict(status='PASS',max_jacobian_error=max(errors),jacobian_cases=len(errors),exact_solution_checks=exact,
                B0_peer_input_output_exact_equal=True,B3_compensation_identity=True,
                singular_reference_rank=inf['rank'],forced_failure=failed,singular_solver_case=retained)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    cfg=json.loads((ROOT/'docs/research/midterm_simulation_s2/CONFIG.json').read_text())
    result=check(cfg)
    with Path(args.output).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print('MATHEMATICAL_CHECKS PASS',result['max_jacobian_error'])
