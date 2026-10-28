import copy,importlib.util,json,unittest
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.optimize._lsq.common import scale_for_robust_loss_function
from common import ROOT,read
from bindings import base,probe
from kernel import kernel_values,nominal_peer,PeerObjective,WindowGraph
from replay_dcs import execute
import independent as ind
spec=importlib.util.spec_from_file_location('frozen_joint_fixtures',ROOT/'tools/two_car_fixed_lag_fgo_v1/test_joint.py');fx=importlib.util.module_from_spec(spec);spec.loader.exec_module(fx)
ART=Path('/home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/evidence-v1')

def get_fixture(n=3):
 c,t,l,o,p=fx.inputs(n);x=l.reshape(-1,6)+[.07,-.02,.015,-.03,.02,-.01];pr=base.joint_initial(c);pr.offset+=np.arange(6)*.03
 return c,t,l,o,p,x,pr

def run(e,c,m,**kw):
 r=[];g=execute(e,c,m,r.append,**kw);return r,g

class Contracts(unittest.TestCase):
 def test_small_large_boundary_and_limits(self):
  for t,s in [(0,1),(.01,1),(1,1),(3,.5),(99,.02)]:
   ss,w,rho=kernel_values(t);self.assertEqual(ss,s);self.assertEqual(w,s*s);self.assertGreaterEqual(rho,w*t)
  self.assertLess(abs(kernel_values(1+1e-9)[2]-1),2e-9);self.assertLess(abs(kernel_values(1-1e-9)[2]-1),2e-9)
  s,w,rho=kernel_values(1e24);self.assertLess(w,1e-40);self.assertLess(abs(rho-3),1e-12)
  for t,phi in [(-1,1),(1,0),(1,-1),(float('nan'),1)]:
   with self.assertRaises(ValueError):kernel_values(t,phi)
 def test_scalar_gradient_is_w_e_not_derivative_of_s_e(self):
  for e in (-8.,-1.,-.2,0.,.2,1.,8.):
   s,w,rho=kernel_values(e*e);h=1e-6
   fd=(kernel_values((e+h)**2)[2]-kernel_values((e-h)**2)[2])/(4*h)
   self.assertAlmostEqual(float(fd),float(w*e),delta=3e-6)
  e=4.;h=1e-6
  wrong=lambda v:float(kernel_values(v*v)[1]*v*v/2)
  wrong_derivative=(wrong(e+h)-wrong(e-h))/(2*h)
  self.assertLess(wrong_derivative,0);self.assertGreater(float(kernel_values(e*e)[1]*e),0)
 def test_nominal_peer_geometry_Jacobian_no_huber_stacking(self):
  c,t,l,o,p,x,pr=get_fixture();state=x[0];z=p[0]+1.2;e,J=nominal_peer(state,z,c['models'],.2)
  fd=fx.numerical_jac(lambda q:nominal_peer(q,z,c['models'],.2)[0],state)
  np.testing.assert_allclose(J,fd,atol=3e-6,rtol=3e-6);huber,_=base.peer_residual(state,z,c['models'],.2)
  self.assertGreater(abs(e),abs(huber));self.assertNotAlmostEqual(e*e,huber*huber)
 def test_scipy_adapter_information_and_gradient_exact(self):
  c,t,l,o,p,x,pr=get_fixture();p=[q+1.2 for q in p];obj=PeerObjective(t,l,o,p,c,pr)
  r,J=obj.evaluate(x.ravel());rho=obj.loss(r*r);W=rho[1]
  j,f=scale_for_robust_loss_function(J.copy(),r.copy(),rho)
  np.testing.assert_allclose(j,np.sqrt(W)[:,None]*J,atol=1e-10,rtol=1e-10)
  np.testing.assert_allclose(f,np.sqrt(W)*r,atol=1e-10,rtol=1e-10)
  np.testing.assert_allclose(j.T@j,J.T@(W[:,None]*J),atol=1e-10,rtol=1e-10)
  np.testing.assert_allclose(j.T@f,J.T@(W*r),atol=1e-10,rtol=1e-10)
  fd=fx.numerical_jac(lambda v:obj.cost(v),x.ravel())
  np.testing.assert_allclose(J.T@(W*r),fd,atol=3e-6,rtol=3e-6)
  self.assertTrue(np.all(rho[2]==0))
 def test_closed_DCS_nominal_peer_path(self):
  c,t,l,o,p,x,pr=get_fixture();obj=PeerObjective(t,l,o,p,c,pr,dcs=False)
  r,J=obj.evaluate(x.ravel());np.testing.assert_array_equal(obj.loss(r*r)[1],np.ones(len(r)))
  other=base.Objective(t,l,o,p,c,pr,False);n=len(other.fun(x.ravel()))
  np.testing.assert_array_equal(r[:n],other.fun(x.ravel()));np.testing.assert_array_equal(J[:n],other.jac(x.ravel()))
  for k in range(len(t)):self.assertEqual(r[n+k],nominal_peer(x[k],p[k],c['models'],.2)[0])
  a=least_squares(obj.fun,x.ravel(),jac=obj.jac,loss='linear',ftol=1e-7,xtol=1e-7,gtol=1e-7)
  b=least_squares(obj.fun,x.ravel(),jac=obj.jac,loss=obj.loss,ftol=1e-7,xtol=1e-7,gtol=1e-7)
  np.testing.assert_array_equal(a.x,b.x)
 def test_disabled_peer_exact_D0_through_marginalization(self):
  c,e=fx.events_for(26);a,_=run(e,c,'D3',peer_enabled=False);b,_=run(e,c,'D0')
  self.assertGreater(a[-1]['marginalizations'],0)
  for x,y in zip(a,b):self.assertEqual(probe.numeric(x),probe.numeric(y))
 def test_old_D0_D1_D2_regression_archived_prefix(self):
  path=ART/'inputs/nominal_seed101';c=json.loads((path/'config.json').read_text());e=read(path/'events.jsonl.gz');e=[r for r in e if r['receive_epoch_ns']<=e[0]['receive_epoch_ns']+31*10**9]
  for d in ('D0','D1','D2'):
   rows,_=run(e,c,d);old=read(ART/'reused'/('nominal_seed101__G'+d[1])/'updates.jsonl.gz')
   for x,y in zip(rows,old):
    self.assertEqual(probe.numeric(x),probe.numeric(y))
    if d=='D2':
     self.assertEqual(x['gate'],y['gate']);self.assertEqual(probe.numeric(x['auxiliary']),probe.numeric(y['auxiliary']))
   self.assertGreater(rows[-1]['marginalizations'],0)
 def test_prefix_causal_with_reweight_and_prior(self):
  c,e=fx.events_for(28);full,_=run(e,c,'D3');cut=e[0]['receive_epoch_ns']+26*10**9;prefix=[r for r in e if r['receive_epoch_ns']<=cut];part,_=run(prefix,c,'D3')
  self.assertGreater(part[-1]['marginalizations'],0)
  for a,b in zip(part,full):self.assertEqual(probe.semantic(a),probe.semantic(b))
 def test_Schur_cross_affine_constant_no_retained_double_count(self):
  c,t,l,o,p,x,pr=get_fixture();p[0]+=1.2;g=WindowGraph(c)
  after,k,d=g._eliminate(x,t,l,o,p,c,pr,True);ind.marginal(d,c)
  self.assertGreater(d['cross_information_norm'],0);self.assertGreater(d['dcs_offset_constant'],0);self.assertGreater(np.linalg.norm(after.offset),0)
  changed=copy.deepcopy(o);changed[1]['car1']['node_2']+=2.;pp=p.copy();pp[1]+=5.
  q,v,_=g._eliminate(x,t,l,changed,pp,c,pr,True);np.testing.assert_array_equal(after.matrix,q.matrix);np.testing.assert_array_equal(after.offset,q.offset);self.assertEqual(k,v)
  full=PeerObjective(t,l,o,p,c,pr);r,J,offset=full.weighted(x.ravel())
  remaining=PeerObjective(t[1:],l[1:],o[1:],p[1:],c,after);rr,jj,offset2=remaining.weighted(x[1:].ravel())
  a,b=J[:,:6],J[:,6:];jp=b-a@np.linalg.lstsq(a,b,rcond=None)[0];rp=r-a@np.linalg.lstsq(a,r,rcond=None)[0]
  np.testing.assert_allclose(jj.T@jj,jp.T@jp,atol=1e-5,rtol=1e-8);np.testing.assert_allclose(jj.T@rr,jp.T@rp,atol=1e-6,rtol=1e-8)
  self.assertLess(abs(rr@rr+offset2+k-(rp@rp+offset)),1e-6)
 def test_true_cost_acceptance_and_iteration_weights(self):
  c,e=fx.events_for(25)
  for v in e:
   if v['kind']=='uwb' and v['vehicle_id']=='car1':v['value']['node_0']+=1.2
  rows,_=run(e,c,'D3')
  self.assertTrue(any(p['information_weight']<1 for r in rows for q in r['dcs_linearizations'] for p in q['peers']))
  for r in rows:
   ts=r['dcs_linearizations'];self.assertTrue(all(b['true_cost']<=a['true_cost']+1e-10 for a,b in zip(ts,ts[1:])))
   if r['accepted_graph']:
    self.assertAlmostEqual(r['optimizer']['cost'],ind.cost(r['snapshot'],np.asarray(r['snapshot']['states']).ravel(),c),places=8)
   for q in ts:
    self.assertAlmostEqual(q['true_cost'],ind.cost(r['snapshot'],np.asarray(q['states']).ravel(),c),places=8)
    for p in q['peers']:self.assertAlmostEqual(p['information_weight'],p['s']**2,places=15)
  for r in rows:
   for d in r['marginalization_details']:ind.marginal(d,c)
 def test_missing_peer_not_manufactured_and_no_history_clear(self):
  c,e=fx.events_for(28,peer_gap=(22,25));r,_=run(e,c,'D3');missing=[q for q in r if q['peer_median_m'] is None];self.assertTrue(missing)
  for q in missing:self.assertFalse(q['peer_factor_used']);self.assertIsNone(q['actual_peer_factor_id'])
  self.assertTrue(r[-1]['provenance']['prior_peer_factor_ids']);self.assertLessEqual(r[-1]['scalar_variables'],126)
 def test_complete_index_rejects_missing_duplicate_extra_failure(self):
  from run_matrix import validate
  from common import SCENARIOS,SEEDS,METHODS
  cells=[dict(run_id=f'{s}_seed{k}__{m}',scenario=s,seed=k,method=m,status='DONE' if m=='D3' else 'REUSED_VERIFIED') for s in SCENARIOS for k in SEEDS for m in METHODS]
  valid={'status':'DONE','cells':cells};validate(valid,True)
  variants=[cells[:-1],cells+[cells[0]],cells[:-1]+[cells[0]],[]]
  for x in variants:
   with self.assertRaises(ValueError):validate({'status':'DONE','cells':x},True)
  for status in ('FAILED','PLANNED_NEW','IN_PROGRESS'):
   bad=copy.deepcopy(valid);next(c for c in bad['cells'] if c['method']=='D3')['status']=status
   with self.assertRaises(ValueError):validate(bad,True)
 def test_no_process_global_monkey_patch(self):
  c,e=fx.events_for(5);a,_=run(e,c,'D1');run(e,c,'D3');b,_=run(e,c,'D1')
  for x,y in zip(a,b):self.assertEqual(probe.numeric(x),probe.numeric(y))

if __name__=='__main__':unittest.main(verbosity=2)
