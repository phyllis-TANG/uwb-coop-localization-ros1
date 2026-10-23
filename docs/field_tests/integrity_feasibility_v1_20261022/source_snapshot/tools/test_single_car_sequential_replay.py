#!/usr/bin/env python3
"""Behavior checks for availability, immutable output and archived solver reuse."""
import copy
import unittest
import numpy as np
from single_car_sequential_replay import Event, SequentialReplay, load_solver, rotation

MODEL = {
    'anchors_xyz_m': {'a': [0., 0., 2.], 'b': [3., 0., 2.], 'c': [0., 3., 2.]},
    'range_bias_m': {'a': 0., 'b': 0., 'c': 0.},
    'start_antenna_xyz_m': [0., 0., .2], 'initial_heading_deg': 0.,
    'base_to_antenna_body_xy_m': [0., 0.], 'antenna_height_m': .2,
    'graph_parameters': {'odom_translation_sigma_m': .03, 'odom_yaw_sigma_deg': 2.,
                         'prior_position_sigma_m': .2, 'prior_heading_sigma_deg': 5.,
                         'range_sigma_m': .2}}
POLICY = {'keyframe_step_s': 1., 'first_keyframe_margin_s': 1.,
          'range_bin_half_width_s': .4, 'minimum_samples_per_link': 5,
          'release_delay_s': 1.}


class SensitiveSolver:
    """Test output intentionally depends on all supplied ranges."""
    @staticmethod
    def align_odom(local, start, heading):
        angle = heading - local[0, 2]
        xy = (local[:, :2] - local[0, :2]) @ rotation(angle).T + start[:2]
        return np.column_stack([xy, local[:, 2] + angle])

    @classmethod
    def optimize_graph(cls, local, observations, anchors, biases, height, start,
                       heading, times, parameters, **kwargs):
        states = cls.align_odom(local, list(start) + [height], heading)
        states[:, 0] += .001 * sum(sum(row.values()) for row in observations)
        return states, {'optimizer_success': True, 'optimizer_nfev': 1}


def synthetic_events(end=8.):
    events = []
    ranges = {key: float(np.linalg.norm(np.asarray(xyz) - [0., 0., .2]))
              for key, xyz in MODEL['anchors_xyz_m'].items()}
    for index in range(int(round(end/.05)) + 1):
        t = index*.05
        events.extend([Event(t+.01, 'odom', t, (0., 0., 0.)),
                       Event(t+.015, 'imu', t, {'gyro': 123.}),
                       Event(t+.02, 'uwb', t, dict(ranges))])
    # This sorting constructs synthetic fixtures; production bags are not sorted.
    return sorted(events, key=lambda e: e.received_s)


def run(events, solver=None):
    replay = SequentialReplay(MODEL, POLICY, solver or SensitiveSolver())
    for event in events:
        replay.ingest(event)
    replay.finish()
    return replay


def stable(rows):
    return [(r['state_time_s'], r['availability_cutoff_s'], r['status'], r['pose'],
             r.get('range_medians_m'), r.get('range_sample_counts')) for r in rows]


class SequentialReplayTests(unittest.TestCase):
    def test_future_mutation_and_truncation_leave_past_outputs_unchanged(self):
        events = synthetic_events()
        complete = run(events).records
        changed = []
        for e in events:
            if e.received_s > 5. and e.kind == 'uwb':
                e = Event(e.received_s, e.kind, e.header_s,
                          {key: value+100. for key, value in e.value.items()})
            changed.append(e)
        mutated = run(changed).records
        before = lambda rows: [r for r in rows if r['availability_cutoff_s'] <= 5.]
        self.assertEqual(stable(before(complete)), stable(before(mutated)))
        self.assertNotEqual(complete[-1]['pose'], mutated[-1]['pose'])
        truncated = [e for e in events if e.received_s <= 5.] + [Event(5., 'clock')]
        self.assertEqual(stable(before(complete)), stable(run(truncated).records))

    def test_published_records_are_not_rewritten_by_smoothing(self):
        replay = SequentialReplay(MODEL, POLICY, SensitiveSolver())
        events = synthetic_events()
        for e in events:
            if e.received_s <= 5.:
                replay.ingest(e)
        old = replay.records
        snapshot = copy.deepcopy(old)
        for e in events:
            if e.received_s > 5.:
                replay.ingest(e)
        replay.finish()
        self.assertEqual(old, snapshot)
        self.assertEqual(stable(old), stable(replay.records[:len(old)]))
        old[0]['pose'][0] = 999.
        self.assertNotEqual(replay.records[0]['pose'][0], 999.)

    def test_missing_future_odom_bracket_is_not_extrapolated(self):
        replay = SequentialReplay(MODEL, POLICY, SensitiveSolver())
        replay.ingest(Event(0., 'odom', 0., (0., 0., 0.)))
        replay.ingest(Event(.01, 'uwb', 0., {'a': 2.}))
        replay.ingest(Event(2.1, 'clock'))
        replay.finish()
        self.assertEqual(replay.records[0]['status'], 'missing_odom_bracket')
        self.assertIsNone(replay.records[0]['pose'])

    def test_equal_deadline_counts_and_late_bin_remains_immutable(self):
        policy = dict(POLICY, minimum_samples_per_link=1)
        replay = SequentialReplay(MODEL, policy, SensitiveSolver())
        for e in [Event(0., 'odom', 0., (0., 0., 0.)),
                  Event(.01, 'uwb', 0., {'a': 2.}),
                  Event(.8, 'uwb', .7, {'a': 2.}),
                  Event(1.9, 'odom', 2., (0., 0., 0.)),
                  Event(2., 'uwb', 1.2, {'a': 4.}), Event(2.1, 'clock')]:
            replay.ingest(e)
        first = replay.records[0]
        self.assertEqual(first['range_sample_counts']['a'], 2)
        self.assertEqual(first['range_medians_m']['a'], 3.)
        replay.ingest(Event(2.4, 'uwb', 1.3, {'a': 100.}))
        replay.finish()
        self.assertEqual(replay.records[0], first)
        self.assertEqual(replay.counters['late_packets_for_closed_bins'], 1)

    def test_imu_values_do_not_enter_fusion(self):
        original = synthetic_events()
        changed = [Event(e.received_s, e.kind, e.header_s, {'gyro': -1e10})
                   if e.kind == 'imu' else e for e in original]
        self.assertEqual(stable(run(original).records), stable(run(changed).records))

    def test_header_and_receipt_disorder_are_explicit_errors(self):
        replay = SequentialReplay(MODEL, POLICY, SensitiveSolver())
        replay.ingest(Event(.1, 'odom', 1., (0., 0., 0.)))
        with self.assertRaisesRegex(ValueError, 'Receipt time'):
            replay.ingest(Event(.05, 'other'))
        with self.assertRaisesRegex(ValueError, 'Nonincreasing'):
            replay.ingest(Event(.2, 'odom', 1., (0., 0., 0.)))

    def test_eof_does_not_create_future_deadlines(self):
        rows = run(synthetic_events(3.5)).records
        self.assertTrue(all(r['availability_cutoff_s'] <= 3.52 for r in rows))
        self.assertEqual([r['state_time_s'] for r in rows], [1., 2.])

    def test_late_bootstrap_skips_past_deadlines(self):
        replay = SequentialReplay(MODEL, POLICY, SensitiveSolver())
        replay.ingest(Event(0., 'odom', -5., (0., 0., 0.)))
        replay.ingest(Event(.1, 'uwb', -5., {'a': 2.}))
        self.assertGreaterEqual(replay.next_state+replay.delay, replay.now)
        self.assertEqual(replay.counters['bootstrap_skipped_deadlines'], 4)

    def test_failed_solver_is_prediction_not_accepted_graph(self):
        class Failed(SensitiveSolver):
            @classmethod
            def optimize_graph(cls, *args, **kwargs):
                states, info = super().optimize_graph(*args, **kwargs)
                info['optimizer_success'] = False
                return states, info
        rows = run(synthetic_events(5.), Failed()).records
        self.assertEqual(rows[-1]['status'], 'predict_only_solver_failed')
        self.assertFalse(rows[-1]['accepted_graph'])
        self.assertEqual(rows[-1]['pose'], [0., 0., 0.])
        self.assertIsNotNone(rows[-1]['candidate_pose'])

    def test_real_archived_solver_matches_identical_input_solve(self):
        solver = load_solver()
        replay = run(synthetic_events(5.), solver)
        expected, info = solver.optimize_graph(
            np.asarray(replay.local), replay.observations, MODEL['anchors_xyz_m'],
            MODEL['range_bias_m'], .2, np.array([0., 0.]), 0., np.asarray(replay.times),
            MODEL['graph_parameters'], tag_to_base_lever_xy_m=np.zeros(2), raise_on_failure=False)
        self.assertTrue(info['optimizer_success'])
        np.testing.assert_allclose(replay.final_graph, expected, atol=1e-12, rtol=0.)
        np.testing.assert_allclose(replay.records[-1]['pose'], [0., 0., 0.], atol=1e-10)


if __name__ == '__main__':
    unittest.main()
