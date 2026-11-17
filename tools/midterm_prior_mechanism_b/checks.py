"""Exposed-seed development, controlled failures and affine analytic identities."""
import argparse,copy,time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from scipy.optimize import least_squares
from adapter import config,conditions,generate,solve,V
from math_model import objective,reference,linear_components,algebra,gaussian_ellipse_probability
from io_utils import save,read,digest
import run as engine
from readback import audit

def main(out):
    out.mkdir(parents=True,exist_ok=False);c=config();qs=conditions(c);seed=c['seeds']['development'][0];maxobj=0.;maxendpoint=0.;maxmu=0.;maxcov=0.;starts={};oldreg=0
    for q in qs:
        u=generate(c,q,seed);key=q['geometry'];assert key not in starts or starts[key]==u['obs']['start'];starts[key]=u['obs']['start']
        old=V.generate(c,q,seed);assert old['obs']['ranges']==u['obs']['ranges'] and old['obs']['movement']==u['obs']['movement'] and old['obs']['start']==u['obs']['start']
        for m in c['methods']:
            f,init,_=V.objective(c,u['obs'],m,np.array(u['oracle']) if m=='B3' else None);r,j=f(init);rr,jj=objective(u,m,init);maxobj=max(maxobj,float(np.max(abs(rr-r))),float(np.max(abs(jj-j))))
            if q['mechanism']=='fixed_survey':
                assert old['obs']==u['obs'];a=V.solve_stage(c,old,m,'P0');b=solve(c,u,m,'P0');a=V.solve_stage(c,old,m,'P1',a);b=solve(c,u,m,'P1',b);maxendpoint=max(maxendpoint,float(np.max(abs(np.array(a['estimate'])-b['estimate']))));oldreg+=1
            x,r,j,a,mu=linear_components(u,m,c);h=j.T@j;inv=np.linalg.solve(h,np.eye(len(x)));k=inv@j.T;maxcov=max(maxcov,float(np.max(abs(inv-a['curvature']))));maxmu=max(maxmu,float(np.max(abs(k-a['gain']))));assert np.allclose(inv,a['curvature'],atol=1e-9,rtol=1e-9)
            assert np.allclose(a['mechanism_noise'],inv if q['mechanism']=='random_correct' else k[:,:-4]@k[:,:-4].T,atol=1e-9,rtol=1e-9)
    assert maxobj<1e-10 and maxendpoint==0.
    # Direct randomized-center pairing across sigmas, unchanged observation streams.
    randoms=[generate(c,q,seed) for q in qs if q['mechanism']=='random_correct'];assert all(u['prior_standard_noise']==randoms[0]['prior_standard_noise'] for u in randoms)
    streams=[c['noise']['range_stream'],c['noise']['motion_stream'],c['prior_stream']];assert len(set(streams))==3
    probe=np.column_stack([np.random.default_rng(np.random.SeedSequence([seed,k])).normal(size=20000) for k in streams]);cross=float(np.max(abs(np.corrcoef(probe,rowvar=False)-np.eye(3))));assert cross<.04
    # A fixed toy Gaussian uses development stream 99, not a localization performance sample.
    rng=np.random.default_rng(np.random.SeedSequence([seed,99]));a=rng.normal(size=(8,3));l=rng.normal(size=(2,3));j=np.vstack([a,l]);k=np.linalg.solve(j.T@j,j.T);mu=k@np.r_[np.zeros(8),[.3,-.2]];z=rng.normal(size=(100000,10));er=z@k.T+mu;pred=k@k.T;assert np.linalg.norm(np.cov(er.T)-pred)/np.linalg.norm(pred)<.02
    exact=gaussian_ellipse_probability(mu[:2],pred[:2,:2],pred[:2,:2],.95);actual=np.mean(np.einsum('ni,ij,nj->n',er[:,:2],np.linalg.inv(pred[:2,:2]),er[:,:2])<=5.991464547107979);assert abs(exact-actual)<.01
    rank=algebra(np.zeros((30,24)),'B1',c,'fixed_correct');assert rank['gain'] is None
    # Entire durable path with artificial exceptions/nonfinite/budget and B0 missing estimate.
    def throw(*args,**kwargs):raise RuntimeError('deliberate development exception')
    def nonfinite(f,x,**kw):return SimpleNamespace(x=np.full_like(x,np.nan),status=1,success=True,message='fixture',nfev=1,njev=1)
    def budget(f,x,**kw):kw['max_nfev']=1;return least_squares(f,x,**kw)
    def override(m,stage):return {'B0':throw,'B1':nonfinite,'B2':budget}.get(m,least_squares)
    engine.run(out/'failures',c,'development',ids=['p00'],workers=1,override=override);fc=audit(out/'failures',out/'failure_readback');r=read(out/'failure_readback/ROWS.json.gz');assert len(r)==8 and next(x for x in r if x['method']=='B0' and x['model']=='nonlinear')['mse1'] is None
    before={str(p):p.read_bytes() for p in (out/'failures/stages').rglob('*.gz')};engine.run(out/'failures',c,'development',resume=True,workers=1);assert all(Path(p).read_bytes()==v for p,v in before.items())
    try:engine.run(out/'failures',c,'development',workers=1)
    except FileExistsError:pass
    else:raise AssertionError('overwrite allowed')
    try:engine.run(out/'interrupted',c,'development',ids=['p00'],workers=1,stop_after=1)
    except KeyboardInterrupt:pass
    saved=(out/'interrupted/stages/p00-s26011601/B0-P0.json.gz').read_bytes();audit(out/'interrupted',out/'missing_readback');engine.run(out/'interrupted',c,'development',resume=True,workers=1);assert (out/'interrupted/stages/p00-s26011601/B0-P0.json.gz').read_bytes()==saved
    start=time.perf_counter();engine.run(out/'panel',c,'development',workers=2);ck=audit(out/'panel',out/'readback');pc=audit(out/'readback',out/'portable',True)
    result=dict(passed=True,formal_observations=0,formal_runs=0,development_seed=seed,old_fixed_survey_regressions=oldreg,max_objective_jacobian_diff=maxobj,max_endpoint_diff=maxendpoint,max_covariance_crosscheck=maxcov,max_gain_crosscheck=maxmu,random_prior_pairing=True,noise_stream_cross_correlation=cross,initialization_unchanged=True,toy_draws=100000,toy_empirical_coverage=float(actual),toy_exact_coverage=exact,failure_resume_overwrite_checked=True,readback=ck,portable=pc,elapsed_panel_and_audit_s=time.perf_counter()-start);save(out/'CHECKS.json',result);print(result)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
