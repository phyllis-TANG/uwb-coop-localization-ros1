"""PR117 endpoint audit, no optimizer calls; exact Hessian and local predictions."""
import argparse
from pathlib import Path
import numpy as np
from bridge import *

def run(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 obs=unpack(OLD/'results/measurements.json.gz');fits=unpack(OLD/'results/estimates.json.gz');refs=unpack(OLD/'results/reference.json.gz')
 plan={i['id']:i for i in read(OLD/'results/PLAN.json')};rows=[];details={};maxdiff=0.;hfdmax=0.;recomputed=[]
 for name,fit in sorted(fits.items()):
  uid,method=name.split('-');o=obs[uid];q=np.array(fit['estimate']);f,_,_=problem(o,method);r,j=f(q);rr,jj=independent(o,method,q)
  np.testing.assert_allclose(r,rr,atol=1e-10,rtol=0);np.testing.assert_allclose(j,jj,atol=1e-10,rtol=0)
  np.testing.assert_allclose(r,fit['residual'],atol=1e-12,rtol=0);g=j.T@r;cost=float(r@r/2)
  assert abs(cost-fit['cost'])<1e-10;np.testing.assert_allclose(g,fit['gradient'],atol=1e-10,rtol=0)
  label=classify(q,r,j,fit['scipy_status'],fit['scipy_success']);assert label==fit['status']
  for which,mat in [('data_information',j[:-4]),('total_information',j)]:
   inf=information(mat,1e-8);assert inf['rank']==fit[which]['rank']
   np.testing.assert_allclose(inf['singular_values'],fit[which]['singular_values'],atol=1e-10,rtol=1e-12)
   np.testing.assert_allclose(inf['covariance'],fit[which]['covariance'],atol=1e-12,rtol=1e-10)
  gn,h=curvature(o,method,q);eg=np.linalg.eigvalsh(gn);eh=np.linalg.eigvalsh(h);step=-np.linalg.solve(h,g);pred=float(-g@step-.5*step@h@step)
  ld=np.longdouble;lr,lj=independent(o,method,q,ld);lr2,_=independent(o,method,np.array(q,ld)+np.array(step,ld),ld)
  trial_r,_=f(q+step);trial=float(cost-trial_r@trial_r/2);ldtrial=float((lr@lr-lr2@lr2)/2)
  truth=np.array(refs[uid]['track']['antenna_xyz_m'])[:,:,:2].ravel();error=float(np.sqrt(np.mean((q[:24]-truth)**2)))
  d=dict(id=name,window=plan[uid]['window'],method=method,old_status=fit['status'],recomputed_status=label,scipy_status=fit['scipy_status'],message=fit['message'],nfev=fit['nfev'],cost=cost,gradient_inf=float(max(abs(g))),scaled_gradient_inf=float(max(abs(g*scales(len(q))))),data_rank=fit['data_information']['rank'],total_rank=fit['total_information']['rank'],gn_min=float(eg[0]),gn_max=float(eg[-1]),exact_min=float(eh[0]),exact_max=float(eh[-1]),hessian_relative_change=float(np.linalg.norm(h-gn,2)/np.linalg.norm(gn,2)),predicted_xy_component_max_m=float(max(abs(step[:24]))),predicted_xy_vector_max_m=float(max(np.linalg.norm(step[:24].reshape(-1,2),axis=1))),predicted_bias_step_m=float(step[-1]) if method=='M2' else None,predicted_drop=pred,float64_trial_drop=trial,longdouble_trial_drop=ldtrial,coordinate_ulp_max_m=float(max(abs(np.spacing(q[:24])))),cost_ulp=float(np.spacing(cost)),coordinate_rmse_m=error,predicted_step_over_rmse=float(max(abs(step[:24]))/error),prediction_only=True)
  if label=='NOT_STATIONARY':
   eps=1e-5;fd=np.column_stack([(lambda a,b:(a[1].T@a[0]-b[1].T@b[0])/(2*eps))(f(q+e),f(q-e)) for e in np.eye(len(q))*eps]);err=float(np.max(abs(fd-h)));hfdmax=max(hfdmax,err);assert err<2e-5
   d['hessian_fd_error']=err;details[name]=dict(gn=gn,exact=h,gradient=g,newton_step=step,physical_scales=scales(len(q)),hessian_fd_error=err)
  rows.append(d)
 # Select accepted controls round-robin over sorted (window,method) strata, fixed IDs, no truth/errors.
 groups={}
 for name,fit in sorted(fits.items()):
  if fit['accepted']:
   uid,method=name.split('-');groups.setdefault((plan[uid]['window'],method),[]).append(name)
 selected=[];depth=0
 while len(selected)<11:
  for key in sorted(groups):
   if depth<len(groups[key]) and len(selected)<11:selected.append(groups[key][depth])
  depth+=1
 failures=[r['id'] for r in rows if r['old_status']=='NOT_STATIONARY'];assert len(failures)==11
 # CSV columns uniform (FD present only for failures).
 for r in rows:r.setdefault('hessian_fd_error',None)
 csvwrite(out/'ENDPOINTS.csv',rows);write(out/'CURVATURE.json',details)
 write(out/'CASES.json',dict(failures=failures,controls=selected,selection='accepted endpoints: round-robin sorted (window,method), within-stratum ascending ID, until 11; no truth/error selection'))
 write(out/'AUDIT.json',dict(passed=True,old_accepted=169,old_not_stationary=11,optimizer_calls=0,hessian_fd_max_error=hfdmax,longdouble_mantissa=np.finfo(np.longdouble).nmant,source_sha256=sources(),inputs={str(p.relative_to(ROOT)):filehash(p) for p in sorted((OLD/'results').glob('*.json.gz'))},argv=__import__('sys').argv))
 print('PASS 180 endpoints; 169/11 unchanged; max Hessian FD',hfdmax)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();run(a.out)
