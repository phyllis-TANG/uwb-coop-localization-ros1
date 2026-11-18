"""Regression tests for the seed-101 survey reference and causal sensor selection."""
import copy
import gzip
import json
import os
from pathlib import Path
import unittest

import numpy as np

import example
import recompute


class SurveyReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime = os.environ.get('HCPL_RUNTIME_DIR')
        def read(name):
            return example.source_bytes(runtime, example.RUNTIME_SHA, example.RUNTIME_DIR, name)
        cls.cfg = json.loads(read('geometry.json'))
        cls.events = list(map(json.loads, gzip.decompress(read('events.jsonl.gz')).splitlines()))
        cls.packets = example.select_packets(cls.events, cls.cfg, example.TARGET)
        archive = (Path(__file__).resolve().parents[3] / 'docs/research'
                   / 'midterm_dual_robot_contract_a/ground_hcpl/epoch10.json')
        cls.archive = json.loads(archive.read_text())

    def solve(self, packets, prior=None):
        return example.estimate(packets, self.cfg['models'],
                                self.cfg['prior_state_s'] if prior is None else prior)

    def test_archive_replays_from_sensor_only_input(self):
        self.assertEqual(self.packets, self.archive['packets'])
        replay = self.solve(self.packets)
        for step, archived in zip(replay['history'], self.archive['history']):
            np.testing.assert_allclose(step['posterior'], archived['posterior'], rtol=0, atol=1e-12)
            np.testing.assert_allclose(step['posterior_cov'], archived['posterior_cov'], rtol=0, atol=1e-12)

    def test_first_update_is_range_only_at_the_survey(self):
        packet = copy.deepcopy(self.packets[0])
        packet['odom'] = [[230., -3., 2.], [-19., 24., -.9]]
        result = self.solve([packet])
        step = result['history'][0]
        xy = np.concatenate([self.cfg['models'][c]['start_antenna_xyz_m'][:2] for c in example.CARS])
        np.testing.assert_array_equal(step['u'], np.zeros(4))
        np.testing.assert_array_equal(step['prior'], np.r_[xy, np.zeros(9)])
        np.testing.assert_array_equal(step['prior_cov'], np.diag([.2**2] * 4 + [.3**2] * 9))
        np.testing.assert_allclose(step['posterior'], self.archive['history'][0]['posterior'], rtol=0, atol=1e-12)
        next_step = self.archive['history'][1]
        np.testing.assert_allclose(next_step['prior_cov'], step['posterior_cov'] + example.Q, rtol=0, atol=1e-12)
        with self.assertRaises(ValueError):
            self.solve(self.packets[1:])

    def test_turn_in_place_rotates_the_antenna_about_the_base(self):
        model = dict(initial_heading_deg=0., base_to_antenna_body_xy_m=[.2, .1])
        start = [3., 9., .7]
        turned = [3., 9., .7 + np.pi/2]
        np.testing.assert_allclose(example.antenna_offset(turned, start, model), [-.3, .1], atol=1e-15)
        translated = [3. + np.cos(.7), 9. + np.sin(.7), .7]
        np.testing.assert_allclose(example.antenna_offset(translated, start, model), [1., 0.], atol=1e-15)

    def test_odom_map_rotation_translation_invariance(self):
        packets = copy.deepcopy(self.packets)
        for packet in packets:
            for i, angle in enumerate((.9, -.7)):
                pose = packet['odom'][i]
                pose[:2] = (example.rotation(angle) @ pose[:2] + np.array([3., -8.])).tolist()
                pose[2] += angle
        result = self.solve(packets)
        for step, expected in zip(result['history'], self.archive['history']):
            np.testing.assert_allclose(step['u'], expected['u'], rtol=0, atol=1e-12)
            np.testing.assert_allclose(step['posterior'], expected['posterior'], rtol=0, atol=1e-12)

    def test_clock_origin_shift_preserves_states_and_input_ages(self):
        shift_s = 7
        shifted = [dict(e, header_epoch_ns=e['header_epoch_ns'] + shift_s * example.NS,
                        receive_epoch_ns=e['receive_epoch_ns'] + shift_s * example.NS) for e in self.events]
        cfg = dict(self.cfg, prior_state_s=self.cfg['prior_state_s'] + shift_s)
        packets = example.select_packets(shifted, cfg, example.TARGET + shift_s)
        output = self.solve(packets, cfg['prior_state_s'])
        for got, expected in zip(output['history'], self.archive['history']):
            self.assertEqual(got['t'], expected['t'] + shift_s)
            self.assertAlmostEqual(got['inputs_ready_s'] - got['t'], expected['inputs_ready_s'] - expected['t'])
            np.testing.assert_allclose(got['posterior'], expected['posterior'], rtol=0, atol=1e-12)
        epoch_shift = 100 * example.NS
        reepoch = [dict(e, header_epoch_ns=e['header_epoch_ns'] + epoch_shift,
                        receive_epoch_ns=e['receive_epoch_ns'] + epoch_shift) for e in self.events]
        self.assertEqual(self.packets, example.select_packets(
            reepoch, dict(self.cfg, epoch_ns=self.cfg['epoch_ns'] + epoch_shift), example.TARGET))

    def test_prefix_and_late_or_missing_frames(self):
        limit = 4
        last = self.cfg['epoch_ns'] + (limit + 1) * example.NS
        prefix = [e for e in self.events if e['receive_epoch_ns'] <= last]
        self.assertEqual(self.packets[:limit], example.select_packets(prefix, self.cfg, limit))
        filtered = self.solve(self.packets[:limit])
        for step, expected in zip(filtered['history'], self.archive['history']):
            np.testing.assert_allclose(step['posterior'], expected['posterior'], rtol=0, atol=1e-12)
        frame_id = self.packets[limit - 1]['range_ids'][0]
        changed = [e if e['source_observation_id'] != frame_id else dict(e, receive_epoch_ns=last + 1)
                   for e in self.events]
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            example.select_packets(sorted(changed, key=lambda e: e['receive_epoch_ns']), self.cfg, example.TARGET)
        without = [e for e in self.events if e['source_observation_id'] != self.packets[0]['odom_ids'][0]]
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            example.select_packets(without, self.cfg, example.TARGET)

    def test_independent_batch_checks_both_vehicles_and_every_prefix(self):
        result = recompute.recompute(self.archive)
        self.assertEqual([v['t'] for v in result['prefixes']], [p['t'] for p in self.packets])
        self.assertEqual([v['car'] for v in result['cars']], [1, 2])
        # A sub-tolerance perturbation of an archived point may pass the comparison,
        # but cannot affect any SVD-derived result (the archive is comparison-only).
        perturbed = copy.deepcopy(self.archive)
        perturbed['history'][0]['prior'][0] += 5e-13
        self.assertEqual(result, recompute.recompute(perturbed))
        archive = copy.deepcopy(self.archive)
        archive['history'][0]['prior_cov'][0][0] += example.Q[0, 0]
        with self.assertRaisesRegex(AssertionError, 'prediction covariance'):
            recompute.recompute(archive)
        archive = copy.deepcopy(self.archive)
        archive['cars'][1]['variants']['eq13_to_16']['HCPL'] += .001
        with self.assertRaisesRegex(AssertionError, 'HCPL'):
            recompute.recompute(archive)


if __name__ == '__main__':
    unittest.main()
