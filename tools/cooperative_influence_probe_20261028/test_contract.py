import copy,importlib.util,json,unittest
import numpy as np
from scipy.optimize import minimize
from common import ROOT,ART,read,CONFIG
from bindings import base,probe
from core import InfluenceGraph,WeightedObjective,antennas,antenna_jac,constraint,clip_pose
from replay_control import execute
spec=importlib.util.spec_from_file_location('fx',ROOT/'tools/two_car_fixed_lag_fgo_v1/test_joint.py');fx=importlib.util.module_from_spec(spec);spec.loader.exec_module(fx)
def run(e,c,m,**kw):
 rows=[];w=execute(e,c,m,rows.append,**kw);return rows,w
def semantic(r):
 # Wall timings, durations and SLSQP diagnostics are not causal state data.
 if isinstance(r,dict):return {k:semantic(v) for k,v in r.items() if not(k.endswith('_wall_s') or k.startswith('estimated_worker_'))}
 if isinstance(r,list):return [semantic(v) for v in r]
 return r
class Contract(unittest.TestCase):
 def test_old_baselines_exact(self):
  p=ART/'evidence-v1';inp=p/'inputs/nominal_seed101';e=read(inp/'events.jsonl.gz');e=[q for q in e if q['receive_epoch_ns']<=e[0]['receive_epoch_ns']+32*10**9];c=json.loads((inp/'config.json').read_text())
  for a,b in [('I','G0'),('J','G1')]:
   out=[];probe.execute(e,c,b,out.append);old=read(p/f'reused/nominal_seed101__{a}/updates.jsonl.gz')
   for x,y in zip(out,old):self.assertEqual(probe.numeric(x),probe.numeric(y))
 def test_constraint_J_actual_rotated_antenna_and_clip(self):
  c,t,l,o,p=fx.inputs(3);x=l.reshape(-1,6).ravel()+np.tile([.1,-.1,1.2,-.1,.05,-.9],3);ref=x[-6:]+[.03,-.04,-.8,.02,.01,.7]
  val,J=constraint(x,ref,c,.04);fd=fx.numerical_jac(lambda z:constraint(z,ref,c,.04)[0],x);np.testing.assert_allclose(J,fd,atol=3e-6,rtol=3e-6)
  cl=clip_pose(x[-6:],ref,c,.04);self.assertLessEqual(max(np.linalg.norm(antennas(cl,c)-antennas(ref,c),axis=1)),.04+1e-14)
  np.testing.assert_array_equal(np.array(cl)[[2,5]],x[-6:][[2,5]])
  # Same base coordinates can violate budget due only to yaw/lever arm.
  r=x[-6:].copy();r[[2,5]]+=1.;self.assertGreater(max(np.linalg.norm(antennas(r,c)-antennas(x[-6:],c),axis=1)),.04)
 def test_weight_information_outside_huber(self):
  c,t,l,o,p=fx.inputs(3);x=l.reshape(-1,6).ravel();pr=base.joint_initial(c);a=base.Objective(t,l,o,p,c,pr,True);b=WeightedObjective(t,l,o,p,c,pr,True,weight=.25)
  r,J=a.evaluate(x);w,K=b.evaluate(x);n=len(p);np.testing.assert_array_equal(w[:-n],r[:-n]);np.testing.assert_array_equal(K[:-n],J[:-n]);np.testing.assert_array_equal(w[-n:],.5*r[-n:]);np.testing.assert_array_equal(K[-n:],.5*J[-n:])
 def test_private_reference_peer_perturbation_and_main_prior_across_lag(self):
  c,e=fx.events_for(27);alter=copy.deepcopy(e)
  for q in alter:
   if q['kind']=='uwb' and q.get('vehicle_id')=='car1' and 'node_0' in q['value']:q['value']['node_0']+=1.2
  a,wa=run(e,c,'W025');b,wb=run(alter,c,'W025');self.assertGreater(wa.graph.reference.marginalizations,0)
  for x,y in zip(a,b):self.assertEqual(semantic(x['reference']),semantic(y['reference']))
  self.assertFalse(np.allclose(a[-1]['main_pose'],b[-1]['main_pose']))
  original=copy.deepcopy(wa.graph.reference.snapshot());wa.graph.prior.point+=100;wa.graph.states[-1]+=10;self.assertEqual(wa.graph.reference.snapshot(),original)
  for q in a:
   ref=q['reference'];self.assertTrue(all(v is None for v in ref['snapshot']['peers_m']));M=np.array(ref['snapshot']['prior']['matrix']);self.assertLess(np.linalg.norm((M.T@M)[:3,3:]),1e-8)
 def test_same_solver_off_small_fixture_vs_original_and_inactive(self):
  c,e=fx.events_for(8);j=[];probe.execute(e,c,'G1',j.append);u,_=run(e,c,'U');k,_=run(e,c,'K100')
  for a,b,d in zip(j[2:],u[2:],k[2:]):
   self.assertTrue(b['accepted_graph'],b['optimizer']);self.assertTrue(d['accepted_graph'],d['optimizer'])
   np.testing.assert_allclose(a['pose'],b['pose'],atol=1e-4,rtol=0);np.testing.assert_allclose(b['pose'],d['pose'],atol=1e-4,rtol=0)
   self.assertLess(abs(a['optimizer']['cost']-b['optimizer']['cost']),1e-6*max(1,abs(a['optimizer']['cost'])))
 def test_actual_budget_active_and_prefix(self):
  c,e=fx.events_for(27)
  for q in e:
   if q['kind']=='uwb' and q.get('vehicle_id')=='car1' and 'node_0' in q['value']:q['value']['node_0']+=1.2
  a,_=run(e,c,'K004');prefix=[q for q in e if q['receive_epoch_ns']<=e[0]['receive_epoch_ns']+25*10**9];b,_=run(prefix,c,'K004')
  self.assertTrue(any(q['publication_mode']=='normal_joint' and max(q['published_separation_m'])>.039 for q in a))
  for q in a:
   if q['budget_certified']:self.assertLessEqual(max(q['published_separation_m']),.0400001)
  for x,y in zip(a,b):self.assertEqual(semantic(x),semantic(y))
 def test_failure_timeout_unknown_and_no_fallback_feedback(self):
  c,e=fx.events_for(6)
  for fault,reason in [('failure','SOLVER_FAILURE'),('timeout','TIMEOUT'),('reference_unknown','REFERENCE_NOT_ACCEPTED')]:
   rows,w=run(e,c,'K004',test_fault=fault)
   for q in rows[2:]:
    self.assertFalse(q['accepted_graph']);self.assertEqual(q['publication_reason'],reason);self.assertEqual(q['pose'],q['reference']['pose'])
    self.assertEqual(q['publication_mode'],'unknown' if fault=='reference_unknown' else 'reference_fallback');self.assertIsNone(q['covariance'])
   self.assertNotEqual(rows[-1]['snapshot']['states'][-1],rows[-1]['reference']['snapshot']['states'][-1])
 def test_full_prior_zero_current_weight_not_peer_free(self):
  c,t,l,o,p=fx.inputs(23);g=InfluenceGraph(c,'W025')
  for i in range(22):g.update(t[i],l[i],o[i],p[i])
  M=g.prior.matrix.copy();self.assertGreater(np.linalg.norm((M.T@M)[:3,3:]),.01);g.weight=0.;r=g.update(t[22],l[22],o[22],p[22])
  self.assertGreater(np.linalg.norm((g.prior.matrix.T@g.prior.matrix)[:3,3:]),.01);self.assertTrue(r['marginalization_details']);self.assertGreater(g.marginalizations,0)
 def test_symmetric_1d_equals_clipping(self):
  for z in [(.3,0.),(0.,.3),(-.3,0.),(.3,.3)]:
   for B in [.04,1.]:
    z=np.array(z);H=np.array([[26.,-25.],[-25.,26.]]);x=np.linalg.solve(H,z);cl=np.clip(x,z-B,z+B)
    sol=minimize(lambda a:.5*np.sum((a-z)**2)+12.5*(a[1]-a[0])**2,x,jac=lambda a:H@a-z,bounds=list(zip(z-B,z+B)),method='SLSQP',options={'ftol':1e-12,'maxiter':300})
    self.assertTrue(sol.success);np.testing.assert_allclose(sol.x,cl,atol=1e-10,rtol=0)
 def test_zero_weight_from_start_matches_independent(self):
  c,t,l,o,p=fx.inputs(24);g=InfluenceGraph(c,'W025');g.weight=0.;ind=base.WindowGraph(c,False)
  for k in range(24):
   a=g.update(t[k],l[k],o[k],p[k]);b=ind.update(t[k],l[k],o[k],None)
   np.testing.assert_allclose(a['main_pose'],b['pose'],atol=1e-7,rtol=0)
 def test_weighted_full_Schur_and_retained_not_consumed(self):
  import independent
  c,t,l,o,p=fx.inputs(24);g=InfluenceGraph(c,'W025')
  for k in range(24):
   row=g.update(t[k],l[k],o[k],p[k])
   for md in row['marginalization_details']:independent.marginal(md,c,.25)
  elim=g.original_update.__globals__['eliminate_oldest'];args=[g.states[:3],g.times[:3],g.local[:3],copy.deepcopy(g.observations[:3]),g.peers[:3],c,g.prior,True]
  a=elim(*args);args[3][1]['car1']={key:100. for key in args[3][1]['car1']};args[4]=[args[4][0],100.,100.];b=elim(*args)
  self.assertEqual(a[0].record(),b[0].record());self.assertEqual(a[1],b[1])
 def test_missing_odom_unknown_and_no_publication(self):
  c,e=fx.events_for(8,omit_odom=('car1',3.,7.));rows,_=run(e,c,'K004');missing=[r for r in rows if r['publication_reason']=='MISSING_ODOM']
  self.assertTrue(missing)
  for r in missing:self.assertIsNone(r['pose']);self.assertFalse(r['accepted_graph']);self.assertEqual(r['publication_mode'],'unknown');self.assertFalse(r['budget_certified'])
 def test_no_shared_module_mutation(self):
  c,e=fx.events_for(5);a=[];probe.execute(e,c,'G1',a.append);run(e,c,'K004');b=[];probe.execute(e,c,'G1',b.append)
  for x,y in zip(a,b):self.assertEqual(probe.numeric(x),probe.numeric(y))
if __name__=='__main__':unittest.main(verbosity=2)
