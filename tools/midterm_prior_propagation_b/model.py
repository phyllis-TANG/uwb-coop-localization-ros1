"""Read-only objective reconstruction and independently differentiated exact Hessian. No optimizer."""
import copy,gzip,hashlib,importlib.util,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_prior_propagation_b'
def load_module(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
M=load_module('prior_math_readonly','tools/midterm_prior_mechanism_b/math_model.py')
def clean(x):
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 return x
def canonical(x):return json.dumps(clean(x),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def read(p):
 p=Path(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return json.load(f)
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 # Exclusive publication: no replacement, including failed records.
 import os,tempfile
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.pending-')
 try:
  with os.fdopen(fd,'wb') as f:
   data=canonical(x);f.write(gzip.compress(data,mtime=0) if p.suffix=='.gz' else data+b'\n');f.flush();os.fsync(f.fileno())
  os.link(tmp,p)
 finally:os.unlink(tmp)
def config():return read(DOC/'CONFIG.json')
def source_units():
 out={}
 for p in sorted((ROOT/'docs/research/midterm_prior_mechanism_b/results').glob('EVIDENCE-*.jsonl.gz')):
  with gzip.open(p,'rt') as f:
   for line in f:
    v=json.loads(line)
    if v['type']=='UNIT':out[v['value']['item']['id']]=v['value']
 return out
def perturb(u,delta):
 v=copy.deepcopy(u);v['obs']['prior_center']=(np.array(v['obs']['prior_center'])+delta).tolist();v['input_sha256']=digest(v['obs']);return v
def exact_hessian(u,m,x):
 r,j=M.objective(u,m,x);h=j.T@j;p=x[:24].reshape(6,2,2);a=np.array(u['obs']['anchors']);sig=u['obs']['range_sigma'];k=8 if m=='B0' else 9
 for t in range(6):
  for link in range(k):
   if link<8:
    car=link//4;d=p[t,car]-a[link%4];idx=list(range(4*t+2*car,4*t+2*car+2));L=np.eye(2)
   else:d=p[t,1]-p[t,0];idx=list(range(4*t,4*t+4));L=np.c_[-np.eye(2),np.eye(2)]
   length=np.linalg.norm(d);v=d/length;Q=(np.eye(2)-np.outer(v,v))/length/sig
   h[np.ix_(idx,idx)]+=r[t*k+link]*(L.T@Q@L)
 return (h+h.T)/2

def transfer(u,m,x,exact=False):
 _,j=M.objective(u,m,x);h=exact_hessian(u,m,x) if exact else j.T@j;n=len(x);scale=np.r_[np.ones(24),.1] if m=='B2' else np.ones(24);hs=scale[:,None]*h*scale;ev=np.linalg.eigvalsh(hs);status='AVAILABLE' if ev[0]>max(1e-12,ev[-1]*1e-12) else 'NONPOSITIVE_OR_ILL_CONDITIONED';b=np.zeros((n,4));b[:4]=np.eye(4)/u['obs']['prior_sigma']**2
 T=None if status!='AVAILABLE' else scale[:,None]*np.linalg.solve(hs,scale[:,None]*b)
 return dict(status=status,min_eigenvalue=ev[0],condition_number=ev[-1]/ev[0] if ev[0]>0 else None,T=T)
def plans(c):
 return [dict(id=f"q{i:02}-s{seed}",source=f"p{base:02}-s{seed}",geometry=g,sigma=s,axis=axis,amplitude=a,delta=[a if z==axis else 0 for z in range(4)],seed=seed) for i,(g,s,base,axis,a) in enumerate((g,s,b,axis,a) for g,s,b in c['bases'] for axis in c['axes'] for a in c['amplitudes_m']) for seed in c['seeds']]
