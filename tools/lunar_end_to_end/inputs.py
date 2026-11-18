"""Generator owns references. Estimator receives separate strict observation records."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/research/lunar_end_to_end';ART=Path('/home/ubuntu22/uwb-lunar-end-to-end-artifacts')
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def atomic(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def ar1(z,rho=.8):
 e=z.copy()
 for i in range(1,len(e)):e[i]=rho*e[i-1]+np.sqrt(1-rho*rho)*z[i]
 return e
def generate(w,seed,peer,motion,sensitivity='control',noiseless=False):
 wi=int(w['id'][1:]);rng=lambda s:np.random.default_rng(np.random.SeedSequence([seed,wi,s]));q=np.array(w['xyz_m']);a=np.array(w['anchors_xyz_m']);delta=np.diff(q[:,:,:2],axis=0);z=rng(2).normal(size=(5,2,2));error=.02*(ar1(z) if motion=='correlated' else z)
 if motion=='scale':error[:,1]+=.05*delta[:,1]
 if motion=='slip_proxy':error[2,1]+=.15*np.array([np.cos(w['yaw_rad'][2][1]),np.sin(w['yaw_rad'][2][1])])
 curve={'normal':np.zeros(6),'constant':np.full(6,.3),'step':np.r_[np.zeros(3),np.full(3,.3)],'ramp':np.linspace(0,.3,6)}[peer]
 measured_q=q.copy();height=q[:,:,2].copy();mask=np.ones(6,dtype=bool)
 if sensitivity.startswith('time'):
  offset=.05 if sensitivity=='time_plus' else -.05
  data=np.load(ART/'scene.npz');tt=w['start_s']+np.arange(6)*.2+offset;xy=np.column_stack([np.interp(tt,data['gt_t'],data['gt_xyz'][:,k]) for k in range(2)]);v=(xy-data['low'])/float(data['res']);ij=np.floor(v).astype(int);u=v-ij;g=data['terrain'];hz=sum(g[ij[:,0]+b,ij[:,1]+c]*(u[:,0] if b else 1-u[:,0])*(u[:,1] if c else 1-u[:,1]) for b,c in [(0,0),(0,1),(1,0),(1,1)])+1.16;measured_q[:,1]=np.column_stack([xy,hz])
 if sensitivity.startswith('height'):height[:,1]+=.15 if sensitivity=='height_plus' else -.15
 if sensitivity=='missing':mask[2:4]=False
 ranges=np.column_stack([np.linalg.norm(q[:,:,None,:]-a[None,None],axis=3).reshape(6,8),np.linalg.norm(measured_q[:,1]-measured_q[:,0],axis=1)+curve]);noise=.04*rng(1).normal(size=(6,9));prior=q[0,:,:2]+.5*rng(3).normal(size=(2,2))
 if noiseless:error*=0;noise*=0;prior=q[0,:,:2].copy()
 ident=digest(dict(window=w['id'],seed=seed,peer=peer,motion=motion,sensitivity=sensitivity))[:24]
 o=dict(id=ident,times_s=w['times_s'],anchors=a.tolist(),heights=height.tolist(),ranges=(ranges+noise).tolist(),peer_mask=mask.tolist(),increments=(delta+error).tolist(),prior=prior.tolist(),sigma_range=.04,sigma_motion=.02,sigma_prior=.5,measurement_ids=[[f'{ident}:t{t}:r{k}' for k in range(9)] for t in range(6)])
 ref=dict(id=ident,xyz=q.tolist(),peer=peer,motion=motion,sensitivity=sensitivity,seed=seed,window=w['id'],bias=curve.tolist(),motion_error=error.tolist(),range_noise=noise.tolist())
 return o,ref
