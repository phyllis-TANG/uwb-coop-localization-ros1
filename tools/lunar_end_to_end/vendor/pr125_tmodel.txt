"""M0/M1/M2 frozen factors plus one centered-time peer trend column for M3."""
from tcommon import *
HEIGHT_MODE='given_world_vertical_height_not_estimated'

def tau(o):
 t=np.array(o['times_s']);return t-(t[0]+t[-1])/2

def scales(n):return np.r_[np.ones(24),np.full(n-24,.1)]

def problem(o,method):
 if o['height_mode']!=HEIGHT_MODE:raise ValueError('Explicit given-height interface required')
 adapted=dict(o,height_mode='height-oracle_world_vertical_1.16m')
 # The frozen factor validates shapes/units; its legacy mode label is internal only.
 old_validate(adapted)
 if method not in ['M0','M1','M2','M3']:raise ValueError('INVALID_METHOD')
 f,start,h=old_problem(adapted,'M2' if method=='M3' else method)
 if method!='M3':return f,start,digest(dict(frozen_receipt=h,method=method,height_contract=HEIGHT_MODE))
 t=tau(o);peer=np.arange(8,54,9)
 def evaluate(q):
  q=np.asarray(q,float)
  if q.shape!=(26,) or not np.isfinite(q).all():raise ValueError('INVALID_STATE')
  r,j=f(q[:25]);r[peer]+=q[25]*t/o['range_sigma_m'];j=np.column_stack([j,np.zeros(len(r))]);j[peer,25]=t/o['range_sigma_m']
  return r,j
 return evaluate,np.r_[start,0.],digest(dict(frozen_receipt=h,method='M3',tau=t.tolist(),height_contract=HEIGHT_MODE))

def independent(o,method,q):
 """Independent explicit loop residual/J; does not call frozen factors."""
 q=np.asarray(q);n=len(q);xy=q[:24].reshape(6,2,2);h=np.array(o['heights_m']);r=[];j=[];s=o['range_sigma_m'];tt=tau(o)
 for t in range(6):
  for c in range(2):
   for k,a in enumerate(o['anchors_xyz_m']):
    d=xy[t,c]-a[:2];dz=h[t,c]-a[2];rr=np.sqrt(d@d+dz*dz);row=np.zeros(n);row[4*t+2*c:4*t+2*c+2]=d/(rr*s)
    r.append((rr-o['ranges_m'][9*t+4*c+k])/s);j.append(row)
  if method!='M0':
   d=xy[t,1]-xy[t,0];dz=h[t,1]-h[t,0];rr=np.sqrt(d@d+dz*dz);row=np.zeros(n);row[4*t:4*t+2]=-d/(rr*s);row[4*t+2:4*t+4]=d/(rr*s)
   b=q[24] if n>=25 else 0.
   if n>=25:row[24]=1/s
   if n==26:b+=q[25]*tt[t];row[25]=tt[t]/s
   r.append((rr+b-o['ranges_m'][9*t+8])/s);j.append(row)
 for t in range(5):
  for c in range(2):
   s=o['motion_sigmas_m'][c]
   for k in range(2):
    row=np.zeros(n);row[4*t+2*c+k]=-1/s;row[4*(t+1)+2*c+k]=1/s
    r.append((xy[t+1,c,k]-xy[t,c,k]-o['global_xy_increments_m'][t][c][k])/s);j.append(row)
 for c in range(2):
  for k in range(2):
   s=o['prior_sigma_m'];row=np.zeros(n);row[2*c+k]=1/s;r.append((xy[0,c,k]-o['prior_center_xy_m'][c][k])/s);j.append(row)
 return np.array(r),np.array(j)

def information(j):
 sc=scales(j.shape[1]);_,s,vt=np.linalg.svd(j*sc,full_matrices=False);rank=int(sum(s>s[0]*1e-8));cov=None
 if rank==len(sc):cov=sc[:,None]*((vt.T/s**2)@vt)*sc[None,:]
 return clean(dict(rank=rank,dimension=len(sc),scales=sc,singular_values=s,condition=float(s[0]/s[-1]) if rank==len(sc) else None,weak_direction_scaled=vt[-1],position_covariance_blocks=None if cov is None else np.stack([cov[i:i+2,i:i+2] for i in range(0,24,2)]).reshape(6,2,2,2),bias_covariance=None if cov is None or len(sc)==24 else cov[24:,24:]))

def classify(q,r,j,status,success):
 if not np.isfinite(np.r_[q,r,j.ravel()]).all():return 'NONFINITE'
 if status==0:return 'BUDGET_EXHAUSTED'
 if not success or max(abs(j.T@r))>1e-5:return 'NOT_STATIONARY'
 if information(j)['rank']!=len(q):return 'RANK_DEFICIENT'
 return 'ACCEPTED'
