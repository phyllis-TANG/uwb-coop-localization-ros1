#!/usr/bin/env python
"""Hardware-independent tests for the fixed-height offline session model."""
import inspect
import unittest

import numpy as np

import analyze_october_field_session as analysis


class FieldSessionTests(unittest.TestCase):
    def test_synthetic_L_and_robust_range(self):
        analysis.self_test()

    def test_reverse_first_leg_alignment(self):
        # Reverse body motion along -local-x travels +room-y when body faces -y.
        local = np.asarray([[0., 0., 0.], [-1., 0., 0.], [-1., 1., -np.pi/2]])
        aligned = analysis.align_odom(local, [2., 2., .2], -np.pi/2)
        np.testing.assert_allclose(aligned[:, :2], [[2., 2.], [2., 3.], [3., 3.]], atol=1e-12)

    def test_bin_has_explicit_support_and_tag_selection(self):
        rows = [(float(i)*.01, {'a': 2.}, 'node_0') for i in range(5)]
        rows += [(.02, {'a': 100.}, 'node_1')]
        self.assertEqual(analysis.bin_ranges(rows, [.02], .1), [{'a': 2.}])
        self.assertEqual(analysis.bin_ranges(rows[:4], [.02], .1), [{}])

    def test_three_noncollinear_anchors_solve_height_geometry(self):
        anchors = {'a': [0., 0., 2.], 'b': [5., 0., 2.5], 'c': [5., 5., 2.]}
        point = np.asarray([1.8, 3.1, .2])
        ranges = dict((k, float(np.linalg.norm(point-v))) for k, v in anchors.items())
        xy, rms = analysis.solve_xy(ranges, anchors, .2)
        np.testing.assert_allclose(xy, point[:2], atol=1e-7)
        self.assertLess(rms, 1e-7)

    def test_endpoint_evaluation_does_not_mutate_trajectory(self):
        xy = np.asarray([[2., 2.], [3., 3.]])
        before = xy.copy()
        metric = analysis.endpoint_metrics(xy, [2., 2.], [2.95, 3.11])
        self.assertAlmostEqual(metric['end_reference_difference_m'], np.hypot(.05, .11))
        np.testing.assert_array_equal(xy, before)
        # Optimizer API has no evaluation endpoint or desired trajectory input.
        self.assertNotIn('end_reference', inspect.getfullargspec(analysis.optimize_graph).args
                         if hasattr(inspect, 'getfullargspec') else
                         inspect.getargspec(analysis.optimize_graph).args)


if __name__ == '__main__':
    unittest.main()
