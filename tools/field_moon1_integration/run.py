"""Six-call frozen field smoke batch with durable attempts; no automatic orphan retry."""
import fcntl,os,subprocess,time,sys
from scipy.optimize import least_squares
from common import *
from inputs import prepare
from model import objective

def main(out):
 cfg=read(DOC/'CONFIG.json');out=Path(out);out.mkdir(parents=True,exist_ok=True)
 with (out/'LOCK').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  freeze=read(DOC/'FREEZE.json')
  for p,h in freeze['hashes'].items(): assert digest(ROOT/p)==h,p
  # An existing batch is read-only, including any orphan attempt.
  if (out/'RUN.json').exists():raise RuntimeError('Existing batch: use verify.py, do not rerun')
  write(out/'RUN.json',{'freeze_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'call_limit':6,'formal_runs':0,'freeze':freeze})
  calls=0
  for case in cfg['cases']:
   o=clean(prepare(case));write(out/'measurements'/f'{case}.json',o)
   for method in cfg['methods']:
    joint=method=='joint';f=objective(o,joint);q=np.array([o['cars'][c]['initial'] for c in ['car1','car2']]).ravel()
    name=case+'_'+method;assert calls<cfg['optimizer_call_limit']
    write(out/'attempts'/f'{name}.json',{'case':case,'method':method,'input_sha256':digest(out/'measurements'/f'{case}.json'),'call_number':calls+1,'optimizer':cfg['optimizer']})
    calls+=1;t=time.perf_counter();opt=cfg['optimizer']
    try:
     fit=least_squares(f.fun,q,jac=f.jac,method='trf',tr_solver='exact',loss='linear',max_nfev=opt['max_nfev'],ftol=opt['ftol'],xtol=opt['xtol'],gtol=opt['gtol'])
     r,j=f.evaluate(fit.x);g=j.T@r
     write(out/'estimates'/f'{name}.json',{'case':case,'method':method,'x':fit.x,'residual':r,'jacobian':j,'cost':float(r@r/2),'gradient_inf':float(max(abs(g))),'scipy_success':bool(fit.success),'status':int(fit.status),'message':str(fit.message),'nfev':int(fit.nfev),'wall_s':time.perf_counter()-t,'finite':bool(np.isfinite(fit.x).all()),'stationary_1e_5':bool(max(abs(g))<=1e-5),'rank_with_prior':int(np.linalg.matrix_rank(j)),'wall_factors':f.wall_factor_count,'peer_factors':len(f.peer_indices)})
    except Exception as e:write(out/'estimates'/f'{name}.json',{'case':case,'method':method,'failure':repr(e),'wall_s':time.perf_counter()-t})
  write(out/'COMPLETE.json',{'optimizer_calls':calls,'formal_runs':0})
if __name__=='__main__':main(sys.argv[1])
