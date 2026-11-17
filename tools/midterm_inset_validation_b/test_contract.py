"""One exposed seed only. Pure algebra/paired input checks and counted fake integration."""
import argparse,tempfile,types
from common import *
from run import generate,execute_stage,V
class Crash(BaseException):pass

def tests():
 c=config();seed=c['seeds']['development'][0];pairs={};maxerr=0.;allchecks=[]
 for q in conditions(c):
  u=generate(c,q,seed);obs=u['obs'];key=q['geometry'];same={k:obs[k] for k in ['anchors','ranges','movement','start']}
  if key in pairs:assert pairs[key]==same
  pairs[key]=same;assert abs(np.linalg.norm(np.array(obs['prior_center'])-np.array(u['truth'])[0].ravel())-abs(q['delta_m']))<c['boundary_tolerance_m']
  lin=affine(u,c);assert lin['accepted'];maxerr=max(maxerr,lin['noise_identity_max']);x0=np.array(lin['reference']);r,j=M.objective(u,'B2',x0);fun,start,_=V.objective(c['frozen_model'],obs,'B2');rr,jj=fun(x0)
  assert start[-1]==0 and np.array_equal(start[:24],obs['start']);assert np.allclose(r,rr,atol=1e-12,rtol=0) and np.allclose(j,jj,atol=1e-12,rtol=0)
  # Truth/oracle do not enter the nonlinear closure: only obs and model configuration do.
  C=np.array(lin['covariance']);T=np.array(lin['T']);G=np.array(lin['G']);K=np.linalg.lstsq(j,np.eye(len(r)),rcond=None)[0];assert np.allclose(C,K[:,:-4]@K[:,:-4].T,atol=1e-12);assert np.allclose(T,K[:,-4:]/obs['prior_sigma'],atol=1e-12)
  for car in range(2):
   for t in range(6):
    sl=slice(4*t+2*car,4*t+2*car+2);P=C[sl,sl];B=T[sl];rc=R.region(P,B,.05,np.zeros(2),c['region'])
    if rc['reason']!='AVAILABLE':continue
    a=np.array([.6,.8]);q95=R.quantile(.95);support=np.sqrt(q95*a@P@a)+.05*np.linalg.norm(B.T@a);assert support<=rc['radius']+1e-12
    r0=R.region(P,B,0,np.zeros(2),c['region']);assert r0['radius']==r0['noise_radius'] and r0['bias_radius']==0
    # Independent unit conversion m -> cm for already derived quantities.
    cm=R.region(P*10000,B,5,np.zeros(2),c['region']);assert np.isclose(cm['radius'],rc['radius']*100)
  allchecks.append(dict(condition=q['id'],normal_inf=lin['normal_inf'],rank=lin['rank']))
 with tempfile.TemporaryDirectory() as d:
  out=Path(d);item=tasks(c,'development')[0];u=generate(c,item['condition'],seed);calls=[0]
  def fake(fun,start,**kwargs):calls[0]+=1;return types.SimpleNamespace(x=np.array(start),status=1,success=True,message='counted fake',nfev=1,njev=1)
  p0,a=execute_stage(out,c,item,u,'P0',solver=fake);p1,b=execute_stage(out,c,item,u,'P1',p0,solver=fake);assert calls[0]==2
  execute_stage(out,c,item,u,'P0',solver=fake);execute_stage(out,c,item,u,'P1',p0,solver=fake);assert calls[0]==2
  changed=dict(p0);changed['estimate']=list(p0['estimate']);changed['estimate'][0]+=.001
  try:execute_stage(out,c,item,u,'P1',changed,solver=fake);raise AssertionError('changed P0 accepted')
  except REC.IdentityMismatch:pass
  other=out/'uncertain'
  def hook(p):
   if p=='after_call':raise Crash()
  try:execute_stage(other,c,item,u,'P0',solver=fake,hook=hook)
  except Crash:pass
  before=calls[0]
  try:execute_stage(other,c,item,u,'P0',solver=fake);raise AssertionError('unsafe retry')
  except REC.UncertainExecution:pass
  assert calls[0]==before
  bad=V.blank('P0');p1,rec=execute_stage(out/'skipped',c,item,u,'P1',bad,solver=fake);assert p1['category']=='SKIPPED_INVALID_P0' and calls[0]==before
 return dict(status='PASS',development_seed=seed,algebra_conditions=allchecks,max_noise_identity_error=maxerr,paired_observations_and_initialization=True,bias_initialization_zero=True,objective_regression=True,QR_covariance=True,support_and_units=True,integration_fake_calls=calls[0],P0_identity_change_rejected=True,uncertain_attempt_no_retry=True,invalid_P0_skip=True,real_optimizer_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();z=tests();save(a.out,z);print(json.dumps(z))
