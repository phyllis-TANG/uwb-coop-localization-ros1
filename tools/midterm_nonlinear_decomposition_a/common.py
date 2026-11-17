"""Read-only sources, explicit state contract and runtime optimizer tripwire."""
import csv,gzip,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
from scipy.stats import chi2
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_nonlinear_decomposition_a'
A=ROOT/'docs/research/midterm_geometry_perturbation_a/results'
B=ROOT/'docs/research/midterm_inset_validation_b/results'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
M=module('decomposition_math','tools/midterm_prior_mechanism_b/math_model.py')
L=module('decomposition_legacy','tools/midterm_geometry_perturbation_a/common.py')
CFG=json.loads((DOC/'CONFIG.json').read_text())
CALLS={'optimizer_calls':0,'new_random_observations':0}
def guard(frame,event,arg):
 if event=='call' and ('/scipy/optimize/' in frame.f_code.co_filename or frame.f_code.co_name in ['generate','generate_input'] and '/tools/' in frame.f_code.co_filename):
  CALLS['optimizer_calls']+=1;raise RuntimeError('FORBIDDEN optimizer/generator call: '+frame.f_code.co_filename)
def protect():sys.setprofile(guard)
def source_check():
 hs=json.loads((DOC/'SOURCE_HASHES.json').read_text())['files'];bad=[p for p,h in hs.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
 assert not bad,bad
 return len(hs)
def records(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def clean(v):
 if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,np.ndarray):return clean(v.tolist())
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,float) and not np.isfinite(v):return None
 return v
def save(p,v):p.write_text(json.dumps(clean(v),ensure_ascii=False,indent=2)+'\n')
def table(p,rs):
 keys=list(dict.fromkeys(k for r in rs for k in r));f=gzip.open(p,'wt',newline='') if p.suffix=='.gz' else p.open('x',newline='')
 with f:
  w=csv.DictWriter(f,fieldnames=keys,lineterminator="\n");w.writeheader();w.writerows(clean(rs))
def readcsv(p):
 with gzip.open(p,'rt') if p.suffix=='.gz' else p.open() as f:return list(csv.DictReader(f))
def scaled(j,m):
 d=np.r_[np.ones(24),.1] if m=='B2' else np.ones(24);u,s,vt=np.linalg.svd(j*d,full_matrices=False)
 return d,u,s,vt

def affine(u,m):
 x=M.reference(u,m);r,j=M.objective(u,m,x);d,U,s,V=scaled(j,m);rank=int(sum(s>s[0]*CFG['rank_rtol']))
 if rank<len(d):raise ArithmeticError('NONUNIQUE_AFFINE_STATE')
 K=(d[:,None]*V.T/s)@U.T;delta=-K@r
 independent=np.linalg.lstsq(j,-r,rcond=None)[0];assert np.max(abs(independent-delta))<1e-9
 return dict(x=x,r=r,j=j,d=d,s=s,V=V,K=K,delta=delta,G=K[:,:74],T=K[:,74:]/u['obs']['prior_sigma'],independent_difference=float(max(abs(independent-delta))))

def weak(j,d):
 h=(j*d).T@(j*d);ev,v=np.linalg.eigh(h);mask=ev<=ev[0]+max(.001*abs(ev[0]),100*np.finfo(float).eps*np.linalg.norm(h,2));return v[:,mask]

def decompose(u,m,x,a=None):
 a=affine(u,m) if a is None else a;r,j=M.objective(u,m,x);dn=x-a['x'];dl=a['delta'];eta=r-a['r']-a['j']@dn;dj=j-a['j'];g=j.T@r
 rhs=np.array([g,-a['j'].T@eta,-dj.T@r]);d,s,V=a['d'],a['s'],a['V']
 terms=np.array([d*(V.T@((V@(d*b))/(s*s))) for b in rhs]);difference=dn-dl
 lhs=a['j'].T@(a['j']@difference);back=np.linalg.norm(lhs-rhs.sum(0))/max(1,np.linalg.norm(lhs),sum(np.linalg.norm(b) for b in rhs));err=max(abs(terms.sum(0)-difference))
 assert err<=1e-8 and back<=1e-10,(err,back)
 return a,dict(dn=dn,dl=dl,difference=difference,terms=terms,eta=eta,gradient=g,weak0=weak(a['j'],d),weakN=weak(j,d),reconstruction_max=err,backward_error=back,residual_norm=np.linalg.norm(r),eta_norm=np.linalg.norm(eta),delta_j_norm=np.linalg.norm(dj),r=r,j=j)
