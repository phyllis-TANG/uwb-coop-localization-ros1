"""No real optimization: mathematical contracts and fake-call durability tests."""
import argparse,copy
from types import SimpleNamespace
from tcommon import *
from tinputs import tracks,make,verify,plan
from tmodel import problem,independent,information,tau
from tengine import once,reserve

def run(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);cfg=read(DOC/'CONFIG.json');sc=read(DOC/'SOLVER.json');seed=read(DOC/'SEEDS.json')['development_seed'];tt,src=tracks();fdmax=0.;identmax=0.;ranks=[];zero=[];steps=[]
 for tr in tt:
  zeroobs={};normal_by_h={}
  for h in [0.,.05,.15]:
   for c in cfg['conditions']:
    o,r=make(tr,cfg,c,seed,h);verify(o,r)
    if h==0:zeroobs[c['id']]=o
    else:
     a={k:v for k,v in o.items() if k!='heights_m'};b={k:v for k,v in zeroobs[c['id']].items() if k!='heights_m'};assert a==b
    f0,z0,receipt=problem(o,'M0')
    if c['id']=='normal':normal_by_h[h]=(f0,z0,receipt)
    other,z,hh=normal_by_h[h];assert receipt==hh and np.array_equal(z0,z)
    for x,y in zip(f0(z),other(z)):np.testing.assert_array_equal(x,y)
    f2,q2,_=problem(o,'M2');f3,q3,_=problem(o,'M3');q3[:25]=q2
    np.testing.assert_array_equal(f2(q2)[0],f3(q3)[0]);np.testing.assert_array_equal(f2(q2)[1],f3(q3)[1][:,:25])
    for method in cfg['methods']:
     f,q,_=problem(o,method);rr,jj=independent(o,method,q);a,b=f(q);np.testing.assert_allclose(a,rr,atol=1e-10,rtol=0);np.testing.assert_allclose(b,jj,atol=1e-10,rtol=0)
     eps=1e-5;fd=np.column_stack([(independent(o,method,q+d)[0]-independent(o,method,q-d)[0])/(2*eps) for d in np.eye(len(q))*eps]);err=float(np.max(abs(fd-b)));fdmax=max(fdmax,err);assert err<2e-6
     nr=48 if method=='M0' else 54
     ranks.append(dict(window=tr['window'],height_sigma_m=h,condition=c['id'],method=method,range_rank=information(b[:nr])['rank'],data_rank=information(b[:-4])['rank'],total_rank=information(b)['rank'],dimension=len(q),data_condition=information(b[:-4])['condition']))
  for c in cfg['conditions']:
   o,r=make(tr,cfg,c,seed,0.,True);xy=np.array(tr['antenna_xyz_m'])[:,:,:2].ravel()
   params={'normal':[0,0],'constant03':[.3,0],'ramp03':[.15,.3]}
   for method in cfg['methods']:
    if c['id']=='normal':tail=[] if method in ['M0','M1'] else ([0] if method=='M2' else [0,0])
    elif c['id']=='constant03' and method in ['M2','M3']:tail=[.3] if method=='M2' else [.3,0]
    elif c['id']=='ramp03' and method=='M3':tail=[.15,.3]
    else:continue
    f,_,_=problem(o,method);rr,j=f(np.r_[xy,tail]);error=float(max(abs(rr)));assert error<1e-10;zero.append(dict(window=tr['window'],condition=c['id'],method=method,max_residual=error))
   if c['id']=='step03':
    # Descriptive least-squares projection of injection only, NOT a true M3 parameter.
    design=np.column_stack([np.ones(6),tau(o)]);coef=np.linalg.lstsq(design,c['curve_m'],rcond=None)[0];f,_,_=problem(o,'M3');r,_=f(np.r_[xy,coef]);assert max(abs(r))>1e-4;steps.append(dict(window=tr['window'],descriptive_projection=coef,max_residual=float(max(abs(r))),not_true_parameter=True))
 for field in ['reference','curve_m','injection_m','height_errors_m','quality']:
  bad=copy.deepcopy(o);bad[field]=[]
  try:problem(bad,'M3');raise AssertionError('accepted forbidden field')
  except ValueError:pass
 bad=copy.deepcopy(o);bad.pop('heights_m')
 try:problem(bad,'M3');raise AssertionError('accepted missing height')
 except (ValueError,KeyError):pass
 assert information(np.zeros((78,26)))['position_covariance_blocks'] is None
 # Fake-call reservation protocol: repeat, orphan, hard limit, and concurrent lock.
 fake=out/'fake';fake.mkdir();write(fake/'BUDGET.json',dict(limit=2));write(fake/'EXECUTION.json',dict(commit=git('rev-parse','HEAD'),source_sha256=sources(),solver=sc));f,q,_=problem(o,'M3');calls=[]
 def optimizer(fun,x,**kw):calls.append(1);return SimpleNamespace(x=x,status=1,success=True,message='FAKE',nfev=1,njev=1)
 once(o,'M3',q,sc['P0'],fake,'unit','P0',optimizer=optimizer)
 try:once(o,'M3',q,sc['P0'],fake,'unit','P0',optimizer=optimizer);raise AssertionError('retry')
 except RuntimeError as ex:assert 'ATTEMPT_EXISTS' in str(ex)
 reserve(fake,'orphan',dict(mock=True))
 try:reserve(fake,'orphan',dict(mock=True));raise AssertionError('orphan retried')
 except RuntimeError as ex:assert 'ATTEMPT_EXISTS' in str(ex)
 try:reserve(fake,'over_limit',dict(mock=True));raise AssertionError('limit passed')
 except RuntimeError as ex:assert 'HARD_CALL_LIMIT' in str(ex)
 with lock(fake/'BUDGET_LOCK'):
  p=subprocess.run([sys.executable,'-c','import sys,fcntl; f=open(sys.argv[1],"a"); fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)',str(fake/'BUDGET_LOCK')],capture_output=True,text=True);assert p.returncode!=0 and 'BlockingIOError' in p.stderr
 secret=out/'reference/secret.json';write(secret,o)
 p=subprocess.run([sys.executable,str(ROOT/'tools/moon1_trend_height_eval/tengine.py'),'--measurement',str(secret),'--root',str(fake),'--unit','forbidden'],capture_output=True,text=True)
 assert p.returncode!=0 and 'reference forbidden' in p.stderr and not (fake/'estimates/forbidden-M0').exists()
 assert len(calls)==1
 report=dict(passed=all(r['data_rank']==r['dimension'] and r['total_rank']==r['dimension'] for r in ranks),source_sha256=sources(),input_source=src,fd_jacobian_max=fdmax,rank_checks=ranks,noiseless=zero,step_mismatch=steps,height_only_in_estimator_geometry=True,M0_peer_invariance=True,M3_b1_zero_equals_M2=True,invalid_fields_rejected=True,reference_path_rejected=True,duplicate_orphan_limit_and_lock_checked=True,fake_optimizer_calls=1,real_optimizer_calls=0,argv=sys.argv)
 write(out/'ACCEPTANCE.json',report);print('PASS' if report['passed'] else 'RANK_FAILURE',fdmax)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();run(a.out)
