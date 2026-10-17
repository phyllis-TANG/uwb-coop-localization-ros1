#!/usr/bin/env python
"""Hardware-independent tests for the fixed-height offline session model."""
import inspect
import unittest
from collections import Counter

import numpy as np

import analyze_october_field_session as analysis
import diagnose_october_L_segments as diagnostics


class FieldSessionTests(unittest.TestCase):
    def test_odom_gate_uses_link_bias_and_keeps_boundary(self):
        anchors = {'a': [0., 0., 2.], 'b': [5., 0., 2.],
                   'c': [5., 5., 2.]}
        point = np.asarray([2., 2., .2])
        biases = {'a': .3, 'b': .2, 'c': .4}
        ranges = dict((key, float(np.linalg.norm(point-xyz))+biases[key])
                      for key, xyz in anchors.items())
        # Exactly representable threshold avoids rounding at the boundary.
        ranges['b'] += .5
        ranges['c'] += 1.2
        original = ranges.copy()
        rejected = Counter()
        kept = analysis.gate_by_odom(ranges, point[:2], anchors, biases,
                                     point[2], .5, rejected)
        self.assertEqual(set(kept), set(['a', 'b']))
        self.assertEqual(rejected, Counter({'c': 1}))
        self.assertEqual(ranges, original)

    def test_graph_retains_two_ranges_when_standalone_xy_is_missing(self):
        anchors = {'a': [0., 0., 2.], 'b': [5., 0., 2.],
                   'c': [5., 5., 2.]}
        local = np.asarray([[0., 0., 0.], [.5, 0., 0.], [1., 0., 0.]])
        start = np.asarray([2., 2.])
        expected = local[:, :2]+start
        observations = []
        for xy in expected:
            point = np.r_[xy, .2]
            observations.append(dict((key, float(np.linalg.norm(point-xyz)))
                                     for key, xyz in anchors.items()))
        del observations[1]['c']
        xy, rms = analysis.solve_xy(observations[1], anchors, .2)
        self.assertTrue(np.isnan(xy).all())
        self.assertTrue(np.isnan(rms))
        parameters = {'odom_translation_sigma_m': .03,
                      'odom_yaw_sigma_deg': 2., 'range_sigma_m': .2,
                      'prior_position_sigma_m': .2,
                      'prior_heading_sigma_deg': 5.}
        graph, info = analysis.optimize_graph(
            local, observations, anchors, dict((key, 0.) for key in anchors),
            .2, start, 0., np.asarray([0., 1., 2.]), parameters)
        self.assertTrue(info['optimizer_success'])
        self.assertEqual(info['range_factors'], 8)
        np.testing.assert_allclose(graph[:, :2], expected, atol=1e-6)

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

    def test_initial_window_excludes_early_motion_command(self):
        windows = analysis.endpoint_windows({'cmd': [(4.4, -.045, 0., 0.)]}, .15, 120.)
        self.assertAlmostEqual(windows[0][1], 3.9)
        with self.assertRaises(ValueError):
            analysis.endpoint_windows({'cmd': [(.9, .045, 0., 0.)]}, .15, 120.)

    def test_reverse_motion_has_two_translation_phases(self):
        data = {'cmd': [(4., -.045, 0., 0.), (30., 0., 0., 0.),
                        (35., 0., 0., -.2), (39., 0., 0., 0.),
                        (44., -.045, 0., 0.), (70., -.045, 0., 0.)]}
        bounds = diagnostics.phase_bounds(data)
        self.assertEqual(bounds['first_motion'], 4.)
        self.assertEqual(bounds['second_translation'], 44.)
        self.assertEqual(bounds['last_translation'], 70.)
        with self.assertRaises(ValueError):
            diagnostics.phase_bounds({'cmd': [(4., -.045, 0., 0.)]})


if __name__ == '__main__':
    unittest.main()
