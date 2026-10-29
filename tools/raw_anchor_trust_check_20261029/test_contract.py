"""Small algebra and provenance checks; never import a locator or read bag bytes."""
import csv,json,sys,unittest
from pathlib import Path
import numpy as np
from common import ROOT,sha
from raw_check import range_jacobian
D=ROOT/'docs/research/raw_anchor_trust_check_20261029'
class Algebra(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rows=json.loads((D/'results/static_matrices.json').read_text())
 def test_four_preregistered_points_only(self):
  self.assertEqual([r['t_s'] for r in self.rows],[23,24,37,54])
 def test_analytic_derivative_independent_central_difference(self):
  # Analytic formula vs direct scalar distances; tolerance fixed here before tests.
  for r in self.rows:
   p=np.array(r['antenna_xyz_m']);a=np.array(r['anchors_xyz_m']);_,J=range_jacobian(p,a)
   for k in range(3):
    d=np.eye(3)[k]*1e-6
    fd=np.array([(sum((p+d-q)**2)**.5-sum((p-d-q)**2)**.5)/2e-6 for q in a])
    np.testing.assert_allclose(J[:,k],fd,atol=2e-9,rtol=0)
 def test_distinct_bias_models_and_local_sparse_condition(self):
  for r in self.rows:
   G=np.array(r['Gxyz'])[:,:2]
   self.assertEqual(np.linalg.matrix_rank(G),2)
   self.assertEqual(np.linalg.matrix_rank(np.c_[G,np.ones(4)]),3)
   H3=np.c_[G,np.eye(4)]
   self.assertEqual(H3.shape[1]-np.linalg.matrix_rank(H3),2)
   # Arbitrary-link bias exactly cancels any local XY perturbation.
   np.testing.assert_allclose(H3@np.r_[np.eye(2),-G],0,atol=1e-14,rtol=0)
   for i in range(4):self.assertEqual(np.linalg.matrix_rank(np.c_[G,np.eye(4)[:,i]]),3)
   for p in r['healthy_pair_checks'].values():self.assertEqual(p['rank'],2)
   # When bias=0, all four H1 identities predict the same observation: rank != attribution.
   z=np.linalg.norm(np.array(r['antenna_xyz_m'])-r['anchors_xyz_m'],axis=1)
   for i in range(4):np.testing.assert_array_equal(z+np.eye(4)[:,i]*0,z)
 def test_unknown_height_removes_H2_residual_redundancy(self):
  for r in self.rows:
   h=r['hypotheses']['H2_unknown_height'];self.assertEqual(h['rank'],4);self.assertEqual(h['residual_dof'],0)
 def test_prefix_and_peer_free_saved_identity(self):
  with (D/'results/support_records.csv').open() as f:support=list(csv.DictReader(f))
  for r in self.rows:
   self.assertEqual(r['reference_prior_peer_n'],0)
   self.assertEqual(r['cutoff_epoch_ns']-r['state_epoch_ns'],10**9)
   records=[s for s in support if float(s['t_s'])==r['t_s']];self.assertTrue(records)
   self.assertEqual(len(records),len({s['source_observation_id'] for s in records}))
   for s in records:self.assertLessEqual(int(s['receive_epoch_ns']),r['cutoff_epoch_ns'])
class Metadata(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with (D/'DATA_USE_MATRIX.csv').open() as f:cls.rows=list(csv.DictReader(f))
  cls.by={r['record_id']:r for r in cls.rows}
 def test_98_entries_not_98_trials(self):
  self.assertEqual(len(self.rows),98);self.assertEqual(len({r['file'] for r in self.rows}),98)
  self.assertEqual(sum(r['inventory']=='historical_catalog' for r in self.rows),76)
  self.assertEqual(sum(r['data_kind']=='simulated' for r in self.rows),2)
  for r in self.rows:self.assertRegex(r['sha256'],r'^[0-9a-f]{64}$')
 def test_unknown_not_zero_or_new_validation(self):
  for r in self.rows:
   self.assertEqual(r['metadata_verified_this_round'],'True')
   for f in ['bag_sha_recomputed_this_round','message_decoded_this_round','video_read_this_round']:self.assertEqual(r[f],'False')
  for rid in ['B071','B072','B030','B031','B051']:self.assertTrue(self.by[rid]['reference_grade'].startswith('C'))
  self.assertTrue(self.by['B019']['reference_grade'].startswith('B_candidate'))
 def test_retry_anomaly_and_occlusion_status(self):
  self.assertIn('184755',self.by['T10']['file'])
  aborted=next(r for r in self.rows if '184047' in r['file']);self.assertIn('aborted',aborted['experiment_completion'])
  self.assertIn('004023',self.by['B055']['file']);self.assertIn('completed_with_measurement_anomaly',self.by['B055']['experiment_completion'])
  for rid in ['T14','T15']:
   self.assertIn('已存在且解码',self.by[rid]['minimum_missing']);self.assertIn('遮挡',self.by[rid]['minimum_missing'])
 def test_holdout_exposure_is_not_erased(self):
  held={r['record_id'] for r in self.rows if r['development_holdout']=='protected_whole_bag_holdout'}
  self.assertEqual(held,{'T09','T11','T13','T15'})
  for rid in held:self.assertIn('不能称完全未见',self.by[rid]['documented_exposure'])
  self.assertIn('T10静止Car2初值',self.by['T09']['documented_exposure'])
 def test_receipts_and_source_scope(self):
  receipt=json.loads((D/'results/run.json').read_text())
  for name,h in receipt['outputs'].items():self.assertEqual(sha(D/'results'/name),h)
  for name in ['raw_check.py','common.py']:self.assertEqual(sha(Path(__file__).parent/name),receipt['source_sha256'][name])
  s=json.loads((D/'SOURCE_INDEX.json').read_text());self.assertTrue(all(x['matches_actual_main'] for x in s.values()))
  self.assertFalse(any(m in sys.modules for m in ['graph','frontend','core','scipy.optimize']))
if __name__=='__main__':unittest.main(verbosity=2)
