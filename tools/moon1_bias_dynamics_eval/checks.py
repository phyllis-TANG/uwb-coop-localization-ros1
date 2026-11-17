"""Zero optimizer calls: input reconstruction, model consistency, isolation."""
import argparse,copy
from bridge import *
from inputs import tracks,make,verify

def run(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);cfg=read(DOC/'CONFIG.json');tt,asset=tracks();maxfd=0.;zeros=[];mismatch=[];pair={}
 for track in tt:
  base=None;baseline_f=None;baseline_start=None;baseline_hash=None
  for condition in cfg['conditions']:
   o,ref=make(track,cfg,condition,cfg['development_seed']);verify(o,ref)
   same={k:v for k,v in o.items() if k!='ranges_m'}
   pair.setdefault(track['window'],digest(same));assert pair[track['window']]==digest(same)
   if base is None:base=o
   else:
    d=np.array(o['ranges_m'])-base['ranges_m'];expected=np.zeros(54);expected[8::9]=condition['peer_curve_m'];np.testing.assert_allclose(d,expected,atol=1e-14,rtol=0)
   f,start,h=problem(o,'M0')
   if baseline_f is None:baseline_f=f;baseline_start=start;baseline_hash=h
   assert h==baseline_hash and np.array_equal(start,baseline_start)
   for a,b in zip(f(start),baseline_f(start)):np.testing.assert_array_equal(a,b)
   no,rr=make(track,cfg,condition,0,True);verify(no,rr);truth=np.array(track['antenna_xyz_m'])[:,:,:2].ravel()
   for method in cfg['methods']:
    fun,q,_=problem(o,method);r,j=fun(q);eps=1e-5;fd=np.column_stack([(fun(q+e)[0]-fun(q-e)[0])/(2*eps) for e in np.eye(len(q))*eps]);err=float(np.max(abs(fd-j)));maxfd=max(maxfd,err);assert err<2e-6
    r2,j2=independent(o,method,q);np.testing.assert_allclose(r,r2,atol=1e-10,rtol=0);np.testing.assert_allclose(j,j2,atol=1e-10,rtol=0)
    nf,_,_=problem(no,method);nq=np.r_[truth,float(np.mean(condition['peer_curve_m']))] if method=='M2' else truth
    nr,_=nf(nq)
    if condition['id']=='normal' or (condition['id']=='constant03' and method=='M2'):
     assert max(abs(nr))<1e-10;zeros.append(dict(window=track['window'],condition=condition['id'],method=method,max_residual=float(max(abs(nr)))))
    elif method=='M2':mismatch.append(dict(window=track['window'],condition=condition['id'],truth_curve_mean_residual=nr.tolist(),expected_nonzero=True))
  f,q,_=problem(base,'M2');c,_=make(track,cfg,cfg['conditions'][1],cfg['development_seed']);g,z,_=problem(c,'M2');shift=q.copy();shift[-1]+=.3
  np.testing.assert_allclose(f(q)[0],g(shift)[0],atol=1e-12,rtol=0);np.testing.assert_array_equal(f(q)[1],g(shift)[1])
 for kind in ['condition','peer_curve_m','quality','truth']:
  bad=copy.deepcopy(base);bad[kind]=[]
  try:problem(bad,'M1');raise AssertionError('accepted label')
  except ValueError:pass
 secret=out/'reference/forbidden.json';write(secret,base)
 p=subprocess.run([sys.executable,str(ROOT/'tools/moon1_bias_dynamics_eval/worker.py'),'--measurement',str(secret),'--method','M1','--config',str(DOC/'SOLVER.json'),'--out',str(out/'forbidden_output')],capture_output=True,text=True)
 assert p.returncode!=0 and 'reference forbidden' in p.stderr and not (out/'forbidden_output').exists()
 write(out/'CHECKS.json',dict(passed=True,optimizer_calls=0,source_sha256=sources(),input_source=asset,weighted_jacobian_max_error=maxfd,noiseless_matched=zeros,timevarying_truth_mismatch=mismatch,M0_invariance=True,shared_inputs=True,label_refusal=True,reference_access_refused=True,M2_constant_shift_identity=True,argv=sys.argv))
 print('PASS no-optimizer acceptance; FD',maxfd)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();run(a.out)
