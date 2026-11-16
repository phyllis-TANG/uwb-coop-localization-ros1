"""Analytic linear-Gaussian checks, not new localization seeds or fits."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.stats import chi2,ncx2
from diagnostics import Layout,Noise,diagnose,information,block_metrics

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);z=p.parse_args()
    a=np.array([[1.,0,1],[0,1,1],[1,1,0],[2,-1,.5]])
    l=np.array([[1.,0,0],[0,2,0]])
    layout=Layout(('x','y','b'),('m',)*3,((0,0,0,1),),2,(1.,1.,.1),4,2,'explicit estimator whitened linear rows')
    d=diagnose(state=np.zeros(3),error=np.zeros(3),j_data=a,j_prior=l,layout=layout,actual_noise=Noise('identity',4),numerical_status={'accepted':True})
    h=a.T@a+l.T@l;c=np.linalg.inv(h);cross=float(np.max(abs(c-d['matrices']['total_curvature'])))
    schur=h[:2,:2]-h[:2,2:3]@h[2:3,:2]/h[2,2]
    assert np.allclose(np.linalg.inv(schur),c[:2,:2],atol=1e-12)
    assert np.allclose(np.linalg.inv(h[2:,2:]-h[2:,:2]@np.linalg.solve(h[:2,:2],h[:2,2:])),c[2:,2:])
    assert cross<1e-12
    rng=np.random.default_rng(88011601);n=100000;unit=rng.normal(size=(n,4));prior_noise=rng.normal(size=(n,2));shift=np.array([.8,-.5])
    cases=[]
    # Linear algebra propagation only, no optimizer even in toy examples.
    for name,aa,ll,omega,delta,random_prior in [
        ('no_prior',a,np.empty((0,3)),np.eye(4),np.array([]),False),
        ('fixed_wrong_prior',a,l,np.eye(4),shift,False),
        ('random_correct_prior',a,l,np.eye(4),np.zeros(2),True),
        ('variance_mismatch',a,l,np.diag([4.,.25,2.,1.]),shift,False),
        ('time_correlated',a,l,.65**abs(np.arange(4)[:,None]-np.arange(4)[None,:]),shift,False)]:
        cc=np.linalg.inv(aa.T@aa+ll.T@ll);mu=cc@ll.T@delta
        eps=unit@np.linalg.cholesky(omega).T
        errors=eps@aa@cc+mu
        pred=cc@aa.T@omega@aa@cc
        if random_prior:errors+=prior_noise@ll@cc;pred+=cc@ll.T@ll@cc
        empirical=np.cov(errors,rowvar=False);rel=float(np.linalg.norm(empirical-pred)/np.linalg.norm(pred));assert rel<.02
        error_xy=errors[:,:2];sub=pred[:2,:2];q=np.einsum('ni,ij,nj->n',error_xy,np.linalg.inv(sub),error_xy)
        nc=float(mu[:2]@np.linalg.solve(sub,mu[:2]));coverage=float(np.mean(q<=chi2.ppf(.95,2)));exact=float(ncx2.cdf(chi2.ppf(.95,2),2,nc))
        assert abs(coverage-exact)<.008
        api_layout=Layout(layout.names,layout.units,layout.position_blocks,2,layout.scales,4,len(ll),layout.whitening)
        out=diagnose(state=np.zeros(3),error=np.zeros(3),j_data=aa,j_prior=ll,layout=api_layout,actual_noise=Noise('full',4,omega),numerical_status={'accepted':True})
        expected=out['matrices']['fixed_prior_noise']+(cc@ll.T@ll@cc if random_prior else 0)
        assert np.allclose(expected,pred,rtol=1e-12,atol=1e-12)
        cases.append(dict(name=name,draws=n,relative_covariance_error=rel,coverage95=coverage,analytic_noncentral_coverage95=exact,mean_bias=mu.tolist()))
    singular=information(np.array([[1.,0,1],[2,0,2]]),[1,1,.1]);assert singular['rank']==1 and singular['covariance'] is None
    assert not block_metrics(None,[0,1],[0,0])['available']
    m=block_metrics(np.diag([4.,9.]),[0,1],[2,3]);assert abs(m['q']-2)<1e-12
    assert m['levels']['0.95']['covered']
    try:diagnose(state=np.zeros(2),error=np.zeros(2),j_data=a,j_prior=l,layout=layout,actual_noise=Noise('identity',4),numerical_status={})
    except ValueError:pass
    else:raise AssertionError('No implicit layout guessing allowed')
    result=dict(passed=True,optimizer_calls=0,localization_observations_generated=0,analytic_mc_seed=88011601,schur_inverse_max_error=cross,cases=cases,rank_deficient_no_covariance=True,explicit_layout_rejection=True)
    with z.out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
