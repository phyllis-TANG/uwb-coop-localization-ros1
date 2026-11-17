#!/usr/bin/env python3
"""Ordinary solve CLI accepts measurements only; never opens reference/ or labels."""
import argparse,time,sys,os
import numpy as np
from scipy.optimize import least_squares
from common import clean,read,write
from model import problem,information

def solve(o,method,cfg,optimizer=least_squares):
 out=dict(method=method,status='INVALID_INPUT',accepted=False,estimate=None,optimizer_calls=0,input_sha256=None)
 begin=time.perf_counter()
 try:
  fun,start,receipt=problem(o,method);out['input_sha256']=receipt
  scales=np.r_[np.ones(24),.1] if method=='M2' else np.ones(24)
  out['initialization']=start.tolist();out['optimizer_calls']=1
  fit=optimizer(lambda q:fun(q)[0],start,jac=lambda q:fun(q)[1],method='trf',loss='linear',x_scale=scales,max_nfev=cfg['max_nfev'],ftol=cfg['ftol'],xtol=cfg['xtol'],gtol=cfg['gtol'])
  out.update(scipy_success=bool(fit.success),scipy_status=int(fit.status),nfev=int(fit.nfev),njev=fit.njev,message=str(fit.message))
  if not np.isfinite(fit.x).all():out['status']='NONFINITE';return clean(out)
  r,j=fun(fit.x);g=j.T@r
  out.update(estimate=fit.x,residual=r,cost=float(r@r/2),gradient=g,gradient_inf=float(np.max(abs(g))),scaled_gradient_inf=float(np.max(abs(g*scales))),data_information=information(j[:-4],cfg['rank_relative_tolerance']),total_information=information(j,cfg['rank_relative_tolerance']))
  if not np.isfinite(np.r_[r,g,out['cost']]).all():out['status']='NONFINITE'
  elif fit.status==0:out['status']='BUDGET_EXHAUSTED'
  elif not fit.success or out['gradient_inf']>cfg['accepted_gradient_inf']:out['status']='NOT_STATIONARY'
  elif out['total_information']['rank']!=len(start):out['status']='RANK_DEFICIENT'
  else:out.update(status='ACCEPTED',accepted=True)
 except Exception as e:
  out.update(status='EXCEPTION' if out['optimizer_calls'] else 'INVALID_INPUT',error=repr(e))
 out['elapsed_s']=time.perf_counter()-begin
 return clean(out)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--measurement',required=True);p.add_argument('--method',choices=['M0','M1','M2'],required=True);p.add_argument('--solver-config',required=True);p.add_argument('--out',required=True)
 a=p.parse_args()
 def deny_reference(event,args):
  if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
   path=os.fsdecode(args[0])
   if 'reference' in path.split(os.sep):raise PermissionError('ordinary solver cannot open reference files')
 sys.addaudithook(deny_reference)
 write(a.out,solve(read(a.measurement),a.method,read(a.solver_config)))
