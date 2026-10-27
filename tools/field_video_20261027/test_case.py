"""Geometry/precision negative tests plus readback of actual T10 stage outputs."""
import csv
import json
import os
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

import evidence as e


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.K = np.array([[1300., 0, 1920], [0, 1100, 1080], [0, 0, 1.]])
        self.D = np.array([.1, -.03, .002, -.001, .005])
        self.T = np.diag([1., -1., -1., 1.])
        self.T[:3, 3] = [2., 3., 4.]
        self.center = np.array([1.1, 2.2, .23])
        self.angle = .4
        self.obj = np.array([[-.072, .072, 0], [.072, .072, 0], [.072, -.072, 0], [-.072, -.072, 0]])
        c, s = np.cos(self.angle), np.sin(self.angle)
        self.world = self.center + self.obj @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.]]).T
        self.corners = cv2.projectPoints(self.world, np.array([np.pi, 0, 0]),
                                         np.array([-2., 3., 4.]), self.K, self.D)[0].reshape(4, 2)

    def test_distorted_raised_plane_inverse(self):
        center, vertices, _ = e.conditional_geometry(self.corners, self.K, self.D, self.T, .23)
        np.testing.assert_allclose(center, self.center, atol=1e-7)
        np.testing.assert_allclose(vertices, self.world, atol=1e-7)

    def test_title_edge_is_canonical_plus_y(self):
        _, _, heading = e.conditional_geometry(self.corners, self.K, self.D, self.T, .23)
        self.assertAlmostEqual(heading, self.angle + np.pi / 2, places=7)

    def test_ground_plane_creates_height_bias(self):
        raised, _, _ = e.conditional_geometry(self.corners, self.K, self.D, self.T, .23)
        ground, _, _ = e.conditional_geometry(self.corners, self.K, self.D, self.T, 0)
        self.assertGreater(np.linalg.norm(raised[:2] - ground[:2]), .05)

    def test_body_lever_rotates_and_unknown_rejected(self):
        np.testing.assert_allclose(e.antenna_candidate([1, 2, .37], np.pi / 2, [.07, -.13, -.2]),
                                   [1.13, 2.07, .17], atol=1e-12)
        with self.assertRaises(ValueError):
            e.antenna_candidate([1, 2, .23], None, [-.17, .025, -.03])

    def test_camera_ray_behind_plane_rejected(self):
        with self.assertRaises(ValueError):
            e.intersect_normalized([0, 0], self.T, 5.)

    def test_degenerate_quad_rejected(self):
        with self.assertRaises(ValueError):
            e.projective_center([[0, 0], [1, 0], [2, 0], [3, 0]])


class ProvenanceTests(unittest.TestCase):
    def sample(self):
        ledger = [{'frame_index': '0', 'pts_ticks': '0', 'time_base_num': '1', 'time_base_den': '600', 'video_time_s': '0'},
                  {'frame_index': '1', 'pts_ticks': '21', 'time_base_num': '1', 'time_base_den': '600', 'video_time_s': '.035'}]
        obs = [dict(ledger[1], vehicle_id='car1')]
        return ledger, obs

    def test_pts_irregular_ticks_preserved(self):
        ledger, obs = self.sample()
        self.assertEqual(e.validate_pts(obs, ledger)['status'], 'passed')

    def test_wrong_pts_and_duplicate_observation_rejected(self):
        ledger, obs = self.sample()
        with self.assertRaises(ValueError):
            e.validate_pts(obs * 2, ledger)
        obs[0]['pts_ticks'] = '20'
        with self.assertRaises(ValueError):
            e.validate_pts(obs, ledger)

    def test_nonmonotonic_ledger_rejected(self):
        ledger, obs = self.sample()
        ledger[1]['pts_ticks'] = '0'
        with self.assertRaises(ValueError):
            e.validate_pts(obs, ledger)

    def test_integer_epoch_never_rounded_as_float(self):
        origin = '1792925285431466217'
        self.assertEqual(e.candidate_receive_epoch_ns(21, 1, 600, 1, '-0.01', origin),
                         str(int(origin) + 25000000))

    def test_strict_json_and_exclusive_outputs(self):
        with tempfile.TemporaryDirectory(prefix='video_ref_test_') as directory:
            p = Path(directory) / 'test.json'
            e.write_json(p, {'unknown': None})
            self.assertIsNone(e.load_json(p)['unknown'])
            with self.assertRaises(FileExistsError):
                e.write_json(p, {'overwrite': True})
            bad = Path(directory) / 'bad.json'
            bad.write_text('{"value":NaN}', encoding='utf-8')
            with self.assertRaises(ValueError):
                e.load_json(bad)


class ActualOutputTests(unittest.TestCase):
    def setUp(self):
        value = os.environ.get('VIDEO_CASE_OUTPUT')
        if not value:
            self.skipTest('Set VIDEO_CASE_OUTPUT for actual-stage readback')
        self.output = Path(value)
        self.repo = Path(__file__).resolve().parents[2]

    def test_reused_T10_observations_and_ledger(self):
        rows = [r for r in e.read_csv(self.output / 'marker_observations.csv') if r['experiment_id'] == 'T10']
        self.assertEqual(len(rows), 388)
        self.assertEqual(e.validate_pts(rows, e.read_csv(self.output / 'T10_frame_pts.csv'))['ledger_frames'], 2903)
        self.assertEqual({r['observation_status'] for r in rows}, {'decoded'})

    def test_sample_failures_are_explicit(self):
        rows = e.read_csv(self.output / 'diagnostics_001/sample_recheck_observations.csv')
        self.assertEqual(sum(r['experiment_id'] == 'T10' and r['observation_status'] == 'decoded' for r in rows), 18)
        failed = [r for r in rows if r['experiment_id'] == '' and r['vehicle_id'] == 'car2']
        self.assertEqual(len(failed), 3)
        self.assertTrue(all(r['observation_status'] == 'failed' and r['detected'] == '0' for r in failed))

    def test_unknown_car2_rotation_does_not_produce_antenna(self):
        rows = e.read_csv(self.output / 'T10_candidate_geometry.csv')
        self.assertEqual(len(rows), 1164)
        for r in rows:
            self.assertEqual(r['metric_reference_valid'], '0')
            if r['vehicle_id'] == 'car2':
                self.assertEqual(r['assumed_body_yaw_rad'], '')
                self.assertEqual(r['antenna_x_m'], '')

    def test_raw_event_readback_preserves_epoch(self):
        j = e.load_json(self.output / 'T10_time_audit.json')
        self.assertEqual(j['raw_records_verified_against_PR49'], 2972)
        self.assertEqual(j['bag_receive_origin_epoch_ns'], '1792925285431466217')
        self.assertIsNone(j['accepted_model'])
        self.assertIsNone(j['total_time_error_bound_s'])
        self.assertAlmostEqual(j['reproduced_PR49_candidate']['candidate_model']['b_relative_s'], -24.954730587166665)


if __name__ == '__main__':
    unittest.main()
