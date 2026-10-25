"""Contract behavior: exact time, invalid entries, identity and pairing isolation."""
import csv
import contextlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

import bag_decoder
import normalize


EPOCH = 1792925285431466217


def header(t=EPOCH, seq=7):
    return {"seq": seq, "stamp": {"secs": t // 10**9, "nsecs": t % 10**9},
            "frame_id": "car2/uwb"}


def raw(t=EPOCH, nodes=None):
    return {"header": header(t), "id": 0, "local_time": 2**32 - 1,
            "system_time": 2**32 - 2, "nodes": nodes if nodes is not None else [
                {"id": 1, "dis": 1.25, "fp_rssi": -80., "rx_rssi": -75.}]}


def bridge(t=EPOCH, value=1.25, tag="node_0"):
    return {"header": header(t), "tag_id": tag,
            "ranges": [{"anchor_id": "node_1", "range": value, "quality": float("nan")} ]}


class ContractTests(unittest.TestCase):
    def test_pairing_keeps_sources_without_double_counting(self):
        rows = [(4, EPOCH + 1, "/car2/nlink_linktrack_nodeframe3", raw()),
                (5, EPOCH + 2, "/car2/uwb/ranges", bridge())]
        tables, diag = normalize.convert(rows, "T08", "a" * 64, EPOCH)
        entries = tables["ranges"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(sum(r["primary_observation"] for r in entries), 1)
        self.assertEqual(entries[0]["bridge_frame_id"], entries[1]["bridge_frame_id"])
        self.assertEqual(entries[1]["pairing_status"], "paired_equal")
        self.assertEqual(entries[0]["device_local_time_ms"], 2**32 - 1)
        self.assertEqual(entries[1]["device_local_time_ms"], None)
        self.assertEqual(entries[1]["quality"], None)
        self.assertEqual(entries[1]["quality_status"], "nonfinite_unknown")
        self.assertEqual(entries[0]["header_epoch_ns"], EPOCH)
        self.assertEqual(entries[0]["canonical_time_s"], 1e-9)
        self.assertEqual(entries[0]["link_kind"], "peer")

    def test_cross_car_same_stamp_is_not_a_pair(self):
        c1 = bridge(tag="node_1")
        c1["ranges"][0]["anchor_id"] = "node_0"
        tables, _ = normalize.convert([(0, EPOCH, "/car2/nlink_linktrack_nodeframe3", raw()),
                                      (1, EPOCH, "/car1/uwb/ranges", c1)], "T08", "a", EPOCH)
        self.assertEqual([r["pairing_status"] for r in tables["ranges"]], ["raw_only", "bridge_only"])

    def test_duplicate_stamp_is_ambiguous_and_not_silently_paired(self):
        rows = [(i, EPOCH+i, "/car2/nlink_linktrack_nodeframe3", raw()) for i in (0, 1)]
        rows.append((2, EPOCH+2, "/car2/uwb/ranges", bridge()))
        tables, _ = normalize.convert(rows, "T08", "a", EPOCH)
        self.assertTrue(all(r["pairing_status"] == "ambiguous_header" for r in tables["ranges"]))

    def test_invalid_ranges_empty_frames_missing_peer_remain_visible(self):
        rows = [(0, EPOCH, "/car2/nlink_linktrack_nodeframe3", raw(nodes=[])),
                (1, EPOCH+1, "/car2/uwb/ranges", bridge(value=float("nan"))),
                (2, EPOCH+2, "/car2/uwb/ranges", bridge(EPOCH+2, value=-.2))]
        tables, _ = normalize.convert(rows, "T08", "a", EPOCH)
        self.assertEqual(len(tables["frames"]), 3)
        self.assertEqual(tables["frames"][0]["entry_count"], 0)
        self.assertIn("node_1", tables["frames"][0]["missing_target_ids"])
        self.assertFalse(tables["ranges"][0]["valid"])
        self.assertIsNone(tables["ranges"][0]["range_m"])
        self.assertEqual(tables["ranges"][1]["range_m"], -.2)

    def test_mismatched_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            normalize.convert([(0,EPOCH,"/car2/uwb/ranges",bridge(tag="node_1"))], "T08", "a", EPOCH)

    def test_pair_mismatch_flagged_not_repaired(self):
        tables, _ = normalize.convert([(0,EPOCH,"/car2/nlink_linktrack_nodeframe3",raw()),
            (1,EPOCH,"/car2/uwb/ranges",bridge(value=2.))], "T08", "a", EPOCH)
        self.assertEqual([r["pairing_status"] for r in tables["ranges"]], ["paired_mismatch"]*2)
        self.assertEqual([r["range_m"] for r in tables["ranges"]], [1.25,2.])

    def test_csv_epoch_and_null_roundtrip(self):
        tables, _ = normalize.convert([(0,EPOCH,"/car2/uwb/ranges",bridge())], "T08", "a", EPOCH)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"ranges.csv"
            normalize.write_table(p, tables["ranges"], normalize.COLUMNS["ranges"])
            with p.open() as stream:
                r = next(csv.DictReader(stream))
        self.assertEqual(int(r["receive_epoch_ns"]), EPOCH)
        self.assertEqual(r["quality"], "")

    def test_device_wrap_reset_and_signed_values(self):
        d = normalize.device_diagnostics([2**32-10, 10, 5], 32)
        self.assertEqual(d["possible_wraps"], 1)
        self.assertEqual(d["reset_or_reorder_candidates"], 1)
        self.assertEqual(d["raw_delta_ms"]["min"], 20-2**32)
        with self.assertRaisesRegex(ValueError,"unsigned"):
            normalize.unsigned(-1,32)
        self.assertEqual(normalize.unsigned(2**63+3,64),2**63+3)

    def test_negative_header_delta_does_not_adjust_any_clock(self):
        tables, diag = normalize.convert([(0,EPOCH-3,"/car2/uwb/ranges",bridge())],"T08","a",EPOCH-5)
        d = diag["topics"]["/car2/uwb/ranges"]
        self.assertEqual(d["receive_minus_header_ns"]["min"],-3)
        self.assertEqual(d["negative_receive_minus_header_count"],1)
        self.assertEqual(tables["ranges"][0]["header_epoch_ns"], EPOCH)
        self.assertEqual(tables["ranges"][0]["canonical_time_s"],2e-9)

    def test_truncated_and_extra_payload_rejected_before_export(self):
        d = bag_decoder.Decoder("test/Time", "uint64 local_time\n")
        with self.assertRaisesRegex(ValueError,"truncated"):
            d.decode(struct.pack("<I",7), "test/Time")
        with self.assertRaisesRegex(ValueError,"extra message"):
            d.decode(struct.pack("<QQ",7,8), "test/Time")

    def test_existing_output_is_never_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"out"
            p.mkdir()
            (p/"keep").write_text("sentinel")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(normalize.main(["--data-root",tmp,"--output",str(p)]),2)
            self.assertEqual((p/"keep").read_text(),"sentinel")

    def test_odom_z_covariance_and_command_header_semantics(self):
        vector={"x":0.,"y":0.,"z":0.}
        pose={"position":dict(vector,z=-3.2),"orientation":dict(vector,w=1.)}
        twist={"linear":vector,"angular":vector}
        m={"header":header(),"child_frame_id":"car2/base_footprint",
           "pose":{"pose":pose,"covariance":[float("nan")]+[0.]*35},
           "twist":{"twist":twist,"covariance":[0.]*36}}
        tables,_=normalize.convert([(0,EPOCH,"/car2/odom",m),
                                   (1,EPOCH+1,"/car2/cmd_vel",twist)],"T08","a",EPOCH)
        od=tables["odom"][0]
        self.assertEqual(od["position_z"],-3.2)
        self.assertEqual(od["position_z_semantics"],"driver_yaw_related_not_height")
        self.assertIsNone(od["pose_covariance"][0])
        self.assertIn("pose_covariance",od["nonfinite_fields"])
        self.assertIsNone(tables["commands"][0]["header_epoch_ns"])
        self.assertIsNone(tables["commands"][0]["frame_id"])

    def test_imu_preserves_all_three_covariances(self):
        m={"header":header(),"orientation":{"x":0.,"y":0.,"z":0.,"w":1.},
           "angular_velocity":{"x":0.,"y":0.,"z":0.},
           "linear_acceleration":{"x":0.,"y":0.,"z":9.8}}
        for k in ("orientation","angular_velocity","linear_acceleration"):
            m[k+"_covariance"]=[float(i) for i in range(9)]
        tables,_=normalize.convert([(0,EPOCH,"/car2/imu",m)],"T08","a",EPOCH)
        for k in ("orientation","angular_velocity","linear_acceleration"):
            self.assertEqual(tables["imu"][0][k+"_covariance"],m[k+"_covariance"])


if __name__ == "__main__":
    unittest.main()
