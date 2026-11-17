"""Measurement-only optimizer, conservative durable attempts and exclusive run lock."""
import time,fcntl,contextlib
from scipy.optimize import least_squares
from bridge import *

@contextlib.contextmanager
def lock(path):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('a') as f:
  fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  yield
  fcntl.flock(f.fileno(),fcntl.LOCK_UN)

def once(o,method,start,settings,out,stage,optimizer=least_squares):
 """Existing attempt is terminal for automatic execution, even if result is missing."""
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 with lock(out/'LOCK'):
  # Validate before reserving optimizer attempt, but never retry an existing stage.
  if (out/(stage+'.attempt.json')).exists():raise RuntimeError('ATTEMPT_EXISTS_NO_AUTOMATIC_RERUN')
  f,_,receipt=problem(o,method);start=np.array(start,float)
  if not np.isfinite(start).all():raise ValueError('INVALID_START')
  write(out/(stage+'.attempt.json'),dict(method=method,stage=stage,measurement_sha256=digest(o),consumed_sha256=receipt,settings=settings,start=start,commit=git('rev-parse','HEAD'),source_sha256=sources(),pid=os.getpid(),unix_time=time.time(),status='ATTEMPT_RESERVED_CALL_MAY_HAVE_STARTED'))
  begin=time.perf_counter();result=dict(method=method,stage=stage,estimate=None,status='EXCEPTION',accepted=False,optimizer_calls=1,settings=settings,initialization=start,input_sha256=receipt)
  try:
   fit=optimizer(lambda q:f(q)[0],start,jac=lambda q:f(q)[1],method='trf',loss='linear',x_scale=scales(len(start)),**settings)
   result.update(scipy_status=int(fit.status),scipy_success=bool(fit.success),message=str(fit.message),nfev=int(fit.nfev),njev=int(fit.njev) if fit.njev is not None else None)
   if np.isfinite(fit.x).all():
    r,j=f(fit.x);g=j.T@r;label=classify(fit.x,r,j,fit.status,fit.success)
    info={}
    for key,mat in [('data_information',j[:-4]),('total_information',j)]:
     v=information(mat,1e-8);v.pop('covariance');info[key]=v
    result.update(estimate=fit.x,residual=r,cost=float(r@r/2),gradient=g,gradient_inf=float(max(abs(g))),scaled_gradient_inf=float(max(abs(g*scales(len(start))))),status=label,accepted=label=='ACCEPTED',**info)
   else:result['status']='NONFINITE'
  except Exception as e:result['error']=repr(e)
  result['elapsed_s']=time.perf_counter()-begin;write(out/(stage+'.result.json'),result)
  return clean(result)
