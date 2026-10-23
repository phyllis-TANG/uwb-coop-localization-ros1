"""Numerical, causal-data, and covariance-policy checks for the dual ablation."""
import copy
import unittest

import numpy as np

from test_two_car_updated_comparison import fixture, OPT
from two_car_updated_comparison import CARS, JointObjective, solve
from two_car_stationary_confidence import (
    PolicyObjective, confidence_scales, near_zero_edges, solve_policy)

DETECTOR = dict(lookback_s=2., max_gap_s=.2, minimum_samples=10,
    pose_speed_max_mps=.001, pose_yaw_rate_max_degps=.1,
    twist_speed_max_mps=.005, twist_yaw_rate_max_radps=.01,
    odom_sigma_multiplier=.1)


def settings(inputs, stationary=False, confidence=False):
    configuration = dict(stationary_covariance=stationary, range_confidence=confidence)
    masks = {c: np.arange(len(inputs['times'])-1) % 2 == 0 for c in CARS}
    scales = dict(peer_sigma_m=.35, wall_sigma_m={c: {k: .25+.05*i
        for i, k in enumerate(sorted(inputs['cars'][c]['model']['anchors_xyz_m']))} for c in CARS})
    return configuration, masks, scales


class StationaryConfidenceTests(unittest.TestCase):
    def test_disabled_policies_exactly_reproduce_original_residual_jacobian_and_fit(self):
        inputs = fixture()
        cfg, masks, scales = settings(inputs)
        x = np.stack([inputs['cars'][c]['initial'] for c in CARS]).ravel()+.03
        for joint in [False, True]:
            a, b = JointObjective(inputs, joint), PolicyObjective(inputs, joint, cfg, masks, scales, DETECTOR)
            np.testing.assert_array_equal(a.fun(x), b.fun(x))
            np.testing.assert_array_equal(a.jac(x), b.jac(x))
            old = solve(inputs, joint, OPT)
            new, _ = solve_policy(inputs, joint, cfg, masks, scales, DETECTOR, OPT)
            np.testing.assert_array_equal(old['states'], new['states'])

    def test_all_policy_analytic_jacobians_match_central_differences(self):
        inputs = fixture()
        x = np.stack([inputs['cars'][c]['initial'] for c in CARS]).ravel()
        x += np.random.default_rng(17).normal(scale=.04, size=x.shape)
        for stationary in [False, True]:
            for confidence in [False, True]:
                cfg, masks, scales = settings(inputs, stationary, confidence)
                for joint in [False, True]:
                    obj = PolicyObjective(inputs, joint, cfg, masks, scales, DETECTOR)
                    step = 1e-6
                    numeric = np.column_stack([(obj.fun(x+e*step)-obj.fun(x-e*step))/(2*step)
                                               for e in np.eye(len(x))])
                    np.testing.assert_allclose(obj.jac(x), numeric, atol=5e-6, rtol=4e-6)

    def test_candidate_covariance_preserves_measured_small_motion_without_adding_factors(self):
        inputs = fixture(noisy=False)
        cfg, masks, scales = settings(inputs, True, True)
        old = JointObjective(inputs, True)
        new = PolicyObjective(inputs, True, cfg, masks, scales, DETECTOR)
        self.assertEqual(old.rows, new.rows)
        self.assertEqual(old.wall_factor_count, new.wall_factor_count)
        self.assertEqual(len(old.peer_indices), len(new.peer_indices))
        for ci, car in enumerate(CARS):
            np.testing.assert_array_equal(old.parts[ci].measured_body, new.parts[ci].measured_body)
            np.testing.assert_array_equal(old.parts[ci].measured_yaw, new.parts[ci].measured_yaw)
            np.testing.assert_array_equal(old.parts[ci].measured, new.parts[ci].measured)
            np.testing.assert_allclose(new.parts[ci].sigma_xy[masks[car]], old.parts[ci].sigma_xy[masks[car]]*.1)
            np.testing.assert_array_equal(new.parts[ci].sigma_xy[~masks[car]], old.parts[ci].sigma_xy[~masks[car]])
        fit, _ = solve_policy(inputs, True, cfg, masks, scales, DETECTOR, OPT)
        np.testing.assert_allclose(fit['states'], np.stack([inputs['cars'][c]['initial'] for c in CARS]), atol=1e-10)

    def test_detector_uses_only_past_full_window_and_retains_small_nonzero_motion(self):
        times = np.arange(0., 6.01, .05)
        rows = np.zeros((len(times), 7)); rows[:, 0] = times
        rows[:, 1] = .0005*times; rows[:, 4] = .0005
        mask, info = near_zero_edges(rows, np.arange(1., 6.), DETECTOR)
        self.assertTrue(mask.all())
        shortened, _ = near_zero_edges(rows, np.arange(.5, 2.1, .5), DETECTOR)
        self.assertFalse(shortened[0])
        self.assertFalse(shortened[1])
        mutated = rows.copy(); mutated[mutated[:, 0] > 3., 1:] += 10.
        changed, _ = near_zero_edges(mutated, np.arange(1., 6.), DETECTOR)
        np.testing.assert_array_equal(changed[:2], mask[:2])
        self.assertFalse(changed[2])

    def test_detector_rejects_motion_twist_disagreement_stale_data_and_large_gap(self):
        t = np.arange(0., 5.01, .05)
        rows = np.zeros((len(t), 7)); rows[:, 0] = t
        for column, value in [(1, .1), (3, .1), (4, .02), (5, .02), (6, .02)]:
            changed = rows.copy()
            changed[:, column] = value*t if column in [1, 3] else value
            mask, _ = near_zero_edges(changed, [1., 2., 3., 4.], DETECTOR)
            self.assertFalse(mask.any())
        stale = rows[rows[:, 0] < 3.5]
        mask, _ = near_zero_edges(stale, [3., 4.], DETECTOR)
        self.assertFalse(mask[0])
        gap = rows[~((rows[:, 0] > 2.) & (rows[:, 0] < 2.5))]
        mask, _ = near_zero_edges(gap, [2., 3.], DETECTOR)
        self.assertFalse(mask[0])

    def test_detector_wraps_yaw_and_rejects_invalid_receipt_times(self):
        t = np.arange(0., 4.01, .05)
        rows = np.zeros((len(t), 7)); rows[:, 0] = t
        angle = np.pi-.001+.0005*t
        rows[:, 3] = np.arctan2(np.sin(angle), np.cos(angle))
        mask, _ = near_zero_edges(rows, [1., 2., 3.], DETECTOR)
        self.assertTrue(mask.all())
        rows[2, 0] = rows[1, 0]
        with self.assertRaises(ValueError): near_zero_edges(rows, [1., 2.], DETECTOR)

    def test_static_scale_formula_uses_link_errors_without_adjusting_means(self):
        records = [dict(wall_errors_m={c: dict(a=a, b=b) for c in CARS}, peer_error_m=p)
                   for a, b, p in [(.3, -.1, -.4), (-.2, .15, .2)]]
        before = copy.deepcopy(records)
        scales = confidence_scales(records, .2, .2)
        self.assertEqual(records, before)
        self.assertAlmostEqual(scales['wall_sigma_m']['car1']['a'], np.hypot(.2, .3))
        self.assertAlmostEqual(scales['wall_sigma_m']['car2']['b'], .25)
        self.assertAlmostEqual(scales['peer_sigma_m'], np.hypot(.2, .4))

    def test_inputs_immutable_and_independent_model_ignores_peer_samples(self):
        inputs = fixture(); before = copy.deepcopy(inputs)
        cfg, masks, scales = settings(inputs, True, True)
        a = PolicyObjective(inputs, False, cfg, masks, scales, DETECTOR)
        x = np.stack([inputs['cars'][c]['initial'] for c in CARS]).ravel()
        changed = copy.deepcopy(inputs)
        for row in changed['peers']: row['range_m'] += 100.
        b = PolicyObjective(changed, False, cfg, masks, scales, DETECTOR)
        np.testing.assert_array_equal(a.fun(x), b.fun(x))
        for car in CARS:
            np.testing.assert_array_equal(inputs['cars'][car]['initial'], before['cars'][car]['initial'])
        self.assertEqual(inputs['peer_sigma_m'], before['peer_sigma_m'])
        self.assertEqual(inputs['peers'], before['peers'])

    def test_complete_wall_loss_and_missing_peers_are_supported(self):
        inputs = fixture()
        inputs['cars']['car1']['observations'] = [{} for _ in inputs['times']]
        for p in inputs['peers']: p['range_m'] = None
        cfg, masks, scales = settings(inputs, True, True)
        a, _ = solve_policy(inputs, False, cfg, masks, scales, DETECTOR, OPT)
        b, _ = solve_policy(inputs, True, cfg, masks, scales, DETECTOR, OPT)
        np.testing.assert_array_equal(a['states'], b['states'])
        self.assertEqual(b['peer_factor_count'], 0)

    def test_failed_solver_budget_is_rejected(self):
        inputs = fixture()
        inputs['cars']['car2']['initial'] += .3
        cfg, masks, scales = settings(inputs, True, True)
        with self.assertRaisesRegex(RuntimeError, 'Unaccepted optimization'):
            solve_policy(inputs, True, cfg, masks, scales, DETECTOR, dict(OPT, max_nfev=1))


if __name__ == '__main__':
    unittest.main()
