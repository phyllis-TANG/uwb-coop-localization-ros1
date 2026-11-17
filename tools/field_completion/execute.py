"""Fixed 38-call maximum batch. Files committed before execution, attempts durable."""
import fcntl,subprocess,time,gzip
from scipy.optimize import least_squares
from fcommon import *
from adapter import make
from objective import Field
from model import objective as old_objective

def packresult(f,q,fit,elapsed):
 r,j=f.evaluate(q);g=j.T@r
 return {'x':q,'residual':r,'cost':float(r@r/2),'gradient_inf':float(np.max(abs(g))),'gradient':g,'scipy_status':int(fit.status),'scipy_success':bool(fit.success),'message':str(fit.message),'nfev':int(fit.nfev),'elapsed_s':elapsed,'finite':bool(np.isfinite(q).all() and np.isfinite(r).all() and np.isfinite(j).all()),'stationary_1e_5':bool(np.max(abs(g))<=1e-5),'jacobian_sha256':__import__('hashlib').sha256(j.tobytes()).hexdigest()}

def main(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);cfg=read(DOC/'CONFIG.json');freeze=read(DOC/'FREEZE.json')
 assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True).strip(),'dirty worktree'
 subprocess.check_call(['git','cat-file','-e','HEAD:docs/research/field_completion/FREEZE.json'],cwd=ROOT)
 for p,h in freeze['hashes'].items():assert digest(ROOT/p)==h,p
 with (out/'LOCK').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if (out/'RUN.json').exists():raise RuntimeError('Read-only existing batch; no automatic rerun')
  write(out/'RUN.json',{'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'freeze':freeze,'max_calls':38,'formal_runs':0})
  calls=0
  def invoke(name,f,q,scales,opt,source):
   nonlocal calls
   assert calls<38
   write(out/'attempts'/f'{name}.json',{'call':calls+1,'source':source,'optimizer':opt,'initial':q,'scales':scales})
   calls+=1;start=time.perf_counter()
   try:
    fit=least_squares(f.fun,q,jac=f.jac,method='trf',tr_solver='exact',loss='linear',x_scale=scales,**opt)
    result=packresult(f,fit.x,fit,time.perf_counter()-start)
   except Exception as e:result={'failure':repr(e),'elapsed_s':time.perf_counter()-start}
   write(out/'estimates'/f'{name}.json',result);print(name,result.get('gradient_inf',result.get('failure')),flush=True)
   return result
  with gzip.open(ROOT/'docs/research/field_moon1_integration/results/portable.json.gz','rt') as stream:old=json.load(stream)
  for rel,e in old.items():
   if not rel.startswith('estimates/') or 'x' not in e:continue
   name=Path(rel).stem;o=old['measurements/'+e['case']+'.json'];f=old_objective(o,e['method']=='joint');q=np.array(e['x']);r,j=f.evaluate(q)
   delta=np.linalg.lstsq(j,-r,rcond=None)[0]
   write(out/'diagnosis'/f'{name}.json',{'old':e,'gn_predicted_step':delta,'gn_max_xy_step_m':float(np.max(np.linalg.norm(delta.reshape(2,-1,3)[:,:,:2],axis=2))),'gn_prediction_only':True})
   write(out/'measurements'/f'old_{name}.json',o)
   invoke('old_'+name,f,q,np.tile([1.,1.,.1],len(q)//3),cfg['P1'],'old_'+name)
  for case in cfg['cases']:
   o=make(case);write(out/'measurements'/f'{case}.json',o)
   if case not in cfg['fit_cases']:continue
   for method in cfg['methods']:
    f=Field(o,method);name=case+'_'+method
    p0=invoke(name+'_P0',f,f.initial(),f.scales,cfg['P0'],case)
    if p0.get('finite'):invoke(name+'_P1',f,np.array(p0['x']),f.scales,cfg['P1'],case)
  write(out/'COMPLETE.json',{'calls':calls,'formal_runs':0})
if __name__=='__main__':main(sys.argv[1])
