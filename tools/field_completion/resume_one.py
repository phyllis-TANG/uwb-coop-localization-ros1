"""Continue only never-attempted P2 items. Orphan calls remain failures, never retried."""
import fcntl,time,subprocess
from scipy.optimize import least_squares
from fcommon import *
from objective import Field
from execute import packresult

def resume(source,out,case,method):
 source=Path(source);out=Path(out);config=read(DOC/'RECOVERY_CONFIG.json');run=read(out/'RUN.json')
 for p,h in run['freeze']['hashes'].items():assert digest(ROOT/p)==h,p
 for p,h in run['freeze']['source_batch_hashes'].items():assert digest(source/p)==h,p
 assert case in config['cases'] and method in config['methods']
 with (out/'LOCK').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  name=case+'_'+method+'_P2';attempt=out/'attempts'/(name+'.json')
  if attempt.exists():raise RuntimeError('Already attempted, including orphan: never rerun')
  o=read(source/'measurements'/f'{case}.json')
  if not (out/'measurements'/f'{case}.json').exists():write(out/'measurements'/f'{case}.json',o)
  priorpath=source/'estimates'/f'{case}_{method}_P1.json';prior=read(priorpath);f=Field(o,method);q=np.array(prior['x']);count=len(list((out/'attempts').glob('*.json')));assert count<16
  write(attempt,{'call':count+1,'source':case,'initial':q,'scales':f.scales,'parent_sha256':digest(priorpath),'optimizer':config['optimizer'],'recovery_driver_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()})
  t=time.perf_counter()
  try:
   fit=least_squares(f.fun,q,jac=f.jac,method='trf',tr_solver='exact',loss='linear',x_scale=f.scales,**config['optimizer']);result=packresult(f,fit.x,fit,time.perf_counter()-t)
  except Exception as e:result={'failure':repr(e)}
  write(out/'estimates'/(name+'.json'),result);print(name,result.get('gradient_inf',result.get('failure')),flush=True)
if __name__=='__main__':resume(*sys.argv[1:])
