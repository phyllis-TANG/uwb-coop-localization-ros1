"""Fixed-prior noise sensitivities and deterministic-set outer disks. No optimizer."""
import gzip,hashlib,importlib.util,json
from functools import lru_cache
from pathlib import Path
import numpy as np
from scipy.stats import chi2
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/research/midterm_bias_region_b'
spec=importlib.util.spec_from_file_location('prior_propagation_readonly',ROOT/'tools/midterm_prior_propagation_b/model.py');OLD=importlib.util.module_from_spec(spec);spec.loader.exec_module(OLD)
def config():return json.loads((DOC/'CONFIG.json').read_text())
def canonical(x):return OLD.canonical(x)
def digest(x):return OLD.digest(x)
def save(p,x):return OLD.save(p,x)
def source():
 c=config();p=ROOT/c['source_archive'];assert hashlib.sha256(p.read_bytes()).hexdigest()==c['source_sha256'];out={};pairs=0;all_refs={}
 with gzip.open(p,'rt') as f:
  for line in f:
   z=json.loads(line)
   if z['type']!='PAIR':continue
   pairs+=1;v=z['value'];q=v['q'];m=v['method']
   for role in ['base','target']:
    u=v[role+'_input'];r=v[role];ref=(digest(u),m)
    state=digest({k:r.get(k) for k in ['estimate','accepted','cost','category','gradient_inf']})
    if ref in all_refs:assert all_refs[ref]==state
    all_refs[ref]=state
   for role in (['target'] if v['study']=='new' else ['base','target']):
    u=v[role+'_input'];r=v[role];mech='perturbed_survey' if v['study']=='new' else ('fixed_correct' if role=='base' else 'fixed_survey');condition=q['id'].split('-s')[0] if v['study']=='new' else f"{q['geometry']}-{q['sigma']}-{mech}"
    key=f"{condition}-s{q['seed']}-{m}";assert key not in out
    out[key]=dict(id=key,condition=condition,geometry=q['geometry'],sigma=q['sigma'],mechanism=mech,method=m,seed=q['seed'],input=u,result=r,input_sha256=digest(u))
 assert pairs==c['expected']['pair_records'] and len(out)==c['expected']['unique_method_endpoints'] and len(all_refs)==len(out)
 return list(out.values())
def quantities(j,h,sigma,scale,c,exact=False):
 n=j.shape[1];out=dict(status='UNAVAILABLE',G=None,T=None,C=None,curvature=None)
 if not np.isfinite(j).all() or not np.isfinite(h).all():return dict(out,status='NONFINITE_INFORMATION')
 hs=scale[:,None]*h*scale;ev=np.linalg.eigvalsh((hs+hs.T)/2)
 if exact:
  if ev[0]<=max(c['hessian_absolute_floor'],ev[-1]*c['hessian_relative_floor']):return dict(out,status='NONPOSITIVE_OR_ILL_CONDITIONED_HESSIAN')
  inv=scale[:,None]*np.linalg.solve(hs,np.diag(scale))
 else:
  _,s,vt=np.linalg.svd(j*scale,full_matrices=False)
  if sum(s>s[0]*c['rank_relative'])<n:return dict(out,status='RANK_DEFICIENT')
  inv=(scale[:,None]*vt.T/s**2)@(vt*scale)
 A=j[:-4];rhs=np.zeros((n,4));rhs[:4]=np.eye(4)/sigma**2;G=inv@A.T;T=inv@rhs;C=G@G.T
 if not np.isfinite(C).all() or not np.isfinite(T).all():return dict(out,status='NONFINITE_PROPAGATION')
 return dict(status='AVAILABLE',G=G,T=T,C=(C+C.T)/2,curvature=None if exact else (inv+inv.T)/2)
def local(u,m,x,view,c):
 if x is None or not np.isfinite(x).all():return dict(status='NO_FINITE_ESTIMATE',G=None,T=None,C=None,curvature=None)
 point=OLD.M.reference(u,m) if view=='oracle_truth_GN' else np.array(x);r,j=OLD.M.objective(u,m,point)
 h=OLD.exact_hessian(u,m,point) if view=='endpoint_exact' else j.T@j
 scale=np.r_[np.full(24,c['position_scale']),c['bias_scale']] if m=='B2' else np.full(24,c['position_scale'])
 return quantities(j,h,u['obs']['prior_sigma'],scale,c,view=='endpoint_exact')
def marginal(P,c):
 if P is None:return 'GLOBAL_UNAVAILABLE',None
 if not np.isfinite(P).all():return 'NONFINITE_MARGINAL',None
 ev=np.linalg.eigvalsh(P)
 if ev[0]<=max(0,ev[-1]*c['marginal_relative_floor']):return 'NONPOSITIVE_OR_SINGULAR_MARGINAL',None
 return 'AVAILABLE',ev

@lru_cache(maxsize=8)
def quantile(confidence):return float(chi2.ppf(confidence,2))

def region(P,B,rho,error,c,ellipse=False):
 reason,ev=marginal(P,c)
 if reason!='AVAILABLE':return dict(reason=reason,covered=None,radius=None,area=None,noise_radius=None,bias_radius=None)
 q=quantile(c['confidence']);nr=float(np.sqrt(q*ev[-1]));br=float(rho*np.linalg.svd(B,compute_uv=False)[0]) if B is not None else 0.;rad=nr+br
 covered=bool(error@np.linalg.solve(P,error)<=q) if ellipse else bool(np.linalg.norm(error)<=rad)
 return dict(reason='AVAILABLE',covered=covered,radius=nr if ellipse else rad,area=float(np.pi*q*np.sqrt(np.prod(ev))) if ellipse else float(np.pi*rad*rad),noise_radius=nr,bias_radius=br)
