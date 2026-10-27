import math
import unittest
from endpoints import endpoint
from prepare_reuse import selected

class EndpointTests(unittest.TestCase):
    def case(self):return dict(id='004023',evaluation_window_s=[10.25,15.25],end_antenna_xyz_m=[3.,4.,.2])
    def row(self,t,x,y,valid='True'):return dict(state_time_s=t,antenna_x_m=x,antenna_y_m=y,estimate_valid=valid)
    def test_frozen_fractional_window_not_reselected(self):
        v=endpoint([self.row(10.2,999,999),self.row(11,3,4),self.row(15,3.2,4.2),self.row(15.3,999,999)],self.case())
        self.assertEqual(v['selected_state_times_s'],[11.,15.]);self.assertAlmostEqual(v['all_finite']['distance_to_manual_endpoint_m'],math.sqrt(.02))
    def test_valid_denominator_separate_from_finite(self):
        v=endpoint([self.row(11,3,4),self.row(12,5,6,'False')],self.case())
        self.assertEqual((v['scheduled_window_outputs'],v['finite_outputs'],v['valid_outputs']),(2,2,1));self.assertEqual(v['estimate_valid_only']['median_xy_m'],[3.,4.])
    def test_nonfinite_preserved_in_denominator(self):
        v=endpoint([self.row(11,float('nan'),4),self.row(12,3,4)],self.case());self.assertEqual((v['scheduled_window_outputs'],v['finite_outputs']),(2,1))
    def test_empty_window_is_explicit_null(self):
        v=endpoint([],self.case());self.assertIsNone(v['all_finite']['median_xy_m']);self.assertIsNone(v['all_finite']['distance_to_manual_endpoint_m'])
    def test_unknown_validity_not_silently_healthy(self):
        with self.assertRaisesRegex(ValueError,'validity'):endpoint([self.row(11,3,4,None)],self.case())
    def test_reference_never_declared_exact(self):
        v=endpoint([self.row(11,3,4)],self.case());self.assertIsNone(v['manual_reference_uncertainty_m']);self.assertEqual(v['all_finite']['distance_to_manual_endpoint_m'],0.)
    def test_reuse_full_Q0_Q1_and_only_old_publications_F1_F2(self):
        self.assertTrue(selected('F0_F3/004023_F3/updates.jsonl.gz'));self.assertTrue(selected('F0_F3/005135_F2/published.csv'));self.assertFalse(selected('F0_F3/005135_F2/updates.jsonl.gz'))

class InputReferenceTests(unittest.TestCase):
    def test_no_manual_reference_or_truth_passed_to_estimator(self):
        from prepare_ready import no_reference_keys
        no_reference_keys({'model':{'start_antenna_xyz_m':[2.,2.,.2]}})
        for key in ('evaluation_window_s','end_antenna_xyz_m','fault_label','truth'):
            with self.assertRaisesRegex(ValueError,'reference/fault label'):no_reference_keys({'nested':[{key:None}]})
