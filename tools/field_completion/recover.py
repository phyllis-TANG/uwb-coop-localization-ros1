"""One uniformly budgeted numerical recovery for ALL 16 full-bag endpoints."""
import fcntl,subprocess,time
from scipy.optimize import least_squares
from fcommon import *
from objective import Field
from execute import packresult

def run(source,out):
 source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 config=read(DOC/'RECOVERY_CONFIG.json');freeze=read(DOC/'RECOVERY_FREEZE.json')
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(),'dirty checkout'
 subprocess.check_call(['git','cat-file','-e','HEAD:docs/research/field_completion/RECOVERY_FREEZE.json'],cwd=ROOT)
 for p,h in freeze['hashes'].items():assert digest(ROOT/p)==h,p
 for p,h in freeze['source_batch_hashes'].items():assert digest(source/p)==h,p
 with (out/'LOCK').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if (out/'RUN.json').exists():raise RuntimeError('existing recovery is read-only')
  write(out/'RUN.json',{'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'freeze':freeze,'optimizer':config,'formal_runs':0})
  count=0
  for case in config['cases']:
   o=read(source/'measurements'/f'{case}.json');write(out/'measurements'/f'{case}.json',o)
   for method in config['methods']:
    name=case+'_'+method;prior=read(source/'estimates'/(name+'_P1.json'));f=Field(o,method);q=np.array(prior['x']);assert count<16
    write(out/'attempts'/(name+'_P2.json'),{'call':count+1,'source':case,'initial':q,'scales':f.scales,'parent_sha256':digest(source/'estimates'/(name+'_P1.json')),'optimizer':config['optimizer']});count+=1;t=time.perf_counter()
    try:
     fit=least_squares(f.fun,q,jac=f.jac,method='trf',tr_solver='exact',loss='linear',x_scale=f.scales,**config['optimizer'])
     result=packresult(f,fit.x,fit,time.perf_counter()-t)
    except Exception as e:result={'failure':repr(e)}
    write(out/'estimates'/(name+'_P2.json'),result);print(name,result.get('gradient_inf',result.get('failure')),flush=True)
  write(out/'COMPLETE.json',{'calls':count,'formal_runs':0})
if __name__=='__main__':run(*sys.argv[1:])
