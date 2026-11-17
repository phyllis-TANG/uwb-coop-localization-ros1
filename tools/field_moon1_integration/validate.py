"""No-optimizer acceptance: raw/portable equivalence, analytic Jacobian, boundary checks."""
import copy,json
import numpy as np
from common import *
from inputs import prepare
from model import objective
from two_car_updated_comparison import read_bag

def checks():
 cfg=read(DOC/'CONFIG.json');out=[]
 for case in cfg['cases']:
  o=clean(prepare(case));src=next(x for x in read(SOURCE/'SOURCES.json') if x['case']==case)
  raw=read_bag(ROOT/src['path'],src['sha256']);raw['duration_s']=21.
  other=clean(prepare(case,raw))
  assert o==other,'raw/portable mismatch'
  assert o['times']==cfg['times_s']
  for joint in [False,True]:
   f=objective(o,joint);q=np.array([o['cars'][c]['initial'] for c in ['car1','car2']]).ravel()
   r,j=f.evaluate(q);fd=np.empty_like(j)
   for k in range(len(q)):
    d=np.zeros_like(q);d[k]=1e-6
    fd[:,k]=(f.fun(q+d)-f.fun(q-d))/(2e-6)
   error=float(np.max(abs(j-fd)));assert error<2e-6,error
   rank=int(np.linalg.matrix_rank(j));assert rank==len(q),(rank,len(q))
   out.append({'case':case,'joint':joint,'jacobian_max_error':error,'rank_with_prior':rank,'state_dim':len(q),'wall_factors':f.wall_factor_count,'peer_factors':len(f.peer_indices)})
  for mutate in [lambda x:x.update(reference={}),lambda x:x.pop('times'),lambda x:x['times'].__setitem__(1,1),lambda x:x['peers'][0].update(range_m=-1),lambda x:x['cars']['car1']['model'].update(evaluation_only={})]:
   bad=copy.deepcopy(o);mutate(bad)
   try:objective(bad,True)
   except (ValueError,KeyError):pass
   else:raise AssertionError('invalid input accepted')
  q=np.array([o['cars'][c]['initial'] for c in ['car1','car2']]).ravel();changed=copy.deepcopy(o)
  for p in changed['peers']:
   if p['range_m'] is not None:p['range_m']+=.3
  assert np.array_equal(objective(o,False).fun(q),objective(changed,False).fun(q))
 return {'passed':True,'optimizer_calls':0,'raw_portable_equal_cases':3,'rows':out,'limits':'Same archived decoder library; raw/portable paths differ but not independent binary decoding. Full rank includes assumed start priors, not guaranteed field observability.'}
if __name__=='__main__':print(json.dumps(checks(),indent=2))
