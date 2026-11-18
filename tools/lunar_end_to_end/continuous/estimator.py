"""Variable-length route estimator: strict observation-only API, analytic derivatives."""
import time
import numpy as np
from scipy.optimize import least_squares
from scipy.linalg import solve_triangular
ALLOWED={'id','times_s','anchors','heights','ranges','increments','prior','sigma_range','sigma_motion','sigma_prior'}
def problem(o,method,rho=None):
 if set(o)!=ALLOWED:raise ValueError('Only observation fields allowed')
 if method not in ('M0','M2','M3'):raise ValueError('method')
 t=np.asarray(o['times_s']);N=len(t);d=4*N;nb={'M0':0,'M2':1,'M3':2}[method];n=d+nb
 for k,shape in dict(anchors=(4,3),heights=(N,2),ranges=(N,9),increments=(N-1,2,2),prior=(2,2)).items():
  v=np.asarray(o[k]);assert v.shape==shape and np.isfinite(v).all(),k
 assert N>=3 and t[0]==0 and (np.diff(t)>0).all()
 sr,sm,sp=[float(o[k]) for k in ('sigma_range','sigma_motion','sigma_prior')];assert min(sr,sm,sp)>0
 a=np.array(o['anchors']);h=np.array(o['heights']);y=np.array(o['ranges']);inc=np.array(o['increments']);p=np.array(o['prior']);tau=t-(t[0]+t[-1])/2
 mask=np.ones((N,9),bool);mask[:,8]=method!='M0'
 W=np.eye(N-1)
 if rho is not None:
  assert abs(rho)<1
  cov=rho**np.abs(np.arange(N-1)[:,None]-np.arange(N-1)[None]);W=solve_triangular(np.linalg.cholesky(cov),np.eye(N-1),lower=True)
 mj=np.zeros(((N-1)*4,n));ii=np.arange((N-1)*4);mj[ii,ii]=-1/sm;mj[ii,ii+4]=1/sm;mj=(W@mj.reshape(N-1,4*n)).reshape(-1,n)
 pj=np.zeros((4,n));pj[:,:4]=np.eye(4)/sp
 def fun(x):
  xy=x[:d].reshape(N,2,2);delta=xy[:,:,None,:]-a[None,None,:,:2];dist=np.sqrt((delta**2).sum(3)+(h[:,:,None]-a[None,None,:,2])**2);pd=xy[:,1]-xy[:,0];peer=np.sqrt((pd**2).sum(1)+(h[:,1]-h[:,0])**2)
  assert min(dist.min(),peer.min())>1e-10
  pred=np.column_stack([dist.reshape(N,8),peer]);J=np.zeros((N,9,n))
  for i in range(N):
   for c in range(2):J[i,4*c:4*c+4,4*i+2*c:4*i+2*c+2]=delta[i,c]/dist[i,c,:,None]/sr
   J[i,8,4*i:4*i+2]=-pd[i]/peer[i]/sr;J[i,8,4*i+2:4*i+4]=pd[i]/peer[i]/sr
  if nb:pred[:,8]+=x[d];J[:,8,d]=1/sr
  if nb==2:pred[:,8]+=tau*x[d+1];J[:,8,d+1]=tau/sr
  motion=(W@(np.diff(xy,axis=0)-inc).reshape(N-1,4)/sm).ravel()
  return np.r_[((pred-y)/sr)[mask],motion,((xy[0]-p)/sp).ravel()],np.vstack([J[mask],mj,pj])
 initial=np.concatenate([p[None],p[None]+np.cumsum(inc,axis=0)]).ravel()+np.tile([.2,-.15,-.2,.15],N)
 return fun,np.r_[initial,np.zeros(nb)],d

def solve(o,method,rho,checkpoint):
 f,x,d=problem(o,method,rho);stages=[];start=time.monotonic();scale=np.r_[np.ones(d),np.full(len(x)-d,.1)]
 for k,limit in enumerate([150,100]):
  checkpoint(dict(x=x.tolist(),stages=stages,inflight=k,optimizer_calls_started=k+1))
  st=time.monotonic();a=least_squares(lambda v:f(v)[0],x,jac=lambda v:f(v)[1],method='trf',x_scale=scale,max_nfev=limit,ftol=1e-10 if k==0 else None,xtol=1e-14,gtol=1e-10)
  x=a.x;stages.append(dict(nfev=a.nfev,njev=a.njev,status=a.status,success=bool(a.success),seconds=time.monotonic()-st))
  checkpoint(dict(x=x.tolist(),stages=stages,inflight=None,optimizer_calls_started=k+1))
 r,J=f(x);sv=np.linalg.svd(J*scale,compute_uv=False);rank=int((sv>sv[0]*1e-8).sum());grad=float(np.max(abs(J.T@r)));finite=bool(np.isfinite(np.r_[x,r,J.ravel()]).all());status='ACCEPTED' if finite and rank==len(x) and grad<=1e-5 and a.status>0 and a.success else 'NOT_STATIONARY' if finite and grad>1e-5 else 'NOT_ACCEPTED'
 return dict(x=x.tolist(),state=status,finite=finite,rank=rank,dimension=len(x),gradient_inf=grad,cost=float(r@r/2),seconds=time.monotonic()-start,stages=stages,optimizer_calls_started=len(stages))
