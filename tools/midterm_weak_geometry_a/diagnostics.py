"""Preselected first-seed exact Hessian/profile diagnostics; no optimization."""
from common import *
import argparse

def exact_hessian(u,m,x):
    r,j=objective(u,m,x);h=j.T@j;p=x[:24].reshape(6,2,2);a=np.array(u['obs']['anchors']);sigma=u['obs']['range_sigma'];eye=np.eye(2)
    for t in range(6):
      for car in range(2):
        ix=slice(4*t+2*car,4*t+2*car+2)
        for k in range(4):
          delta=p[t,car]-a[k];dist=np.linalg.norm(delta);v=delta/dist;h[ix,ix]+=r[9*t+4*car+k]*(eye-np.outer(v,v))/(sigma*dist)
      delta=p[t,1]-p[t,0];dist=np.linalg.norm(delta);v=delta/dist;s=r[9*t+8]*(eye-np.outer(v,v))/(sigma*dist);i=slice(4*t,4*t+2);k=slice(4*t+2,4*t+4);h[i,i]+=s;h[k,k]+=s;h[i,k]-=s;h[k,i]-=s
    return h

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False);sel=read(args.results/'readback/SELECTION.json');ends={(z['id'],z['method'],z['init']):z for z in records(args.results/'ENDPOINTS.jsonl.gz')};hrows=[];profiles=[];maxfd=0.;maxcov=0.
    for rec in records(DOC/'INPUTS.jsonl.gz'):
      if rec['input']['seed']!=CFG['representative_seed']:continue
      u=rec['input']
      for m in CFG['methods']:
        chosen=next(s for s in sel if s['id']==rec['id'] and s['method']==m);original=rec['original'][m]['P1'];candidates={'I0':original,**{i:ends[(rec['id'],m,i)]['stages']['P1'] for i in CFG['initializations']}}
        for mode,ini in [('original','I0'),('selected',chosen['selected_init'])]:
          if ini is None:continue
          x=np.array(candidates[ini]['estimate']);r,j=objective(u,m,x);h=exact_hessian(u,m,x);scale=np.r_[np.ones(24),.1] if m=='B2' else np.ones(24);gn=j.T@j;sh=h*scale[:,None]*scale;sgn=gn*scale[:,None]*scale;ev=np.linalg.eigvalsh(sh)
          errors=[]
          for step in [1e-5,5e-6]:
            fd=np.empty_like(h)
            for k in range(len(x)):
              dx=np.zeros_like(x);dx[k]=step;rp,jp=objective(u,m,x+dx);rm,jm=objective(u,m,x-dx);fd[:,k]=(jp.T@rp-jm.T@rm)/(2*step)
            errors.append(float(np.linalg.norm(fd-h)/np.linalg.norm(h)))
          maxfd=max(maxfd,*errors);assert max(errors)<1e-6
          a=algebra(j,m,SOURCE,u['condition']['mechanism']);diff=None
          if a['curvature'] is not None:
            inv=np.linalg.solve(gn,np.eye(len(x)));diff=float(np.linalg.norm(inv-a['curvature'])/np.linalg.norm(inv));assert diff<1e-6;maxcov=max(maxcov,diff)
          hrows.append(dict(id=rec['id'],method=m,mode=mode,init=ini,min_scaled_exact_eigenvalue=float(ev[0]),min_scaled_gn_eigenvalue=float(np.linalg.eigvalsh(sgn)[0]),negative_eigenvalues=int(sum(ev< -1e-8*max(abs(ev)))),second_order_relative_norm=float(np.linalg.norm(sh-sgn)/np.linalg.norm(sgn)),fd_relative_1e5=errors[0],fd_relative_5e6=errors[1],covariance_inverse_relative_difference=diff))
        accepted=[(i,z) for i,z in candidates.items() if z['accepted']]
        if accepted and original['endpoint_valid']:
          far=max(accepted,key=lambda iz:(distance(original['estimate'],iz[1]['estimate']),iz[0]));x=np.array(original['estimate']);y=np.array(far[1]['estimate'])
          for t in np.linspace(0,1,101):
            r,_=objective(u,m,x+t*(y-x));profiles.append(dict(id=rec['id'],method=m,from_init='I0',to_init=far[0],lambda_value=float(t),cost=float(r@r/2),endpoint_distance_m=distance(x,y)))
    csvsave(out/'HESSIAN.csv',hrows);csvsave(out/'PROFILES.csv',profiles);save(out/'CHECKS.json',dict(representative_seed=CFG['representative_seed'],hessian_endpoints=len(hrows),profile_points=len(profiles),max_finite_difference_relative_error=maxfd,max_inverse_relative_difference=maxcov,optimizer_calls=0));print(read(out/'CHECKS.json'))
if __name__=='__main__':main()
