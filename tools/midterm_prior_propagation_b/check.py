"""No real optimizer calls: analytic Hessian vs independent central differences and affine QR identity."""
import argparse,tempfile
from pathlib import Path
from model import *
def check():
 src=source_units();c=config();rows=[];h=c['analysis']['fd_step_m'];V=load_module('validation_check','tools/midterm_simulation_validation/core.py')
 for _,_,idx in c['bases']:
  v=src[f'p{idx:02}-s281117001'];u=v['input']
  for m in c['methods']:
   x=np.array(v['results'][m]['P1']['estimate']);r,j=M.objective(u,m,x);H=exact_hessian(u,m,x);fd=np.empty_like(H)
   for k in range(len(x)):
    d=np.zeros_like(x);d[k]=h;rp,jp=M.objective(u,m,x+d);rm,jm=M.objective(u,m,x-d);fd[:,k]=(jp.T@rp-jm.T@rm)/(2*h)
   rhs=np.zeros((len(x),4));rhs[:4]=np.eye(4)/u['obs']['prior_sigma']**2;fc=np.empty_like(rhs)
   for k in range(4):
    d=np.eye(4)[k]*h;rp,jp=M.objective(perturb(u,d),m,x);rm,jm=M.objective(perturb(u,-d),m,x);fc[:,k]=(jp.T@rp-jm.T@rm)/(2*h)
   delta=np.array([.001,-.002,.003,-.004]);vprior=np.r_[np.zeros(len(r)-4),delta/u['obs']['prior_sigma']];linear=np.linalg.lstsq(j,vprior,rcond=None)[0];T=transfer(u,m,x)['T'];err=float(np.max(abs(fd-H))/max(1,np.max(abs(H))));sign=float(np.max(abs(fc+rhs)));ident=float(np.max(abs(linear-T@delta)));frozen,_,_=V.objective(c['frozen_model'],u['obs'],m);rr,jj=frozen(x)
   assert err<c['analysis']['fd_relative_tolerance'] and sign<1e-5 and ident<1e-9
   assert np.allclose(r,rr,atol=1e-10,rtol=0) and np.allclose(j,jj,atol=1e-10,rtol=0)
   rows.append(dict(base=idx,method=m,hessian_fd_relative_error=err,center_gradient_sign_error=sign,affine_QR_identity_error=ident))
 # Failure-path fixture: no scipy least_squares invocation.
 u=next(iter(src.values()))['input']
 def boom(*args,**kw):raise RuntimeError('intentional fixture')
 bad=V.solve_stage(c['frozen_model'],u,'B2','P0',solver=boom);skipped=V.solve_stage(c['frozen_model'],u,'B2','P1',bad,solver=boom)
 assert bad['estimate'] is None and bad['position_mse']==[None,None] and skipped['category']=='SKIPPED_INVALID_P0'
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)/'bad.json.gz';save(p,bad);assert read(p)==bad
  try:save(p,bad);raise AssertionError('overwrite allowed')
  except FileExistsError:pass
 return dict(checks=rows,exception_saved=True,invalid_P0_skipped=True,exclusive_write=True,actual_optimizer_calls=0,planned_method_runs=len(plans(c))*len(c['methods']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();z=check();save(a.out,z);print(json.dumps(z,indent=2))
