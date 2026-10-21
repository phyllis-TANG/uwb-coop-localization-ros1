#!/usr/bin/env python3
"""Unit checks and independent CSV-level reconstruction of the fixed grid."""
import csv
import hashlib
import io
import json
import math
import unittest
from pathlib import Path

import numpy as np

import analyze_sensitivity as analysis


ROOT = Path(__file__).resolve().parent


def rows(name):
    with (ROOT / 'results' / name).open(newline='') as stream:
        return list(csv.DictReader(stream))


class UnitTests(unittest.TestCase):
    def test_rotating_lever_and_translation(self):
        states = np.array([[0., 0., 0.], [1., 2., math.pi / 2], [3., 4., math.pi]])
        actual = analysis.antenna_xy(states, np.array([.12, -.08]))
        np.testing.assert_allclose(actual, [[.12, -.08], [1.08, 2.12], [2.88, 4.08]], atol=1e-14)

    def test_local_body_increments(self):
        states = np.array([[0., 0., math.pi / 2], [0., 1., 0.], [2., 1., 0.]])
        np.testing.assert_allclose(analysis.body_increments(states), [[1., 0.], [2., 0.]], atol=1e-14)

    def test_wrap(self):
        self.assertAlmostEqual(float(analysis.wrap(math.radians(359))), math.radians(-1))

    def test_scatter_is_not_reference_rmse(self):
        # A perfectly constant but wrong position must have zero scatter.
        result = analysis.position_metrics(np.array([[10., 10.], [10., 10.], [10., 10.]]))
        self.assertEqual(result['scatter_about_median_RMS_m'], 0.)
        self.assertEqual(result['first_last_displacement_m'], 0.)

    def test_scatter_and_median(self):
        result = analysis.position_metrics(np.array([[0., 0.], [1., 0.], [2., 0.]]))
        self.assertEqual(result['median_x_m'], 1.)
        self.assertAlmostEqual(result['scatter_about_median_RMS_m'], math.sqrt(2. / 3.))
        self.assertEqual(result['first_last_displacement_m'], 2.)

    def test_signed_range_statistics(self):
        result = analysis.statistics([-2., -1., 3.])
        self.assertEqual(result['median_m'], -1.)
        self.assertEqual(result['abs_median_m'], 2.)
        self.assertAlmostEqual(result['RMS_m'], math.sqrt(14. / 3.))

    def test_half_open_phase(self):
        phases = [{'phase': 'left', 'start_s': 0., 'end_s': 1.},
                  {'phase': 'right', 'start_s': 1., 'end_s': 2.}]
        self.assertEqual(analysis.phase_at(1., phases), 'right')
        with self.assertRaises(ValueError):
            analysis.phase_at(2., phases)


class ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tracks = rows('trajectories.csv')
        cls.endpoints = rows('endpoint_comparison.csv')
        cls.static = rows('stationary_diagnostics.csv')
        cls.residuals = rows('residual_summary.csv')
        cls.steps = rows('odom_step_residuals.csv')

    def test_protocol_and_complete_grid(self):
        self.assertEqual(analysis.digest((ROOT / 'protocol.json').read_bytes()), analysis.EXPECTED_PROTOCOL_SHA256)
        expected = {(r, s, o) for r in ['004023', '005135'] for s in [.5, 1., 2.] for o in [.5, 1., 2.]}
        actual = {(r['run'], float(r['range_scale']), float(r['odom_translation_scale'])) for r in self.endpoints}
        self.assertEqual(actual, expected)
        self.assertEqual(len(self.endpoints), 18)
        self.assertEqual(len(self.static), 72)
        self.assertEqual(len(self.tracks), 1692)
        self.assertEqual(len(self.steps), 1674)
        self.assertTrue(all(r['optimizer_success'] == 'True' for r in self.endpoints))
        records = json.loads((ROOT / 'results/optimizer_records.json').read_text())
        self.assertEqual(len(records), 18)
        self.assertTrue(all(r['optimizer_success'] and r['optimizer_status'] > 0 for r in records))

    def test_endpoints_from_trajectory_and_manual_reference(self):
        targets = {'004023': [2.97, 3.11], '005135': [2.93, 3.04]}
        for row in self.endpoints:
            with self.subTest(run=row['run'], cell=row['cell']):
                selected = [t for t in self.tracks if t['run'] == row['run'] and t['cell'] == row['cell']
                    and float(row['window_start_s']) <= float(t['time_s']) < float(row['window_end_s'])]
                xy = np.array([[float(t['antenna_x_m']), float(t['antenna_y_m'])] for t in selected])
                self.assertEqual(len(xy), 5)
                center = np.median(xy, axis=0)
                self.assertAlmostEqual(float(center[0]), float(row['median_x_m']), places=13)
                self.assertAlmostEqual(float(center[1]), float(row['median_y_m']), places=13)
                expected = math.dist(center, targets[row['run']])
                self.assertAlmostEqual(expected, float(row['endpoint_difference_m']), places=13)

    def test_all_stationary_metrics_from_trajectory(self):
        for row in self.static:
            with self.subTest(run=row['run'], cell=row['cell'], phase=row['phase']):
                selected = [t for t in self.tracks if t['run'] == row['run'] and t['cell'] == row['cell']
                    and float(row['window_start_s']) <= float(t['time_s']) < float(row['window_end_s'])]
                xy = np.array([[float(t['antenna_x_m']), float(t['antenna_y_m'])] for t in selected])
                center = np.median(xy, axis=0)
                scatter = math.sqrt(sum(math.dist(p, center) ** 2 for p in xy) / len(xy))
                self.assertEqual(len(xy), int(row['samples']))
                self.assertAlmostEqual(scatter, float(row['scatter_about_median_RMS_m']), places=13)
                self.assertAlmostEqual(math.dist(xy[-1], xy[0]), float(row['first_last_displacement_m']), places=13)

    def test_odom_residual_summary_from_steps(self):
        for row in self.residuals:
            selected = [s for s in self.steps if s['run'] == row['run'] and s['cell'] == row['cell']]
            mean_sq = sum(float(s['body_x_residual_m']) ** 2 + float(s['body_y_residual_m']) ** 2 for s in selected) / len(selected)
            yaw_sq = sum(float(s['yaw_residual_deg']) ** 2 for s in selected) / len(selected)
            self.assertAlmostEqual(math.sqrt(mean_sq), float(row['odom_step_translation_vector_RMS_m']), places=13)
            self.assertAlmostEqual(math.sqrt(yaw_sq), float(row['odom_step_yaw_RMS_deg']), places=13)
            self.assertLess(float(row['reconstructed_cost_abs_difference']), 1e-8)

    def test_range_summary_matches_link_partition(self):
        links = rows('residual_by_link.csv')
        for row in self.residuals:
            selected = [s for s in links if s['run'] == row['run'] and s['cell'] == row['cell']]
            count = sum(int(s['samples']) for s in selected)
            mean_sq = sum(int(s['samples']) * float(s['RMS_m']) ** 2 for s in selected) / count
            self.assertEqual(count, int(row['range_factors']))
            self.assertAlmostEqual(math.sqrt(mean_sq), float(row['range_RMS_m']), places=13)

    def test_reported_shifts_from_frozen_baseline(self):
        for row in self.endpoints:
            selected = [t for t in self.tracks if t['run'] == row['run'] and t['cell'] == row['cell']]
            baseline = {float(t['time_s']): (float(t['antenna_x_m']), float(t['antenna_y_m']))
                        for t in self.tracks if t['run'] == row['run'] and t['cell'] == 'r1_o1'}
            shifts = [math.dist([float(t['antenna_x_m']), float(t['antenna_y_m'])], baseline[float(t['time_s'])]) for t in selected]
            self.assertAlmostEqual(max(shifts), float(row['trajectory_displacement_from_F_max_m']), places=13)
            self.assertAlmostEqual(float(np.median(shifts)), float(row['trajectory_displacement_from_F_median_m']), places=13)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    verification = {'tests_run': result.testsRun, 'failures': len(result.failures),
                    'errors': len(result.errors), 'successful': result.wasSuccessful(),
                    'verification_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (ROOT / 'results/test_verification.json').write_text(json.dumps(verification, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
