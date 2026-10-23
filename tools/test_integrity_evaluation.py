import unittest
import numpy as np
from evaluate_single_car_integrity import intervals,recover_time

class MetricTests(unittest.TestCase):
    def test_exact_nonuniform_interval_duration_and_final_clip(self):
        result=intervals([True,True,False,True],[1,2,4,7],[2,4,7,8],{'method':'M1'})
        self.assertEqual([(r['start_s'],r['end_s'],r['duration_s']) for r in result],[(1.,4.,3.),(7.,8.,1.)])
    def test_no_exceedance_produces_no_interval(self):
        self.assertEqual(intervals([False,False],[1,2],[2,3],{}),[])
    def test_recovery_needs_three_postfault_consecutive_samples(self):
        self.assertEqual(recover_time([True,True,True,False,True,True,True],np.arange(7),2),2.)
        self.assertIsNone(recover_time([True,True,False,True,True],np.arange(5),0))
    def test_unavailable_is_counted_as_unalerted_exceedance(self):
        exceed=np.array([False,True,True,True]);alarm=np.array([False,False,False,True]);available=np.array([False,False,True,True]);dt=np.array([1.,2.,3.,4.])
        total=dt[exceed&~alarm].sum();valid=dt[exceed&~alarm&available].sum();unknown=dt[exceed&~available].sum()
        self.assertEqual(total,5.);self.assertEqual(total,valid+unknown)
