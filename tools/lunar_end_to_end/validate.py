"""Pre-freeze identities, independent derivative, generator and recovery checks."""
import copy,json,subprocess,sys,tempfile,time
from pathlib import Path
import numpy as np
from inputs import *
from model import problem,solve
from checker import residual,jacobian
from runner import progress,timeout

def main():
 checks={};windows=json.loads((DOC/'WINDOWS.json').read_text());w=windows[0];o,ref=generate(w,2026111601,'normal','white',noiseless=True);q=np.array(ref['xyz'])[:,:,:2].ravel();mx=0
 for method in ['M0','M1','M2','M3']:
  f,x=problem(o,method);v=np.r_[q,np.zeros(len(x)-24)];r,j=f(v);assert abs(r).max()<1e-10
  test=x+.01*np.sin(np.arange(len(x)));r,j=f(test);ri,_=residual(o,method,test);ji=jacobian(o,method,test);mx=max(mx,float(abs(j-ji).max()));assert np.allclose(r,ri,atol=1e-10) and abs(j-ji).max()<1e-6
 checks['noiseless_and_independent_jacobian']=dict(passed=True,max_jacobian_difference=mx)
 # Compare equations with fixed PR125 in an isolated interpreter to avoid module shadowing.
 old=dict(schema=1,frame='moon_map',units=['m','s'],times_s=o['times_s'],anchors_xyz_m=o['anchors'],height_mode='given_world_vertical_height_not_estimated',heights_m=o['heights'],ranges_m=np.array(o['ranges']).ravel().tolist(),global_xy_increments_m=o['increments'],motion_sigmas_m=[.02,.02],range_sigma_m=.04,prior_center_xy_m=o['prior'],prior_sigma_m=.5,initialization_offset_m=[.2,-.15,-.2,.15],peer_direction='one_car1_to_car2')
 script="import sys,json;sys.path.insert(0,'/home/ubuntu22/uwb-moon1-trend-height-sensitivity/tools/moon1_trend_height_eval');from tmodel import problem;o=json.loads(sys.stdin.read());out={};\nfor m in ['M0','M1','M2','M3']:\n f,x,h=problem(o,m);r,j=f(x);out[m]=[x.tolist(),r.tolist(),j.tolist()]\nprint(json.dumps(out))"
 data=json.loads(subprocess.check_output([sys.executable,'-c',script],input=json.dumps(old).encode()))
 for m,(x,r,j) in data.items():
  f,xx=problem(o,m);rr,jj=f(xx);assert np.allclose(x,xx) and np.allclose(r,rr,atol=1e-10) and np.allclose(j,jj,atol=1e-10)
 checks['fixed_PR125_equations_all_methods']=True
 C=np.diag([1,-1,-1]);assert np.linalg.det(C)==1 and np.allclose(C@C,np.eye(3));checks['coordinate_units']=dict(rotation_det=1,source_timestamp='integer ns subtraction before seconds',metres=True)
 # Lever derivative and static SE(2) gauge: delta center = -R S lever delta yaw preserves antenna.
 theta=.7;l=np.array([.12,-.08]);R=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]]);S=np.array([[0,-1],[1,0]]);J=np.column_stack([np.eye(2),R@S@l]);null=np.r_[-R@S@l,1];assert np.linalg.norm(J@null)<1e-14;checks['static_lever_yaw_null']=dict(rank=int(np.linalg.matrix_rank(J)),null_residual=float(np.linalg.norm(J@null)),limitation='core XY model has no yaw state; analytic demonstration only')
 z=np.random.default_rng(2026111602).normal(size=(5,100000));e=ar1(z);cov=e@e.T/e.shape[1];theory=.8**abs(np.arange(5)[:,None]-np.arange(5));err=float(abs(cov-theory).max());assert err<.02;checks['AR1_stationary_covariance']=dict(max_abs_error=err,tolerance=.02,theory=theory.tolist(),samples=100000)
 base,_=generate(w,2026111601,'normal','white');plus,_=generate(w,2026111601,'normal','white','time_plus');minus,_=generate(w,2026111601,'normal','white','time_minus');d=(np.array(plus['ranges'])[:,8]-np.array(minus['ranges'])[:,8])/.1;xyz=np.array(w['xyz_m']);v=np.gradient(xyz[:,1],.2,axis=0);los=(xyz[:,1]-xyz[:,0]);pred=(los*v).sum(1)/np.linalg.norm(los,axis=1);assert np.sign(d).tolist()==np.sign(pred).tolist();checks['time_offset_sign']=dict(positive_means='Car2 sampled later than labeled peer time',numeric_derivative=d.tolist(),velocity_projection=pred.tolist())
 altered=copy.deepcopy(base);npra=np.array(altered['ranges']);npra[:,8]+=10;altered['ranges']=npra.tolist();f,x=problem(base,'M0');g,xx=problem(altered,'M0');assert np.array_equal(x,xx) and np.array_equal(f(x)[0],g(x)[0]);checks['M0_peer_invariance']=True
 try:problem(dict(base,reference=ref),'M0');raise AssertionError('Leak accepted')
 except ValueError:checks['reference_schema_rejection']=True
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);plan=[dict(key=k,group='test') for k in ['done','interrupted','unstarted','failed']];atomic(root/'results/done.json',dict(state='ACCEPTED',finite=True,stages=[{},{}]));atomic(root/'attempts/done.json',{});atomic(root/'attempts/interrupted.json',{});atomic(root/'endpoints/interrupted.json',dict(stages=[{}]));atomic(root/'attempts/failed.json',{});atomic(root/'results/failed.json',dict(state='FAILED',stages=[]));p=progress(root,plan);assert p['attempted']==3 and p['optimizer_calls']==3 and p['statuses']['UNEXECUTED']==1 and p['statuses']['INTERRUPTED']==1
  try:timeout(None,None)
  except TimeoutError:checks['timeout_signal_handler']=True
  checks['ledger_failure_interruption_counts']=p
 # Development observations cover every motion and method, distinct seed. No evaluation seeds used.
 t=time.monotonic();dev=[]
 for wi,w in enumerate(windows):
  for motion in ['white','correlated','scale','slip_proxy']:
   oo,rr=generate(w,2026111603,'ramp',motion)
   for m in ['M0','M1','M2','M3']:
    out=solve(oo,m,lambda v:None);dev.append(dict(window=w['id'],motion=motion,method=m,**out))
 seconds=time.monotonic()-t;atomic(DOC/'DEVELOPMENT.json',dict(checks=checks,methods=len(dev),optimizer_calls=sum(len(x['stages']) for x in dev),seconds=seconds,max_method_seconds=max(x['seconds'] for x in dev),accepted=sum(x['state']=='ACCEPTED' for x in dev),results=dev));print(json.dumps(dict(checks=checks,development_seconds=seconds,accepted=sum(x['state']=='ACCEPTED' for x in dev),methods=len(dev)),indent=2))
if __name__=='__main__':main()
