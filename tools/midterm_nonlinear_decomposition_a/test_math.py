"""Deterministic tests only: no RNG, data generation, nonlinear optimizer."""
from regions import *
import argparse

def tests():
 cases=[]
 # Full-rank regression and nonzero normal-equation residual.
 J=np.array([[1.,2.],[3.,-1.],[2.,1.]]);r0=np.array([.2,-.4,.1]);dn=np.array([.3,-.2]);dl=np.linalg.lstsq(J,-r0,rcond=None)[0];g=J.T@(r0+J@dn)
 assert np.allclose(np.linalg.solve(J.T@J,g),dn-dl);cases.append('linear_decomposition_nonzero_gradient')
 # A deterministic nonlinear residual, deliberately not stationary.
 x=np.array([.2,.4]);r=np.array([x[0]**2+x[1],x[0]+2*x[1],2*x[0]-x[1]])-np.array([.1,.3,-.2]);rbase=-np.array([.1,.3,-.2]);j0=np.array([[0.,1.],[1.,2.],[2.,-1.]]);jn=j0.copy();jn[0,0]=2*x[0];eta=r-rbase-j0@x;delta=np.linalg.lstsq(j0,-rbase,rcond=None)[0]
 rhs=jn.T@r-j0.T@eta-(jn-j0).T@r;assert np.allclose(j0.T@j0@(x-delta),rhs);cases.append('nonlinear_identity_all_three_terms')
 for rank,F,Q in [(2,np.diag([2.,1.]),None),(1,np.array([[2.,0.],[0.,0.]]),np.array([[1.],[0.]])),(0,np.zeros((2,2)),np.empty((2,0)))]:
  z=factor_support(F,Q);assert z['rank']==rank
  q=chi2.ppf(.95,rank) if rank else 0.;edge=np.array([2*np.sqrt(q),0.]);B=np.eye(2)
  assert region(z,edge,B,0,.05,'noise_support')['covered']
  if rank<2:assert not region(z,np.array([0.,.01]),B,0,.05,'noise_support')['covered']
  if rank:assert not region(z,edge*1.001,B,0,.05,'noise_support')['covered']
  assert region(z,edge+np.array([.05,0]),B,.05,.05,'outer_circle')['covered']
  angle=.73;R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
  zz=factor_support(R@F,None if Q is None else R@Q);assert region(zz,R@edge,R@B,0,.05,'noise_support')['covered']
  zm=factor_support(1000*F,Q,unit_m=1000);assert region(zm,1000*edge,B,50,.05,'outer_circle')['covered'];assert np.isclose(region(zm,1000*edge,B,50,.05,'outer_circle')['radius'],1000*region(z,edge,B,.05,.05,'outer_circle')['radius'])
  cases.append(f'rank{rank}_boundary_support_offset_rotation_units')
 # Ill-resolved numerical rank is unavailable, not rounded into a line.
 assert factor_support(np.diag([1.,1e-10]))['reason']=='RANK_UNCERTAIN';cases.append('uncertain_rank_not_truncated')
 # All deterministic directions: support function bounded by spectral-norm outer circle.
 for angle in np.linspace(0,2*np.pi,65):
  v=np.array([np.cos(angle),np.sin(angle)]);P=np.diag([4.,0]);B=np.array([[1.,2.],[0.,1.]]);q=chi2.ppf(.95,1)
  assert np.sqrt(q*(v@P@v))+.05*np.linalg.norm(B.T@v)<=np.sqrt(q*4)+.05*np.linalg.norm(B,2)+1e-12
 assert abs(12*CFG['alpha_joint_block']-.05)<1e-15;cases+=['support_function_outer_bound','joint_union_risk_allocation']
 return dict(status='PASS',cases=cases,deterministic_tests=len(cases),**CALLS)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();protect();z=tests();save(args.out,z);print(z)
