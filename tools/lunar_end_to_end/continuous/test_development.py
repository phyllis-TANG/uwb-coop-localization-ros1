"""Synthetic development checks, separate from route evaluation inputs."""
import unittest,importlib.util
from pathlib import Path
import numpy as np
from estimator import problem,solve
from checker import residual,audit

def fixture(N=9):
 t=np.linspace(0,2,N);q=np.stack([np.column_stack([t,np.sin(t)*.1]),np.column_stack([t+2,np.ones(N)])],axis=1);a=np.array([[-5,-4,1],[-5,5,1],[7,-4,1],[7,5,1]]);h=np.ones((N,2));pos=np.dstack([q,h]);y=np.column_stack([np.linalg.norm(pos[:,:,None]-a[None,None],axis=3).reshape(N,8),np.linalg.norm(pos[:,1]-pos[:,0],axis=1)])
 return dict(id='development',times_s=t.tolist(),anchors=a.tolist(),heights=h.tolist(),ranges=y.tolist(),increments=np.diff(q,axis=0).tolist(),prior=q[0].tolist(),sigma_range=.04,sigma_motion=.02,sigma_prior=.5),q
class Tests(unittest.TestCase):
 def test_01_jacobians(self):
  for N in [6,9,24]:
   for method in ['M0','M2','M3']:
    for rho in [None,.8]:
     o,_=fixture(N);f,x,_=problem(o,method,rho);r,J=f(x);np.testing.assert_allclose(r,residual(o,x,method,rho),atol=1e-10);K=np.column_stack([np.imag(residual(o,x.astype(complex)+1j*1e-20*np.eye(1,len(x),k)[0],method,rho))/1e-20 for k in range(len(x))]);np.testing.assert_allclose(J,K,atol=1e-10)
 def test_02_truth_rejected(self):
  o,_=fixture();o['truth']=0
  with self.assertRaises(ValueError):problem(o,'M3')
 def test_03_bad_scale(self):
  o,_=fixture();o['sigma_motion']=0
  with self.assertRaises(AssertionError):problem(o,'M3')
 def test_04_bad_time(self):
  o,_=fixture();o['times_s'][2]=-1
  with self.assertRaises(AssertionError):problem(o,'M3')
 def test_05_bad_rho(self):
  o,_=fixture()
  with self.assertRaises(AssertionError):problem(o,'M3',1)
 def test_06_no_peer(self):
  o,_=fixture();f,x,_=problem(o,'M0');r=f(x)[0];o['ranges']=np.asarray(o['ranges']);o['ranges'][:,8]+=100;g,z,_=problem(o,'M0');np.testing.assert_array_equal(r,g(z)[0])
 def test_07_constant_and_slope(self):
  o,q=fixture();N=len(q);o['ranges']=np.asarray(o['ranges']);t=np.asarray(o['times_s']);o['ranges'][:,8]+=.3+.07*(t-t[-1]/2);r,_=problem(o,'M3')[0](np.r_[q.ravel(),.3,.07]);np.testing.assert_allclose(r,0,atol=1e-12)
 def test_08_whitening_covariance(self):
  n=8;C=.8**abs(np.arange(n)[:,None]-np.arange(n)[None]);W=np.eye(n);W[1:]/=.6
  for i in range(1,n):W[i,i-1]=-.8/.6
  np.testing.assert_allclose(W@C@W.T,np.eye(n),atol=1e-14)
 def test_09_old_six_sample_equivalence(self):
  spec=importlib.util.spec_from_file_location('old',Path(__file__).parents[1]/'model.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);o,_=fixture(6);o['times_s']=(np.arange(6)*.2).tolist();oo=dict(o,peer_mask=[True]*6,measurement_ids=[[str(i) for i in range(9)]]*6)
  for m in ['M0','M2','M3']:
   f,x,_=problem(o,m);g,y=old.problem(oo,m);np.testing.assert_array_equal(x,y);np.testing.assert_allclose(f(x)[0],g(y)[0],atol=1e-12);np.testing.assert_allclose(f(x)[1],g(y)[1],atol=1e-12)
 def test_10_development_solves(self):
  o,_=fixture()
  for m,rho in [('M0',None),('M2',None),('M3',None),('M3',.8)]:
   r=solve(o,m,rho,lambda x:None);r.update(method=m,rho=rho);self.assertEqual(r['state'],'ACCEPTED');self.assertEqual(r['optimizer_calls_started'],2);audit(o,r)
if __name__=='__main__':unittest.main(verbosity=2)
