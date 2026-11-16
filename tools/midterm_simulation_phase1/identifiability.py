"""P-S1 diagnostic XY + one constant range bias; not a production backend."""
import json,csv,math
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
P=Path(__file__).resolve().parents[2]/'docs/research/midterm_simulation_phase1'

def design(geometry,motion):
 t=np.linspace(0,1,6);anchors=np.array([[-3,0],[-1,0],[4,0],[6,0.]]) if geometry=='weak' else np.array([[0,0],[5,0],[5,5],[0,5.]])
 x=np.zeros((6,2,2));x[:,0]=[1,0 if geometry=='weak' else 1];x[:,1]=[2,0 if geometry=='weak' else 2]
 if motion=='straight':x[:,:,0]+=t[:,None]*.5
 if motion=='turn':
  x[:,:,0]+=(.5*np.sin(t*np.pi))[:,None];x[:,:,1]+=(.5*(1-np.cos(t*np.pi)))[:,None]
 return anchors,x

def model(z,anchors,kind):
 x=z[:-1].reshape(6,2,2);bias=z[-1];rows=[];jac=[];n=len(z)
 for t in range(6):
  for c in range(2):
   for k,a in enumerate(anchors):
    d=x[t,c]-a;r=np.linalg.norm(d);v=np.zeros(n);v[4*t+2*c:4*t+2*c+2]=d/r
    active=kind=='wall' and c==0 and k==0;v[-1]=int(active);rows.append(r+bias*active);jac.append(v)
  d=x[t,1]-x[t,0];r=np.linalg.norm(d);v=np.zeros(n);v[4*t:4*t+2]=-d/r;v[4*t+2:4*t+4]=d/r;v[-1]=int(kind=='peer');rows.append(r+bias*(kind=='peer'));jac.append(v)
 return np.array(rows),np.array(jac)

def movement(z):
 x=z[:-1].reshape(6,4);vals=np.diff(x,axis=0).ravel();j=np.zeros((20,25))
 for i in range(20):j[i,i]=-1;j[i,i+4]=1
 return vals,j

def main():
 results=[];fits=[];checks=[];scales=np.r_[np.ones(24),.1]
 for geom in ['good','weak']:
  for motion in ['static','straight','turn']:
   for kind in ['wall','peer']:
    anchors,x=design(geom,motion);z=np.r_[x.ravel(),.3];meas,j=model(z,anchors,kind);mv,mj=movement(z)
    fd=np.column_stack([(model(z+np.eye(25)[i]*1e-6,anchors,kind)[0]-model(z-np.eye(25)[i]*1e-6,anchors,kind)[0])/2e-6 for i in range(25)])
    error=float(np.max(np.abs(fd-j)));assert error<1e-8;checks.append(error)
    base=np.vstack([j/.04,mj/.02]);prior=np.zeros((4,25));prior[:,:4]=np.eye(4)
    for mode,a in [('measurements',j/.04),('data_motion',base),('with_initial_prior',np.vstack([base,prior/.05]))]:
     _,s,v=np.linalg.svd(a*scales,full_matrices=False);tol=s[0]*1e-8;rank=int(sum(s>tol))
     results.append(dict(geometry=geom,motion=motion,bias_source=kind,information=mode,state_dimension=25,rank=rank,rank_relative_threshold=1e-8,singular_values=s.tolist(),weak_direction_scaled=v[-1].tolist(),weak_direction_physical=(v[-1]*scales).tolist(),condition=float(s[0]/s[-1]) if s[-1]>tol else None))
    for prior_sigma in [.05,.5,5.]:
     for init in [-.3,0,.3]:
      start=z.copy();start[:-1]+=init;start[-1]=init
      def fun(q):return np.r_[(model(q,anchors,kind)[0]-meas)/.04,(movement(q)[0]-mv)/.02,(q[:4]-z[:4])/prior_sigma]
      def jac(q):return np.vstack([model(q,anchors,kind)[1]/.04,mj/.02,prior/prior_sigma])
      fit=least_squares(fun,start,jac=jac,x_scale=scales,max_nfev=200,ftol=1e-10,xtol=1e-10,gtol=1e-10)
      fits.append(dict(geometry=geom,motion=motion,bias_source=kind,prior_sigma_m=prior_sigma,initial_shift_m=init,success=bool(fit.success),nfev=fit.nfev,bias_estimate_m=float(fit.x[-1]),bias_error_m=float(fit.x[-1]-.3),position_rmse_m=float(np.sqrt(np.mean((fit.x[:-1]-z[:-1])**2))),cost=float(fit.cost)))
 with (P/'S1_INFORMATION.json').open('x') as f:json.dump(results,f,indent=2)
 with (P/'S1_INITIALIZATION.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=fits[0]);w.writeheader();w.writerows(fits)
 (P/'S1_CHECKS.json').write_text(json.dumps(dict(max_jacobian_error=max(checks),cases=12,diagnostic_fits=len(fits),failed_fits=sum(not r['success'] for r in fits)),indent=2))
if __name__=='__main__':main()
