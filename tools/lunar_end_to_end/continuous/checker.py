"""Independent loop residual/complex-step readback; no optimizer imports."""
import numpy as np

def residual(o,x,method,rho=None):
 N=len(o['times_s']);xy=x[:4*N].reshape(N,2,2);h=np.asarray(o['heights']);a=np.asarray(o['anchors']);y=np.asarray(o['ranges']);tau=np.asarray(o['times_s'])-o['times_s'][-1]/2;out=[]
 for i in range(N):
  for c in range(2):
   for j in range(4):out.append((np.sqrt(sum((xy[i,c,k]-a[j,k])**2 for k in range(2))+(h[i,c]-a[j,2])**2)-y[i,4*c+j])/o['sigma_range'])
  if method!='M0':
   pred=np.sqrt(sum((xy[i,1,k]-xy[i,0,k])**2 for k in range(2))+(h[i,1]-h[i,0])**2)+x[4*N]
   if method=='M3':pred+=tau[i]*x[4*N+1]
   out.append((pred-y[i,8])/o['sigma_range'])
 motion=np.diff(xy,axis=0)-np.asarray(o['increments'])
 for i in range(N-1):
  for c in range(2):
   for k in range(2):out.append((motion[i,c,k] if rho is None or i==0 else (motion[i,c,k]-rho*motion[i-1,c,k])/np.sqrt(1-rho*rho))/o['sigma_motion'])
 for c in range(2):
  for k in range(2):out.append((xy[0,c,k]-o['prior'][c][k])/o['sigma_prior'])
 return np.asarray(out)

def metrics(o,ref,x,method):
 N=len(o['times_s']);xy=np.asarray(x[:4*N]).reshape(N,2,2);q=np.dstack([xy,np.asarray(o['heights'])]);truth=np.asarray(ref['xyz']);error=np.linalg.norm(q-truth,axis=2);t=np.asarray(o['times_s']);anchor=np.linalg.norm(q[:,:,None]-np.asarray(o['anchors'])[None,None],axis=3)-np.asarray(o['ranges'])[:,:8].reshape(N,2,4);b0=x[4*N] if method!='M0' else None;b1=x[4*N+1] if method=='M3' else 0 if method=='M2' else None
 rawpeer=np.linalg.norm(q[:,1]-q[:,0],axis=1)-np.asarray(o['ranges'])[:,8];peer=rawpeer+(b0 or 0)+(b1 or 0)*(t-t[-1]/2);motion=np.diff(xy,axis=0)-np.asarray(o['increments'])
 return dict(error_m=error.tolist(),rmse_m=np.sqrt(np.mean(error**2,axis=0)).tolist(),peak_m=error.max(0).tolist(),anchor_residual_rms_m=np.sqrt(np.mean(anchor**2,axis=(0,2))).tolist(),motion_residual_rms_m=np.sqrt(np.mean(motion**2,axis=(0,2))).tolist(),anchor_residual_slope_m_s=[float(np.polyfit(t,anchor[:,c].mean(1),1)[0]) for c in range(2)],peer_residual_rms_m=float(np.sqrt(np.mean(peer**2))),bias0_m=b0,bias_slope_m_s=b1,true_slope_m_s=ref['true_slope_m_s'],slope_error_m_s=None if b1 is None else b1-ref['true_slope_m_s'])

def audit(o,r):
 x=np.asarray(r['x']);method=r['method'];rho=r['rho'];rr=residual(o,x,method,rho);J=np.column_stack([np.imag(residual(o,x.astype(complex)+1j*1e-20*np.eye(1,len(x),k)[0],method,rho))/1e-20 for k in range(len(x))]);grad=float(np.max(abs(J.T@rr)));scale=np.r_[np.ones(4*len(o['times_s'])),np.full(len(x)-4*len(o['times_s']),.1)];sv=np.linalg.svd(J*scale,compute_uv=False);rank=int(sum(sv>sv[0]*1e-8))
 assert abs(float(rr@rr/2)-r['cost'])<1e-7
 assert abs(grad-r['gradient_inf'])<1e-7 and rank==r['rank']
 last=r['stages'][-1];expected='ACCEPTED' if rank==len(x) and grad<=1e-5 and last['status']>0 and last['success'] else 'NOT_STATIONARY' if grad>1e-5 else 'NOT_ACCEPTED';assert expected==r['state']
 return dict(cost_error=abs(float(rr@rr/2)-r['cost']),gradient_error=abs(grad-r['gradient_inf']),rank=rank)
