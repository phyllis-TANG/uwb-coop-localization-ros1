import copy
import json
from pathlib import Path
import unittest

import numpy as np

from engine import Estimator, antenna, wall_distance
from evaluate import recovery, metrics, summarize
from protocol import Admission, CARS, TAGS, Gate, WALLS
from simulate import _row, generate

HERE = Path(__file__).resolve().parent


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((HERE/"frozen_config.json").read_text())
        self.geo = json.loads((HERE.parent/"synthetic_comparison_config.json").read_text())
        self.initial = {"car1": np.array([1., 1., .2]), "car2": np.array([3., 2., -.3])}
        self.odom = np.array([self.initial[c] for c in CARS])

    def peer(self, idx=0, car="car1", sample=0, receive=0, value=2.):
        return _row(idx, car, TAGS[CARS[1-CARS.index(car)]], sample, receive, value)

    def walls(self, poses, stamp):
        return [_row(i*10+j, car, w, stamp, stamp, wall_distance(poses[i], car, w, self.geo))
                for i, car in enumerate(CARS) for j, w in enumerate(sorted(WALLS))]

    def test_future_arrival_is_not_read(self):
        with self.assertRaisesRegex(ValueError, "not arrived"):
            Admission(self.config).take(0, [self.peer(receive=1)])

    def test_future_sample_and_old_sample_rejected(self):
        a = Admission(self.config)
        a.take(400000000, [self.peer(sample=1, receive=0), self.peer(idx=1)])
        self.assertEqual(a.counts["future_sample"], 1)
        self.assertEqual(a.counts["stale_sample"], 1)

    def test_unknown_clock_blocks_observation(self):
        a = Admission(self.config)
        a.take(0, [dict(self.peer(), clock_mapping_id="bag_arrival_only")])
        self.assertEqual(a.counts["unvalidated_measurement_clock"], 1)

    def test_identity_and_self_peer_rejected(self):
        a = Admission(self.config)
        a.take(0, [dict(self.peer(), tag_id="node_0"), dict(self.peer(idx=1), target_id="node_1")])
        self.assertEqual(a.counts["identity"], 1)
        self.assertEqual(a.counts["target_identity"], 1)

    def test_duplicate_and_bridge_never_count_twice(self):
        a = Admission(self.config)
        row = self.peer()
        _, peers, _ = a.take(0, [row, row, dict(self.peer(idx=1), source="bridge")])
        self.assertEqual(len(peers), 1)
        self.assertEqual(a.counts["duplicate"], 1)
        self.assertEqual(a.counts["not_primary_valid_raw"], 1)

    def test_reciprocal_late_is_not_second_factor(self):
        a = Admission(self.config)
        a.take(0, [self.peer()])
        _, peers, _ = a.take(10000000, [self.peer(idx=1, car="car2", receive=10000000)])
        self.assertEqual(peers, [])
        self.assertEqual(a.counts["correlated_late_suppressed"], 1)

    def test_direction_priority_is_fixed_and_alternates(self):
        a = Admission(self.config)
        for k in range(2):
            stamp = k*self.config["dt_ns"]
            _, peers, _ = a.take(stamp, [self.peer(idx=k*2, sample=stamp, receive=stamp),
                                            self.peer(idx=k*2+1, car="car2", sample=stamp, receive=stamp)])
            self.assertEqual(peers[0]["vehicle_id"], CARS[k])

    def test_integer_monotonic_cutoff(self):
        a = Admission(self.config)
        a.take(10, [])
        for stamp in [9, 10.]:
            with self.assertRaises(ValueError):
                a.take(stamp, [])

    def test_finite_positive_ranges_only(self):
        a = Admission(self.config)
        a.take(0, [self.peer(idx=i, value=v) for i, v in enumerate([float("nan"), float("inf"), -1., 0.])])
        self.assertEqual(a.counts["invalid_range"], 4)

    def test_quarantine_requires_good_observations_to_reopen(self):
        g = Gate(self.config)
        for _ in range(3):
            self.assertFalse(g.admit("car1", 10.))
        for _ in range(3):
            self.assertFalse(g.admit("car1", 0.))
        self.assertTrue(g.admit("car1", 0.))
        self.assertFalse(g.state["car2"]["closed"])

    def test_missing_observations_predict_without_failure(self):
        m = Estimator("fixed", self.config, self.geo, self.initial)
        m.step(0, self.odom, [])
        after = self.odom.copy()
        after[:, :2] += [.1, -.02]
        x, d = m.step(200000000, after, [])
        np.testing.assert_allclose(x, after[:, :2], atol=1e-12)
        self.assertTrue(d["solver_success"])
        self.assertEqual(d["healthy"], [False, False])

    def test_independent_peer_invariance(self):
        xs = []
        for value in [1., 100.]:
            m = Estimator("independent", self.config, self.geo, self.initial)
            x, _ = m.step(0, self.odom, self.walls(self.odom, 0)+[self.peer(idx=100, value=value)])
            xs.append(x)
        np.testing.assert_array_equal(*xs)

    def test_independent_vehicle_isolation(self):
        xs = []
        for error in [0., 10.]:
            rows = self.walls(self.odom, 0)
            rows = [dict(r, range_m=r["range_m"]+error) if r["vehicle_id"] == "car2" else r for r in rows]
            x, _ = Estimator("independent", self.config, self.geo, self.initial).step(0, self.odom, rows)
            xs.append(x[0])
        np.testing.assert_array_equal(*xs)

    def test_async_transport_noiseless_constant_velocity(self):
        m = Estimator("fixed", self.config, self.geo, self.initial)
        m.step(0, self.odom, [])
        now = self.odom.copy()
        now[:, :2] += [[.08, .02], [-.02, .04]]
        mid = (self.odom+now)/2
        rows = self.walls(mid, 100000000)
        rows = [dict(r, receive_ns=150000000) for r in rows]
        distance = np.linalg.norm(antenna(mid[0], "car1", self.geo)-antenna(mid[1], "car2", self.geo))
        rows.append(self.peer(idx=100, sample=100000000, receive=160000000, value=distance))
        x, _ = m.step(200000000, now, rows)
        np.testing.assert_allclose(x, now[:, :2], atol=1e-10)

    def test_joint_preserves_cross_vehicle_covariance(self):
        m = Estimator("fixed", self.config, self.geo, self.initial)
        m.step(0, self.odom, [self.peer()])
        self.assertGreater(np.linalg.norm(m.cov[:2, 2:]), 1e-6)

    def test_huber_limits_single_spike_compared_with_fixed(self):
        shifts = []
        for method in ["fixed", "huber"]:
            m = Estimator(method, self.config, self.geo, self.initial)
            x, _ = m.step(0, self.odom, self.walls(self.odom, 0)+[self.peer(idx=100, value=8.)])
            shifts.append(np.linalg.norm(x-self.odom[:, :2]))
        self.assertLess(shifts[1], shifts[0])

    def test_firewall_bound_and_shadow_invariance_under_repeated_peer(self):
        models = {method: Estimator(method, self.config, self.geo, self.initial) for method in ["independent", "firewall"]}
        for tick in range(30):
            stamp = tick*200000000
            rows = [dict(r, record_index=r["record_index"]+tick*1000) for r in self.walls(self.odom, stamp)]
            rows += [self.peer(idx=tick*1000+100, sample=stamp, receive=stamp, value=2.6)]
            values = {name: model.step(stamp, self.odom, rows) for name, model in models.items()}
            shadow = models["firewall"].shadow
            np.testing.assert_allclose(shadow, values["independent"][0], atol=1e-13)
            shifts = np.linalg.norm(values["firewall"][0]-values["independent"][0], axis=1)
            self.assertTrue(np.all(shifts <= self.config["healthy_shift_cap_m"]+1e-12))

    def test_same_budget_every_method(self):
        counts = []
        for method in self.config["methods"]:
            model = Estimator(method, self.config, self.geo, self.initial)
            model.step(0, self.odom, [self.peer()])
            counts.append(model.linear_solves)
        self.assertEqual(counts, [16]*5)

    def test_online_configuration_has_no_truth_fault_or_seed(self):
        model = Estimator("firewall", self.config, self.geo, self.initial)
        for key in ["fault_start_s", "fault_end_s", "validation_seeds", "scenarios", "development", "validation"]:
            self.assertNotIn(key, model.config)

    def test_deterministic_generation_and_disjoint_seeds(self):
        a, ta = generate(self.config, self.geo, "development", "peer_bias", "car1", 11)
        b, tb = generate(self.config, self.geo, "development", "peer_bias", "car1", 11)
        self.assertEqual(a["events"], b["events"])
        np.testing.assert_array_equal(a["odom"], b["odom"])
        np.testing.assert_array_equal(ta, tb)
        self.assertFalse(set(self.config["development_seeds"]) & set(self.config["validation_seeds"]))

    def test_future_stream_extension_does_not_change_prefix(self):
        public, _ = generate(self.config, self.geo, "development", "async_delay", "car1", 11)
        cut = 10*200000000
        streams = [public["events"], [r for r in public["events"] if r["receive_ns"] <= cut]]
        xs = []
        for events in streams:
            model = Estimator("firewall", self.config, self.geo, public["initial"])
            for k in range(11):
                now = k*200000000
                previous = (k-1)*200000000
                arrived = [r for r in events if previous < r["receive_ns"] <= now]
                x, _ = model.step(now, public["odom"][k], arrived)
            xs.append(x)
        np.testing.assert_array_equal(*xs)

    def test_recovery_requires_full_dwell_and_reports_censoring(self):
        t = np.arange(10.)
        self.assertEqual(recovery(t, np.zeros(10), np.zeros(10), 3., .03, 2.), 0.)
        self.assertIsNone(recovery(t, np.ones(10), np.zeros(10), 3., .03, 2.))
        errors = np.ones(10)
        errors[7:] = 0
        self.assertEqual(recovery(t, errors, np.zeros(10), 3., .03, 2.), 4.)

    def test_summary_strict_json_and_all_seed_blocks_retained(self):
        times = np.array([0., 12., 30., 48.])
        truth = np.zeros((4, 2, 3))
        estimates = {m: np.zeros((4, 2, 2)) for m in self.config["methods"]}
        diagnostics = {m: [{"solver_success": True} for _ in range(4)] for m in estimates}
        rows = []
        for source in CARS:
            rows += metrics(self.config, "fixture", "normal", source, 11, times, truth, estimates, diagnostics)
        result = summarize(rows, self.config)
        json.dumps(result, allow_nan=False)
        self.assertTrue(all(p["seed_blocks"] == 1 for p in result["paired"]))

    def test_geometry_fault_is_removed_and_truth_not_changed(self):
        a, truth_a = generate(self.config, self.geo, "development", "geometry_degenerate", "car1", 11)
        b, truth_b = generate(self.config, self.geo, "development", "normal", "car1", 11)
        np.testing.assert_array_equal(truth_a, truth_b)
        for tick, expected in [(10, 4), (100, 2), (200, 4)]:
            stamp = tick*self.config["dt_ns"]-20000000
            walls = [r for r in a["events"] if r["vehicle_id"] == "car1" and r["sample_ns"] == stamp and r["target_id"] in WALLS]
            self.assertEqual(len(walls), expected)


if __name__ == "__main__":
    unittest.main()
