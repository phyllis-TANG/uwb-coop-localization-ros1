"""Generator checks use development seeds only, never formal seeds."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from simulate import EPOCH_NS, SCENARIOS, make_case, write_case


class SyntheticInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {scenario: make_case(7, scenario) for scenario in SCENARIOS}

    def test_integer_time_and_unique_record_identity(self):
        _, events, truth, labels = self.cases["nominal"]
        self.assertEqual(events[0]["receive_epoch_ns"], EPOCH_NS)
        self.assertEqual([e["record_index"] for e in events], list(range(len(events))))
        self.assertEqual(len({e["source_observation_id"] for e in events}), len(events))
        self.assertTrue(all(type(e["header_epoch_ns"]) is int and type(e["receive_epoch_ns"]) is int for e in events))
        self.assertTrue(all(a["receive_epoch_ns"] <= b["receive_epoch_ns"] for a, b in zip(events, events[1:])))
        self.assertLess(events[-1]["receive_epoch_ns"], EPOCH_NS + 65_000_000_000)
        self.assertEqual(len(truth), 65)
        self.assertFalse(labels["clock"]["eof_advanced"])

    def test_truth_and_fault_not_in_events(self):
        for _, events, _, _ in self.cases.values():
            for event in events:
                self.assertFalse({"truth", "fault", "fault_label", "true_pose"} & set(event))
                json.dumps(event, allow_nan=False)

    def test_faults_only_change_declared_measurements(self):
        cfg0, nominal, truth0, _ = self.cases["nominal"]
        for scenario in SCENARIOS[1:]:
            cfg, faulty, truth, _ = self.cases[scenario]
            self.assertEqual(cfg0, cfg)
            self.assertEqual(truth0, truth)
            self.assertEqual(len(nominal), len(faulty))
            changed = 0
            for before, after in zip(nominal, faulty):
                offset = before["header_epoch_ns"] - EPOCH_NS
                active = 24_000_000_000 <= offset < 38_000_000_000
                expected = copy.deepcopy(before["value"])
                if active and before["kind"] == "uwb":
                    car = before["vehicle_id"]
                    if scenario == "peer_bias" and car == "car1":
                        expected["node_0"] += 1.2
                        changed += 1
                    elif scenario == "wall_bias" and car == "car1":
                        expected["node_2"] += 1.2
                        changed += 1
                    elif scenario == "peer_gap":
                        expected.pop("node_0" if car == "car1" else "node_1")
                        changed += 1
                self.assertEqual(expected, after["value"])
                self.assertEqual(before["receive_epoch_ns"], after["receive_epoch_ns"])
            self.assertGreater(changed, 0)

    def test_two_dimensional_motion_and_initial_truth(self):
        config, _, truth, _ = self.cases["nominal"]
        for car in ("car1", "car2"):
            xy = np.array([row["cars"][car]["pose"][:2] for row in truth])
            self.assertEqual(np.linalg.matrix_rank(xy - xy.mean(axis=0)), 2)
            self.assertGreater(np.linalg.norm(np.diff(xy, axis=0), axis=1).min(), 0.001)
            self.assertGreater(np.ptp([row["cars"][car]["pose"][2] for row in truth]), 0.5)
            # Seed7 placements have actual finite uncertainty, not exact truth.
            self.assertNotEqual(config["models"][car]["start_antenna_xyz_m"][:2], truth[1]["cars"][car]["antenna_xyz_m"][:2])

    def test_immutable_files_and_deterministic_gzip(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a", Path(directory) / "b"
            ma = write_case(a, 8, "nominal")
            mb = write_case(b, 8, "nominal")
            self.assertEqual(ma, mb)
            with self.assertRaises(FileExistsError):
                write_case(a, 8, "nominal")
            with gzip.open(a / "events.jsonl.gz", "rt") as stream:
                self.assertEqual(len([json.loads(line) for line in stream]), ma["event_count"])


if __name__ == "__main__":
    unittest.main()
