"""Measurement-only calls with a durable bounded reservation ledger."""
import time
from scipy.optimize import least_squares
from tcommon import *
from tmodel import problem,scales,information,classify

def reserve(root,key,identity):
 root=Path(root);p=root/'attempts'/(key+'.json');p.parent.mkdir(exist_ok=True)
 with lock(root/'BUDGET_LOCK'):
  if p.exists():raise RuntimeError('ATTEMPT_EXISTS_NO_AUTOMATIC_RERUN')
  budget=read(root/'BUDGET.json');used=len(list((root/'attempts').glob('*.json')))
  if used>=budget['limit']:raise RuntimeError('HARD_CALL_LIMIT')
  write(p,dict(identity,reservation=used+1,status='CALL_MAY_HAVE_STARTED',pid=os.getpid(),unix_time=time.time()))
 return p

def once(o,method,start,settings,root,key,stage,optimizer=least_squares):
 f,_,h=problem(o,method);start=np.asarray(start,float)
 if not np.isfinite(start).all():raise ValueError('INVALID_START')
 freeze=read(Path(root)/'EXECUTION.json')
 reserve(root,key+'-'+stage,dict(unit_method=key,stage=stage,input_sha256=digest(o),consumed_sha256=h,start=start,settings=settings,code_sha=freeze['commit'],source_hash=digest(freeze['source_sha256']),execution_sha256=filehash(Path(root)/'EXECUTION.json')))
 record=dict(method=method,stage=stage,estimate=None,status='EXCEPTION',accepted=False,optimizer_calls=1,input_sha256=h,initialization=start);began=time.perf_counter()
 try:
  fit=optimizer(lambda q:f(q)[0],start,jac=lambda q:f(q)[1],method='trf',loss='linear',x_scale=scales(len(start)),**settings)
  record.update(scipy_status=int(fit.status),scipy_success=bool(fit.success),message=str(fit.message),nfev=int(fit.nfev),njev=int(fit.njev) if fit.njev is not None else None)
  if np.isfinite(fit.x).all():
   r,j=f(fit.x);g=j.T@r;label=classify(fit.x,r,j,fit.status,fit.success);nr=48 if method=='M0' else 54
   record.update(estimate=fit.x,residual=r,cost=float(r@r/2),gradient=g,gradient_inf=float(max(abs(g))),scaled_gradient_inf=float(max(abs(g*scales(len(start))))),status=label,accepted=label=='ACCEPTED',range_information=information(j[:nr]),data_information=information(j[:-4]),total_information=information(j))
  else:record['status']='NONFINITE'
 except Exception as e:record['error']=repr(e)
 record['elapsed_s']=time.perf_counter()-began;write(Path(root)/'estimates'/key/(stage+'.json'),record);return clean(record)

def unit(measurement,root,uid,methods):
 root=Path(root);freeze=read(root/'EXECUTION.json');assert sources()==freeze['source_sha256'],'SOURCE_CHANGED'
 o=read(measurement);sc=freeze['solver'];(root/'unit_locks').mkdir(exist_ok=True)
 with lock(root/'unit_locks'/uid):
  for method in methods:
   key=uid+'-'+method;folder=root/'estimates'/key;folder.mkdir(parents=True,exist_ok=False)
   _,start,_=problem(o,method);p0=once(o,method,start,sc['P0'],root,key,'P0');p1=None
   if p0['estimate'] is not None and np.isfinite(p0['estimate']).all():p1=once(o,method,p0['estimate'],sc['P1'],root,key,'P1')
   final=p1 if p1 is not None and p1['estimate'] is not None else p0
   ok=p1 is not None and p1['estimate'] is not None
   write(folder/'FINAL.json',dict(method=method,stage=final['stage'],estimate=final['estimate'],status=final['status'] if ok else 'NO_FINITE_P1',accepted=bool(ok and final['accepted']),optimizer_calls=1+int(p1 is not None)))

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--measurement',required=True);p.add_argument('--root',required=True);p.add_argument('--unit',required=True);a=p.parse_args()
 def guard(event,args):
  if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)) and 'reference' in os.fsdecode(args[0]).split(os.sep):raise PermissionError('reference forbidden')
 sys.addaudithook(guard);unit(a.measurement,a.root,a.unit,['M0','M1','M2','M3'])
