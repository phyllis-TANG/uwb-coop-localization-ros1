"""Read-only bridge to PR117. No reference data are loaded on import."""
import sys,json,hashlib,gzip,os,subprocess,csv
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'docs/research/moon1_localization_eval'
DOC=ROOT/'docs/research/moon1_bias_dynamics_eval'
sys.path.insert(0,str(ROOT/'tools/moon1_localization_eval'))
from model import problem,information,prediction
from common import clean,digest,read,filehash

def write(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:
  json.dump(clean(obj),f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)

def csvwrite(p,rows):
 with Path(p).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(clean(rows))

def unpack(p):
 with gzip.open(p,'rt') as f:return json.load(f)

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def sources():
 paths=list((ROOT/'tools/moon1_bias_dynamics_eval').glob('*.py'))+list((ROOT/'tools/moon1_localization_eval').glob('*.py'))
 paths += [ROOT/'tools/midterm_simulation_s2/prototype.py',ROOT/'tools/midterm_simulation_phase1/identifiability.py']
 paths += [p for p in DOC.glob('*') if p.name in ['PROTOCOL.md','CONFIG.json','SOLVER.json','CONTINUATION.json','NUMERICAL_DIAGNOSIS.md']]
 return {str(p.relative_to(ROOT)):filehash(p) for p in sorted(paths)}

def scales(n):return np.r_[np.ones(24),.1] if n==25 else np.ones(24)

def independent(o,method,q,dtype=float):
 """Independent loop residual/Jacobian; longdouble for roundoff diagnosis."""
 q=np.array(q,dtype=dtype);n=len(q);pts=q[:24].reshape(6,2,2);r=[];j=[]
 h=np.array(o['heights_m'],dtype=dtype);a=np.array(o['anchors_xyz_m'],dtype=dtype);sigma=dtype(o['range_sigma_m']);y=np.array(o['ranges_m'],dtype=dtype)
 for t in range(6):
  for c in range(2):
   for k in range(4):
    d=pts[t,c]-a[k,:2];z=h[t,c]-a[k,2];v=np.sqrt(d@d+z*z)
    row=np.zeros(n,dtype=dtype);row[t*4+c*2:t*4+c*2+2]=d/(v*sigma)
    r.append((v-y[9*t+4*c+k])/sigma);j.append(row)
  if method!='M0':
   d=pts[t,1]-pts[t,0];z=h[t,1]-h[t,0];v=np.sqrt(d@d+z*z)
   row=np.zeros(n,dtype=dtype);row[t*4:t*4+2]=-d/(v*sigma);row[t*4+2:t*4+4]=d/(v*sigma)
   if n==25:row[-1]=1/sigma
   r.append((v+(q[-1] if n==25 else 0)-y[9*t+8])/sigma);j.append(row)
 for t in range(5):
  for c in range(2):
   sig=dtype(o['motion_sigmas_m'][c])
   for k in range(2):
    row=np.zeros(n,dtype=dtype);row[t*4+c*2+k]=-1/sig;row[(t+1)*4+c*2+k]=1/sig
    r.append((pts[t+1,c,k]-pts[t,c,k]-dtype(o['global_xy_increments_m'][t][c][k]))/sig);j.append(row)
 for c in range(2):
  for k in range(2):
   sig=dtype(o['prior_sigma_m']);row=np.zeros(n,dtype=dtype);row[c*2+k]=1/sig
   r.append((pts[0,c,k]-dtype(o['prior_center_xy_m'][c][k]))/sig);j.append(row)
 return np.array(r,dtype=dtype),np.array(j,dtype=dtype)

def curvature(o,method,q):
 q=np.array(q);f,_,_=problem(o,method);r,j=f(q);h=j.T@j;gn=h.copy();pts=q[:24].reshape(6,2,2);height=np.array(o['heights_m']);row=0;n=len(q)
 for t in range(6):
  for c in range(2):
   for a in o['anchors_xyz_m']:
    d=pts[t,c]-np.array(a[:2]);z=height[t,c]-a[2];v=np.sqrt(d@d+z*z)
    k=np.eye(2)/v-np.outer(d,d)/v**3;idx=slice(4*t+2*c,4*t+2*c+2)
    h[idx,idx]+=r[row]/o['range_sigma_m']*k;row+=1
  if method!='M0':
   d=pts[t,1]-pts[t,0];z=height[t,1]-height[t,0];v=np.sqrt(d@d+z*z);k=np.eye(2)/v-np.outer(d,d)/v**3
   b=np.zeros((2,n));b[:,4*t:4*t+2]=-np.eye(2);b[:,4*t+2:4*t+4]=np.eye(2)
   h+=r[row]/o['range_sigma_m']*(b.T@k@b);row+=1
 return gn,h

def classify(q,r,j,scipy_status,success,threshold=1e-5):
 if not np.isfinite(np.r_[q,r,j.ravel()]).all():return 'NONFINITE'
 if scipy_status==0:return 'BUDGET_EXHAUSTED'
 if not success or np.max(abs(j.T@r))>threshold:return 'NOT_STATIONARY'
 if information(j,1e-8)['rank']!=len(q):return 'RANK_DEFICIENT'
 return 'ACCEPTED'
