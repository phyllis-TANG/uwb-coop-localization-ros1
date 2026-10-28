import copy,importlib.util,json,unittest
from pathlib import Path
import numpy as np
from io_evidence import ART,read
from signals import *
class ReadOnlyContracts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=Path(json.loads((ART/'evidence-v1/ARCHIVE_CHECK.json').read_text())['matrix_root']);inp=cls.root/'inputs/nominal_seed101';cls.c=json.loads((inp/'config.json').read_text());cls.e=read(inp/'events.jsonl.gz');cls.r=read(cls.root/'reused/nominal_seed101__I/updates.jsonl.gz')[2];cls.streams={c:[e for e in cls.e if e['kind']=='uwb' and e['vehicle_id']==c] for c in CARS};cls.origin=cls.e[0]['receive_epoch_ns']
  spec=importlib.util.spec_from_file_location('scalar_fixture',cls.root/'source/tools/two_car_fixed_lag_fgo_v1/audit.py');cls.audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.audit)
 def test_rotated_antenna_and_wrap_not_false_jump(self):
  m=dict(base_to_antenna_body_xy_m=[.1,.2],antenna_height_m=.3)
  np.testing.assert_allclose(antenna([1,2,np.pi/2],m),[.8,2.1,.3],atol=1e-14)
  self.assertAlmostEqual(wrap((-np.pi+.01)-(np.pi-.01)),.02,places=12)
 def test_local_signals_ignore_peer_truth_labels_and_future_payload(self):
  a=construct_local(self.r,self.c,self.streams,self.origin,self.audit);r=copy.deepcopy(self.r);streams=copy.deepcopy(self.streams)
  r['truth']={'pose':[900,800,700]};r['fault_label']='changed';r['peer_median_m']=900.;r['main_pose']=[900.]*6
  for car in CARS:
   key='node_0' if car=='car1' else 'node_1'
   for e in streams[car]:e['value'][key]=900.;e['truth']='unused';e['fault_label']='unused'
   future=copy.deepcopy(streams[car][0]);future['header_epoch_ns']=r['state_epoch_ns'];future['receive_epoch_ns']=r['availability_cutoff_epoch_ns']+1
   for k in self.c['models'][car]['anchors_xyz_m']:future['value'][k]=900.
   streams[car].append(future)
  b=construct_local(r,self.c,streams,self.origin,self.audit);self.assertEqual(a,b)
 def test_information_proxy_unknown_startup_and_prior_sensitive(self):
  s=copy.deepcopy(self.r['snapshot']);a=gn_proxy(s,self.c,self.audit,True);self.assertEqual(a['status'],'nominal_GN_proxy_not_published_covariance');self.assertLess(a['solve_relative_residual'],1e-7)
  self.assertEqual(gn_proxy(s,self.c,self.audit,False)['xy_trace_sigma'],[None,None])
  s['prior']['matrix']=(np.array(s['prior']['matrix'])*.1).tolist();b=gn_proxy(s,self.c,self.audit,True)
  self.assertTrue(all(y>x for x,y in zip(a['xy_trace_sigma'],b['xy_trace_sigma'])))
 def test_local_signals_refuse_peer_enabled_snapshot(self):
  r=copy.deepcopy(self.r);r['snapshot']['peer_enabled']=True
  with self.assertRaises(AssertionError):construct_local(r,self.c,self.streams,self.origin,self.audit)
if __name__=='__main__':unittest.main(verbosity=2)
