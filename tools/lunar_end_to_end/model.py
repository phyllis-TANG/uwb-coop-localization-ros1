"""Estimator boundary: observations and public constants only; no reference imports."""
import numpy as np
from scipy.optimize import least_squares
import time
ALLOWED={'id','times_s','anchors','heights','ranges','peer_mask','increments','prior','sigma_range','sigma_motion','sigma_prior','measurement_ids'}
def problem(o,method):
 if set(o)!=ALLOWED:raise ValueError('Unexpected observation fields')
 
 for key,shape in {'anchors':(4,3),'heights':(6,2),'ranges':(6,9),'increments':(5,2,2),'prior':(2,2),'times_s':(6,),'peer_mask':(6,)}.items():
  arr=np.asarray(o[key]);
  if arr.shape!=shape or not np.isfinite(arr).all():raise ValueError('Invalid shape/nonfinite '+key)
 if min(o['sigma_range'],o['sigma_motion'],o['sigma_prior'])<=0 or not np.allclose(o['times_s'],np.arange(6)*.2):raise ValueError('Invalid units/grid/scale')
 n=24+{'M0':0,'M1':0,'M2':1,'M3':2}[method];a=np.array(o['anchors']);h=np.array(o['heights']);y=np.array(o['ranges']);tau=np.array(o['times_s'])-.5;mask=np.ones((6,9),bool);mask[:,8]=o['peer_mask'] if method!='M0' else False;s=o['sigma_range'];si=o['sigma_motion'];sp=o['sigma_prior'];inc=np.array(o['increments']);p=np.array(o['prior']);rows=np.arange(6)[:,None,None]*4+np.arange(2)[None,:,None]*2+np.arange(2)[None,None,:]
 mj=np.zeros((20,n));indices=np.arange(20);mj[indices,indices]=-1/si;mj[indices,indices+4]=1/si;pj=np.zeros((4,n));pj[:,:4]=np.eye(4)/sp
 def evaluate(q):
  xy=q[:24].reshape(6,2,2);d=xy[:,:,None,:]-a[None,None,:,:2];z=h[:,:,None]-a[None,None,:,2];dist=np.sqrt((d*d).sum(3)+z*z);pd=xy[:,1]-xy[:,0];pr=np.sqrt((pd*pd).sum(1)+(h[:,1]-h[:,0])**2)
  pred=np.column_stack([dist.reshape(6,8),pr]);j=np.zeros((6,9,n))
  for t in range(6):
   for c in range(2):j[t,4*c:4*c+4,4*t+2*c:4*t+2*c+2]=d[t,c]/dist[t,c,:,None]/s
   j[t,8,4*t:4*t+2]=-pd[t]/pr[t]/s;j[t,8,4*t+2:4*t+4]=pd[t]/pr[t]/s
  if n>=25:pred[:,8]+=q[24];j[:,8,24]=1/s
  if n==26:pred[:,8]+=q[25]*tau;j[:,8,25]=tau/s
  return np.r_[((pred-y)/s)[mask],((np.diff(xy,axis=0)-inc)/si).ravel(),((xy[0]-p)/sp).ravel()],np.vstack([j[mask],mj,pj])
 start=np.concatenate([p[None],p[None]+np.cumsum(inc,axis=0)],axis=0).ravel()+np.tile([.2,-.15,-.2,.15],6)
 return evaluate,np.r_[start,np.zeros(n-24)]
def diagnostics(q,r,j,status,success):
 sc=np.r_[np.ones(24),np.full(len(q)-24,.1)];_,sv,vt=np.linalg.svd(j*sc,full_matrices=False);rank=int(sum(sv>sv[0]*1e-8));grad=float(np.max(abs(j.T@r)));finite=bool(np.isfinite(np.r_[q,r,j.ravel()]).all());state='ACCEPTED' if finite and status!=0 and success and grad<=1e-5 and rank==len(q) else ('NONFINITE' if not finite else 'BUDGET_EXHAUSTED' if status==0 else 'NOT_STATIONARY' if grad>1e-5 or not success else 'RANK_DEFICIENT')
 cov=sc[:,None]*((vt.T/sv**2)@vt)*sc[None,:] if rank==len(q) else None
 return dict(state=state,finite=finite,gradient_inf=grad,rank=rank,dimension=len(q),singular_values=sv.tolist(),weak_direction_scaled=vt[-1].tolist(),covariance_diagonal=None if cov is None else np.diag(cov).tolist(),cost=float(r@r/2))
def solve(o,method,endpoint):
 f,q=problem(o,method);stages=[];start=time.monotonic()
 for stage,limit in enumerate([150,100]):
  endpoint(dict(q=q.tolist(),stages=stages,optimizer_calls_started=stage+1,stage_inflight=stage))
  t=time.monotonic();ans=least_squares(lambda q:f(q)[0],q,jac=lambda q:f(q)[1],method='trf',x_scale=np.r_[np.ones(24),np.full(len(q)-24,.1)],max_nfev=limit,ftol=None if stage else 1e-10,xtol=1e-14,gtol=1e-10);q=ans.x;r,j=f(q)
  stages.append(dict(stage=stage,nfev=ans.nfev,njev=ans.njev,status=ans.status,success=bool(ans.success),seconds=time.monotonic()-t))
  endpoint(dict(q=q.tolist(),stages=stages,optimizer_calls_started=stage+1,stage_inflight=None,**diagnostics(q,r,j,ans.status,ans.success)))
  if time.monotonic()-start>30:break
 return dict(q=q.tolist(),stages=stages,optimizer_calls_started=len(stages),seconds=time.monotonic()-start,**diagnostics(q,r,j,ans.status,ans.success))
