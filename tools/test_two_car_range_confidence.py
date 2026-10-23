"""Numerical and information-isolation tests for omitted-link weighting."""
import copy
import unittest

import numpy as np

from test_two_car_updated_comparison import fixture, OPT
from test_two_car_stationary_confidence import DETECTOR, settings
from two_car_updated_comparison import CARS, JointObjective
from two_car_range_confidence import (
    AdaptiveObjective, PredictionFilter, lagged_weight, predict_confidence, range_prediction, solve_objective)

POLICY = dict(history_bins=3, minimum_valid_history=3, threshold_abs_z=2., minimum_weight=.1)


class RangeConfidenceTests(unittest.TestCase):
    def test_range_geometry_jacobian_with_nonzero_lever(self):
        inputs = fixture(); model = inputs['cars']['car1']['model']
        state = np.array([1.2, 3.7, .8]); covariance = np.diag([.01, .02, .03])
        anchor = model['anchors_xyz_m']['node_10']
        _, _, h = range_prediction(state, covariance, model, anchor)
        numeric = [(range_prediction(state+e*1e-6, covariance, model, anchor)[0]-
                    range_prediction(state-e*1e-6, covariance, model, anchor)[0])/2e-6 for e in np.eye(3)]
        np.testing.assert_allclose(h, numeric, atol=1e-9)

    def test_checked_wall_never_enters_own_prediction(self):
        inputs = fixture(n=9); original = predict_confidence(inputs, POLICY)
        changed = copy.deepcopy(inputs)
        for row in changed['cars']['car2']['observations']: row['node_10'] += 1.
        actual = predict_confidence(changed, POLICY)
        for key in ['predicted_m', 'prediction_sd_with_measurement_m']:
            np.testing.assert_array_equal([r[key] for r in original['car2/node_10']],
                                          [r[key] for r in actual['car2/node_10']])
        self.assertLess(actual['car2/node_10'][-1]['weight'], 1.)

    def test_peer_ranges_never_enter_peer_prediction(self):
        inputs = fixture(n=8); original = predict_confidence(inputs, POLICY)
        changed = copy.deepcopy(inputs)
        for row in changed['peers']: row['range_m'] += 1.
        actual = predict_confidence(changed, POLICY)
        np.testing.assert_array_equal([r['predicted_m'] for r in original['peer']],
                                      [r['predicted_m'] for r in actual['peer']])
        self.assertLess(actual['peer'][-1]['weight'], 1.)

    def test_future_data_do_not_change_past_predictions_or_weights(self):
        inputs = fixture(n=9); original = predict_confidence(inputs, POLICY)
        changed = copy.deepcopy(inputs)
        for car in CARS:
            changed['cars'][car]['local'][5:] += 2.
            for row in changed['cars'][car]['observations'][5:]:
                for key in row: row[key] += 2.
        for row in changed['peers'][5:]: row['range_m'] += 2.
        actual = predict_confidence(changed, POLICY)
        for name in original:
            self.assertEqual(original[name][:5], actual[name][:5])

    def test_current_checked_sample_cannot_change_current_weight(self):
        inputs = fixture(n=7); original = predict_confidence(inputs, POLICY)
        changed = copy.deepcopy(inputs)
        changed['cars']['car1']['observations'][3]['node_10'] += 10.
        actual = predict_confidence(changed, POLICY)
        self.assertEqual(original['car1/node_10'][3]['weight'], actual['car1/node_10'][3]['weight'])

    def test_lagged_history_warmup_persistence_missing_and_limits(self):
        self.assertEqual(lagged_weight([8., 8.], POLICY), 1.)
        self.assertEqual(lagged_weight([1., 8., 1.], POLICY), 1.)
        self.assertAlmostEqual(lagged_weight([4., 4., 4.], POLICY), .25)
        self.assertEqual(lagged_weight([100., 100., 100.], POLICY), .1)
        self.assertEqual(lagged_weight([None, 4., 4.], POLICY), 1.)
        self.assertEqual(lagged_weight([4., 4., 4., 0., 0., 0.], POLICY), 1.)

    def test_exact_motion_prediction_and_covariance_positive(self):
        inputs = fixture(n=7, noisy=False)
        confidence = predict_confidence(inputs, POLICY)
        for rows in confidence.values():
            for row in rows:
                self.assertAlmostEqual(row['predicted_m'], row['measured_corrected_m'], places=11)
                self.assertEqual(row['weight'], 1.)
        model = inputs['cars']['car1']['model']; f = PredictionFilter(model)
        for i in range(1, 7):
            f.propagate(inputs['cars']['car1']['local'][i-1], inputs['cars']['car1']['local'][i], 1.)
            f.update_other_walls(inputs['cars']['car1']['observations'][i], omitted='node_10')
            self.assertGreater(np.linalg.eigvalsh(f.covariance).min(), 0.)

    def test_unit_weights_reproduce_original_residual_and_jacobian(self):
        inputs = fixture(); _, masks, scales = settings(inputs)
        confidence = predict_confidence(inputs, POLICY)
        for rows in confidence.values():
            for row in rows: row['weight'] = 1.
        x = np.stack([inputs['cars'][c]['initial'] for c in CARS]).ravel()+.02
        for joint in [False, True]:
            a = JointObjective(inputs, joint)
            b = AdaptiveObjective(inputs, joint, False, masks, scales, DETECTOR, confidence)
            np.testing.assert_array_equal(a.fun(x), b.fun(x))
            np.testing.assert_array_equal(a.jac(x), b.jac(x))

    def test_time_varying_scale_full_jacobian_and_factor_means(self):
        inputs = fixture(); _, masks, scales = settings(inputs)
        confidence = predict_confidence(inputs, POLICY)
        for rows in confidence.values():
            for i, row in enumerate(rows): row['weight'] = .2+.1*i
        x = np.stack([inputs['cars'][c]['initial'] for c in CARS]).ravel()+.02
        for stationary in [False, True]:
            for joint in [False, True]:
                obj = AdaptiveObjective(inputs, joint, stationary, masks, scales, DETECTOR, confidence)
                baseline = JointObjective(inputs, joint)
                self.assertEqual(obj.rows, baseline.rows)
                for a, b in zip(obj.parts, baseline.parts):
                    np.testing.assert_array_equal(a.measured, b.measured)
                    np.testing.assert_array_equal(a.measured_body, b.measured_body)
                numeric = np.column_stack([(obj.fun(x+e*1e-6)-obj.fun(x-e*1e-6))/2e-6 for e in np.eye(len(x))])
                np.testing.assert_allclose(obj.jac(x), numeric, atol=5e-6, rtol=5e-6)

    def test_missing_measurements_and_failed_solver(self):
        inputs = fixture(); _, masks, scales = settings(inputs)
        inputs['cars']['car1']['observations'] = [{} for _ in inputs['times']]
        for row in inputs['peers']: row['range_m'] = None
        confidence = predict_confidence(inputs, POLICY)
        self.assertTrue(all(r['weight'] == 1. for r in confidence['peer']))
        obj = AdaptiveObjective(inputs, True, True, masks, scales, DETECTOR, confidence)
        inputs['cars']['car2']['initial'] += .3
        with self.assertRaisesRegex(RuntimeError, 'Unaccepted optimization'):
            solve_objective(inputs, obj, dict(OPT, max_nfev=1))


if __name__ == '__main__': unittest.main()
