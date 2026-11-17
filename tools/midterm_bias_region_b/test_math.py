"""Analytic linear contract and independent exact noise-derivative check; no optimization."""
import argparse
from regions import *
def tests():
 c=config();rng=np.random.default_rng(811);A=rng.normal(size=(12,4))*10;sigma=.05;L=np.eye(4)/sigma;j=np.vstack([A,L]);H=j.T@j;v=quantities(j,H,sigma,np.ones(4),c);G=v['G'];T=v['T'];delta=np.array([.003,-.002,.001,.004]);noise=rng.normal(size=12)
 actual=np.linalg.lstsq(j,np.r_[noise,delta/sigma],rcond=None)[0];assert np.allclose(actual,G@noise+T@delta,atol=1e-14)
 # Linear covariance via independent column-wise QR solves.
 direct=np.linalg.lstsq(j,np.vstack([np.eye(12),np.zeros((4,12))]),rcond=None)[0];assert np.allclose(v['C'],direct@direct.T,atol=1e-14)
 ex=quantities(j,H,sigma,np.ones(4),c,True);assert np.allclose(ex['C'],v['C']) and not np.allclose(ex['C'],np.linalg.inv(H))
 F=np.eye(4)[:2];P=F@v['C']@F.T;B=F@T;rho=.05;q=chi2.ppf(.95,2);a=np.array([.6,.8]);support=np.sqrt(q*a@P@a)+rho*np.linalg.norm(B.T@a);z=np.sqrt(q)*P@a/np.sqrt(a@P@a);d=rho*B.T@a/np.linalg.norm(B.T@a);assert abs(a@(z+B@d)-support)<1e-13
 rad=region(P,B,rho,np.zeros(2),c)['radius'];samples=[]
 chol=np.linalg.cholesky(P)
 for _ in range(1000):
  t=rng.normal(size=2);t/=np.linalg.norm(t);d=rng.normal(size=4);d*=rho/np.linalg.norm(d);samples.append(np.linalg.norm(np.sqrt(q)*chol@t+B@d))
 assert max(samples)<=rad+1e-14
 r0=region(P,B,0,np.zeros(2),c);assert r0['bias_radius']==0 and r0['radius']==r0['noise_radius']
 assert r0['area']>=region(P,B,0,np.zeros(2),c,ellipse=True)['area']-1e-14
 # Unit rescaling m -> cm: A,L divide by100; covariance x10000 and radii x100.
 jc=j/100;vc=quantities(jc,jc.T@jc,sigma*100,np.ones(4),c);rc=region(F@vc['C']@F.T,F@vc['T'],rho*100,np.zeros(2),c)
 assert np.allclose(vc['C'],v['C']*10000) and np.allclose(vc['T'],T) and np.isclose(rc['radius'],rad*100)
 assert quantities(np.zeros((8,4)),np.zeros((4,4)),sigma,np.ones(4),c)['status']=='RANK_DEFICIENT'
 assert quantities(j,-np.eye(4),sigma,np.ones(4),c,True)['status']=='NONPOSITIVE_OR_ILL_CONDITIONED_HESSIAN'
 assert region(np.diag([1,0]),B,0,np.zeros(2),c)['reason']=='NONPOSITIVE_OR_SINGULAR_MARGINAL'
 # Representative saved endpoint: gradient derivative wrt every standardized data row.
 u=None
 with gzip.open(ROOT/c['source_archive'],'rt') as f:
  for line in f:
   e=json.loads(line)
   if e['type']=='PAIR':u=e['value']['target_input'];x=np.array(e['value']['target']['estimate']);m=e['value']['method'];break
 r,j=OLD.M.objective(u,m,x);nd=len(r)-4;eps=1e-5;fd=[]
 for k in range(nd):
  plus=json.loads(json.dumps(u));minus=json.loads(json.dumps(u));nr=48 if m=='B0' else 54
  if k<nr:
   idx=(k//8)*9+k%8 if m=='B0' else k;field='ranges';sig=u['obs']['range_sigma']
  else:idx=k-nr;field='movement';sig=u['obs']['motion_sigma']
  plus['obs'][field][idx]+=eps*sig;minus['obs'][field][idx]-=eps*sig
  rp,jp=OLD.M.objective(plus,m,x);rm,jm=OLD.M.objective(minus,m,x);fd.append((jp.T@rp-jm.T@rm)/(2*eps))
 fd=np.array(fd).T;err=float(np.max(abs(fd+j[:-4].T)));assert err<2e-7
 return dict(status='PASS',linear_identity_error=float(np.max(abs(actual-G@noise-T@delta))),noise_gradient_fd_max_error=err,support_equality_error=float(abs(a@(z+B@(rho*B.T@a/np.linalg.norm(B.T@a)))-support)),sampled_max_norm=max(samples),proved_outer_radius=rad,checks=['affine mean','independent QR covariance','support equality direction','1000 direction checks (not proof)','rho0 noise disk','m-to-cm units','rank deficient','negative Hessian','singular marginal','white data noise gradient derivative'],formal_runs=0,real_optimizer_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();z=tests();save(a.out,z);print(json.dumps(z))
