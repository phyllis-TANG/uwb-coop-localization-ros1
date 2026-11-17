"""Zero-solver acceptance and full input/time evidence."""
import copy,gzip,json
from fcommon import *
from adapter import make
from objective import Field
from two_car_updated_comparison import read_bag

def small(o):
 o=copy.deepcopy(o);o['times']=o['times'][:6];o['peers']=o['peers'][:6]
 for c in CARS:
  for k in ['local','initial','observations','range_sample_counts']:o['cars'][c][k]=o['cars'][c][k][:6]
 return o

def run():
 cfg=read(DOC/'CONFIG.json');report=[];timing=[]
 for case in cfg['cases']:
  o=make(case);src=next(x for x in read(SOURCE/'SOURCES.json') if x['case']==case)
  raw=read_bag(ROOT/src['path'],src['sha256']);assert o==make(case,raw)
  d=small(o)
  for method in cfg['methods']:
   f=Field(d,method);q=f.initial();r,j=f.evaluate(q)
   fd=np.column_stack([(f.fun(q+np.eye(len(q))[k]*1e-6)-f.fun(q-np.eye(len(q))[k]*1e-6))/2e-6 for k in range(len(q))])
   err=float(np.max(abs(j-fd)));assert err<1e-5
   report.append({'case':case,'method':method,'jacobian_error':err,'small_rank':int(np.linalg.matrix_rank(j)),'small_dimension':len(q),'full_epochs':len(o['times'])})
  f2=Field(d,'F2');q=f2.initial();q[-1]=.2
  np.testing.assert_allclose(f2.fun(q),Field(d,'F3').fun(np.r_[q,0]),atol=1e-12)
  changed=copy.deepcopy(d)
  for p in changed['peers']:
   if p['range_m'] is not None:p['range_m']+=.3
  assert np.array_equal(Field(d,'F0').fun(Field(d,'F0').initial()),Field(changed,'F0').fun(Field(changed,'F0').initial()))
  # Generate model-matching synthetic wall/peer data from the deterministic rigid odom initialization.
  syn=copy.deepcopy(d);q0=Field(syn,'F0').initial();s=q0.reshape(2,6,3)
  for ci,c in enumerate(CARS):
   m=syn['cars'][c]['model'];ant=s[ci,:,:2]+np.array([rotation(t)@m['base_to_antenna_body_xy_m'] for t in s[ci,:,2]])
   syn['cars'][c]['observations']=[{k:float(np.linalg.norm(np.r_[xy,m['antenna_height_m']]-a)+m['range_bias_m'][k]) for k,a in m['anchors_xyz_m'].items()} for xy in ant]
  f=Field(syn,'F3');_,_,ant,_=f.peer(np.r_[q0,0,0]);dz=.17-.2;dist=np.sqrt(np.sum((ant[0]-ant[1])**2,axis=1)+dz*dz)
  for b0,b1,method in [(0,0,'F1'),(.3,0,'F2'),(.2,.03,'F3')]:
   ss=copy.deepcopy(syn)
   for i,p in enumerate(ss['peers']):p['range_m']=float(dist[i]+b0+b1*f.tau[i])
   ff=Field(ss,method);qq=np.r_[q0,([b0] if method=='F2' else [b0,b1] if method=='F3' else [])]
   assert np.max(abs(ff.fun(qq)))<1e-10
  # Reject fault/reference top-level additions before optimization.
  bad=copy.deepcopy(d);bad['reference']={}
  try:Field(bad,'F1')
  except ValueError:pass
  else:raise AssertionError('reference accepted')
  with gzip.open(SOURCE/case/'measurements.jsonl.gz','rt') as fh:msgs=[json.loads(l) for l in fh]
  for topic in sorted(set(m['topic'] for m in msgs)):
   m=[x for x in msgs if x['topic']==topic];g=np.array([(x['receipt_ns']-x['header_ns'])*1e-6 for x in m]);rr=np.array([x['receipt_ns'] for x in m]);hh=np.array([x['header_ns'] for x in m])
   timing.append({'case':case,'topic':topic,'count':len(m),'receipt_nonincreasing':int(np.sum(np.diff(rr)<=0)),'header_nonincreasing':int(np.sum(np.diff(hh)<=0)),'receipt_minus_header_ms_p05_p50_p95':np.percentile(g,[5,50,95]).tolist(),'frame_ids':sorted(set(x['frame_id'] for x in m)),'child_frames':sorted(set(x['child_frame_id'] for x in m if 'child_frame_id' in x))})
 return {'passed':True,'optimizer_calls':0,'raw_portable_identical_cases':5,'checks':report,'timing':timing}
if __name__=='__main__':write(sys.argv[1],run())
