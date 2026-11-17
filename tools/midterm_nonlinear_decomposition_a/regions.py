"""Structural-support Gaussian sets, not a pseudoinverse-only coverage test."""
from common import *

def factor_support(F,support=None,unit_m=1.):
 """F is noise gain in position units; support is mathematically certified, not inferred by truncation."""
 F=np.asarray(F,float);U,s,_=np.linalg.svd(F,full_matrices=False)
 if support is None:
  if len(s)!=2 or s[-1]<=1e-8*s[0]:return dict(reason='RANK_UNCERTAIN',rank=None)
  support=np.eye(2)
 Q=np.asarray(support,float);rank=Q.shape[1]
 assert Q.shape[0]==2 and np.allclose(Q.T@Q,np.eye(rank),atol=1e-12)
 off=np.linalg.norm(F-Q@(Q.T@F))
 if off>1e-10*unit_m:return dict(reason='STRUCTURAL_SUPPORT_MISMATCH',rank=None)
 if rank:
  P=(Q.T@F)@(Q.T@F).T;ev=np.linalg.eigvalsh(P)
  if ev[0]<=0 or np.sqrt(ev[0]/ev[-1])<=1e-8:return dict(reason='RANK_UNCERTAIN',rank=None)
 else:P=np.empty((0,0));ev=np.array([])
 return dict(reason='AVAILABLE',rank=rank,Q=Q,P=P,lambda_max=ev[-1] if rank else 0.,off_support_gain=off,unit_m=unit_m)

def region(z,e,B,rho,alpha,kind):
 if z['reason']!='AVAILABLE':return dict(reason=z['reason'],covered=None,radius=None,area=None,support_distance=None,q=None,rank=z['rank'])
 rank=z['rank'];Q=z['Q'];tol=1e-10*z['unit_m'];qcrit=float(chi2.ppf(1-alpha,rank)) if rank else 0.;e=np.asarray(e);perp=np.linalg.norm(e-Q@(Q.T@e));q=float((Q.T@e)@np.linalg.solve(z['P'],Q.T@e)) if rank else 0.
 radius=np.sqrt(qcrit*z['lambda_max'])+(rho*np.linalg.norm(B,2) if kind=='outer_circle' else 0.)
 if kind=='noise_support':
  hit=perp<=tol and q<=qcrit+100*np.finfo(float).eps*max(1,qcrit);area=np.pi*qcrit*np.sqrt(np.linalg.det(z['P'])) if rank==2 else 0.
 else:
  hit=np.linalg.norm(e)<=radius+100*np.finfo(float).eps*max(z['unit_m'],radius);area=np.pi*radius*radius
 return dict(reason='AVAILABLE',rank=rank,covered=bool(hit),radius=radius,area=area,support_distance=perp,support_tolerance=tol,q=q,qcrit=qcrit)

def structural_gains(u,a):
 """Analytic weak-y chain. Never declares small numerical eigenvalues to be exact zero."""
 G=a['G'].copy();T=a['T'].copy();weak_case=u['condition']['geometry']=='weak'
 err=0.
 if weak_case:
  truth=np.array(u['truth']);anchors=np.array(u['obs']['anchors']);assert np.all(anchors[:,1]==0) and np.all(truth[:,:,1]==0)
  assert np.all(a['j'][:54,1:24:2]==0)
  for t in range(6):
   for car in range(2):
    k=4*t+2*car+1;gg=np.zeros(74);gg[54+2*car+1:54+4*t:4]=u['obs']['motion_sigma'];tt=np.zeros(4);tt[2*car+1]=1
    err=max(err,float(max(abs(G[k]-gg))),float(max(abs(T[k]-tt))));G[k]=gg;T[k]=tt
  assert err<1e-10,err
 return G,T,err
