"""Analytic checks for the exact covariance row contract and Gaussian propagation."""
from common import *
from scipy.stats import ncx2
import argparse

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();checks=[]
 # Independent AR innovation operator, including stationary first observation.
 t=np.zeros((6,6))
 for i in range(6):
  t[i,0]=.7**i
  for j in range(1,i+1):t[i,j]=np.sqrt(1-.7**2)*.7**(i-j)
 full=np.kron(t@t.T,np.eye(9));allomega=np.eye(74);allomega[:54,:54]=full
 for method in METHODS:
  ids=np.r_[data_indices(method),np.arange(54,74)];assert np.allclose(omega(method,'ar1_07'),allomega[np.ix_(ids,ids)],atol=1e-14)
  for mod,var in [('iid_004',1),('iid_008',4)]:assert np.array_equal(np.diag(omega(method,mod)),np.r_[np.full(len(data_indices(method)),var),np.ones(20)])
 rng=np.random.default_rng(88011701);a=rng.normal(size=(74,3));l=np.array([[1.,0,0],[0,2.,0]]);shift=np.array([2.,-3.]);layout_scale=[1.,1.,.1];n=100000;eps=rng.normal(size=(n,74))
 for name,prior,delta,model in [('independent',l,np.zeros(2),'iid_004'),('wrong_prior',l,shift,'iid_004'),('variance_mismatch',l,shift,'iid_008'),('time_correlation',l,shift,'ar1_07'),('no_prior',np.empty((0,3)),np.empty(0),'iid_004')]:
  h=a.T@a+prior.T@prior;c=information(np.vstack([a,prior]),layout_scale)['covariance'];direct=np.linalg.inv(h);assert np.allclose(c,direct,atol=1e-12)
  o=omega('B2',model);g=c@a.T;pred=g@o@g.T;mu=c@prior.T@delta
  samples=eps@np.linalg.cholesky(o).T@g.T+mu;emp=np.cov(samples.T);rel=float(np.linalg.norm(emp-pred)/np.linalg.norm(pred));assert rel<.02
  qq=np.einsum('ni,ij,nj->n',samples[:,:2],np.linalg.inv(pred[:2,:2]),samples[:,:2]);nc=float(mu[:2]@np.linalg.solve(pred[:2,:2],mu[:2]));exact=float(ncx2.cdf(quantile(.95,2),2,nc));observed=float(np.mean(qq<=quantile(.95,2)));assert abs(exact-observed)<.008
  checks.append(dict(case=name,covariance_relative_error=rel,coverage95=observed,analytic_coverage95=exact))
 deficient=information(np.array([[1.,0,0],[2.,0,0]]),layout_scale);assert deficient['rank']==1 and deficient['covariance'] is None and not block_metrics(None,[0,1],[0.,0.])['available']
 write_json(args.out,dict(passed=True,optimizer_calls=0,new_localization_inputs=0,analytic_draws_per_case=n,seed=88011701,AR_stationary_row_contract_checked=True,B0_selection_checked=True,rank_deficient_unavailable=True,cases=checks))
if __name__=='__main__':main()
