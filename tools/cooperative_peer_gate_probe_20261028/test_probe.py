"""Required equivalence, causal isolation and actual objective/prior contracts."""
import copy,importlib.util,json,os,unittest
from pathlib import Path
import numpy as np
from pinned import graph,replay,ROOT
from probe import execute,numeric,semantic,antenna_pair,decision
from records import read,Provenance
OLD=Path(os.environ['PEER_GATE_OLD_ROOT'])/'formal-v1'

def inputs(sc='nominal'):
 root=OLD/'inputs'/f'{sc}_seed101'
 return list(read(root/'events.jsonl.gz')),json.loads((root/'config.json').read_text())
def go(events,config,method,mode=None):
 rows=[];worker=execute(events,config,method,rows.append,mode);return rows,worker

class ProbeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.events,cls.config=inputs();cls.cache={q:go(cls.events,cls.config,q)[0] for q in ('G0','G1','G2')}
 def test_baseline_exact_frozen_and_archived(self):
  for method,arm in [('G0','D0'),('G1','D1')]:
   original=[];replay.execute(self.events,self.config,arm,original.append)
   archive=list(read(OLD/'runs'/f'nominal_seed101__{arm}'/'updates.jsonl.gz'))
   self.assertEqual(len(original),63)
   for own,native,stored in zip(self.cache[method],original,archive):
    self.assertEqual(numeric(own),numeric(native));self.assertEqual(numeric(own),numeric(stored))
 def test_unit_admission_equals_G1_after_marginalization(self):
  rows,_=go(self.events,self.config,'G2','allow_all')
  for a,b in zip(rows,self.cache['G1']):self.assertEqual(numeric(a),numeric(b))
  self.assertGreater(rows[-1]['marginalizations'],0)
 def test_all_reject_equals_G0_and_real_objective(self):
  rows,_=go(self.events,self.config,'G2','reject_all')
  for a,b in zip(rows,self.cache['G0']):self.assertEqual(numeric(a),numeric(b));self.assertFalse(a['peer_factor_used']);self.assertTrue(all(x is None for x in a['snapshot']['peers_m']))
  s=self.cache['G1'][10]['snapshot'];prior=graph.JointPrior(**s['prior']);peers=list(s['peers_m']);without=peers[:];without[-1]=None
  a=graph.Objective(s['times_s'],s['local'],s['observations'],peers,self.config,prior,True);b=graph.Objective(s['times_s'],s['local'],s['observations'],without,self.config,prior,True);x=np.array(s['states']).ravel()
  self.assertEqual(len(a.fun(x)),len(b.fun(x))+1);np.testing.assert_array_equal(a.fun(x)[:-1],b.fun(x));np.testing.assert_array_equal(a.jac(x)[:-1],b.jac(x))
 def test_peer_mutation_cannot_change_auxiliary_private_history(self):
  changed=copy.deepcopy(self.events)
  for e in changed:
   if e['kind']=='uwb':
    key='node_0' if e['vehicle_id']=='car1' else 'node_1';e['value'][key]+=2.
  rows,_=go(changed,self.config,'G2');delta=0.
  for a,b in zip(rows,self.cache['G2']):
   self.assertEqual(semantic(a['auxiliary']),semantic(b['auxiliary']));delta=max(delta,float(np.max(np.abs(np.array(a['pose'])-b['pose']))))
  self.assertGreater(delta,1e-8);self.assertGreater(rows[-1]['auxiliary']['marginalizations'],0)
 def test_receive_prefix_has_no_future_rewrite(self):
  prefix=[e for e in self.events if e['receive_epoch_ns']<=self.events[0]['receive_epoch_ns']+30_000_000_000];rows,_=go(prefix,self.config,'G2');full={r['state_epoch_ns']:r for r in self.cache['G2']}
  self.assertGreater(rows[-1]['marginalizations'],0)
  for r in rows:self.assertEqual(semantic(r),semantic(full[r['state_epoch_ns']]))
 def test_missing_peer_is_not_unknown_or_manufactured(self):
  events,config=inputs('peer_gap');rows,_=go(events,config,'G2');missing=[r for r in rows if r['gate']['state']=='missing']
  self.assertEqual([r['state_time_s'] for r in missing],list(range(25,38)))
  for r in missing:self.assertIsNone(r['peer_median_m']);self.assertFalse(r['peer_factor_used']);self.assertIsNone(r['snapshot']['peers_m'][-1]);self.assertIsNone(r['gate']['engineering_q'])
  self.assertEqual([r['gate']['state'] for r in rows[:2]],['unknown','unknown'])
 def test_unknown_input_insufficiency_is_distinct(self):
  events=[e for e in self.events if not(e['kind']=='odom' and e['vehicle_id']=='car1' and 19_000_000_000<=e['header_epoch_ns']-self.events[0]['receive_epoch_ns']<=22_000_000_000)]
  rows,_=go(events,self.config,'G2');unknown=[r for r in rows if r['status']=='missing_odom_bracket'];self.assertTrue(unknown)
  for r in unknown:self.assertEqual(r['gate']['state'],'unknown');self.assertFalse(r['peer_factor_used']);self.assertIsNone(r['auxiliary'])
 def test_old_factors_and_joint_prior_are_not_cleared(self):
  events,config=inputs('peer_bias');rows,_=go(events,config,'G2');refused=[r for r in rows if r['gate']['state']=='rejected'];self.assertTrue(refused)
  self.assertTrue(any(v is not None for v in refused[0]['snapshot']['peers_m'][:-1]))
  trail=Provenance(rows[0]['state_epoch_ns']-10**9)
  for r in rows:trail.add(r)
  self.assertTrue(rows[-1]['provenance']['prior_peer_factor_ids']);self.assertGreater(np.linalg.norm(np.array(rows[-1]['snapshot']['prior']['matrix']).T@np.array(rows[-1]['snapshot']['prior']['matrix'])[:,:]),0)
  cross=np.array(rows[-1]['snapshot']['prior']['matrix']);self.assertGreater(np.linalg.norm((cross.T@cross)[:3,3:]),1e-6);self.assertGreater(np.linalg.norm(rows[-1]['snapshot']['prior']['offset']),0)
 def test_joint_schur_cross_affine_and_constant_independent_FD(self):
  spec=importlib.util.spec_from_file_location('probe_independent_frozen_audit',ROOT/'tools/two_car_fixed_lag_fgo_v1/audit.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.residuals.peer_sigma=self.config['peer']['sigma_m']
  details=[d for r in self.cache['G2'] for d in r['marginalization_details']]
  for d in (details[0],details[-1]):module.marginal_check(d,self.config,True)
  self.assertGreater(details[-1]['cross_information_norm'],1e-6)
 def test_no_auxiliary_consumption_and_bounded_state(self):
  for r in self.cache['G2']:
   self.assertLessEqual(r['graph_states'],21);self.assertLessEqual(r['auxiliary']['graph_states'],21);self.assertEqual(r['scalar_variables'],6*r['graph_states']);self.assertTrue(all(x is None for x in r['auxiliary']['snapshot']['peers_m']));self.assertFalse(r['auxiliary']['snapshot']['peer_enabled'])
   self.assertEqual(r['state_epoch_ns'],r['auxiliary']['state_epoch_ns']);self.assertEqual(r['availability_cutoff_epoch_ns'],r['auxiliary']['availability_cutoff_epoch_ns'])
   if r['gate']['engineering_q'] is not None:
    p=antenna_pair(r['auxiliary']['pose'],self.config);q=abs(r['peer_median_m']-np.linalg.norm(np.array(p[0])-p[1]))/.2;self.assertEqual(q,r['gate']['engineering_q']);self.assertEqual(r['gate']['admitted_by_policy'],q<=3)

if __name__=='__main__':unittest.main(verbosity=2)
