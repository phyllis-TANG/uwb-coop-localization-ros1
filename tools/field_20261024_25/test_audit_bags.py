"""Meaningful parser/integrity failure cases; no ROS runtime required."""
import contextlib
import hashlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import audit_bags
import bag_decoder


def encode_fields(items):
    result = b""
    for name, value in items:
        raw = name.encode() + b"=" + value
        result += struct.pack("<I", len(raw)) + raw
    return result


def record(items, data):
    header = encode_fields(items)
    return struct.pack("<I", len(header)) + header + struct.pack("<I", len(data)) + data


def tiny_bag(compression=b"none"):
    identity = struct.pack("<I", 0)
    connection = record([("op", b"\x07"), ("conn", identity), ("topic", b"/test")],
                        encode_fields([("type", b"std_msgs/String"),
                                       ("md5sum", b"992ce8a1687cec8c8bd883ec73ca41d1"),
                                       ("message_definition", b"string data\n"),
                                       ("callerid", b"/fixture")]))
    messages = b"".join(record([("op", b"\x02"), ("conn", identity),
                                 ("time", struct.pack("<II", 10, n))],
                                struct.pack("<I", len(text)) + text)
                        for n, text in [(100, b"hello"), (200, b"world")])
    chunk = record([("op", b"\x05"), ("compression", compression),
                    ("size", struct.pack("<I", len(messages)))], messages)
    return b"#ROSBAG V2.0\n" + connection + chunk


def frame3_json():
    packet = bytearray(29)
    packet[:2] = b"\x55\x05"
    struct.pack_into("<H", packet, 2, len(packet))
    packet[4], packet[5], packet[20] = 0, 1, 1
    struct.pack_into("<II", packet, 6, 1000, 2000)
    struct.pack_into("<H", packet, 18, 5000)
    packet[21], packet[22] = 0, 2
    packet[23:26] = (1234).to_bytes(3, "little", signed=True)
    packet[26], packet[27] = 160, 150
    packet[-1] = sum(packet[:-1]) & 255
    return {"schema": "linktrack_frame3_raw_v1", "packet_hex": packet.hex(),
            "role": 0, "node_id": 1, "local_time_ms": 1000, "system_time_ms": 2000,
            "voltage_v": 5.0, "nodes": [{"role": 0, "node_id": 2, "distance_m": 1.234,
                                          "fp_rssi_db": -80., "rx_rssi_db": -75.}]}


class BagParsingTests(unittest.TestCase):
    def test_tiny_bag_schema_and_every_message_byte(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.bag"
            path.write_bytes(tiny_bag())
            connections, messages = bag_decoder.load_bag(path)
        decoder = bag_decoder.Decoder(connections[0]["type"], connections[0]["definition"])
        self.assertEqual([decoder.decode(raw, "std_msgs/String") for _, _, raw in messages],
                         [{"data": "hello"}, {"data": "world"}])
        self.assertEqual(messages[1][1] - messages[0][1], 100)

    def test_truncated_record_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "truncated.bag"
            path.write_bytes(tiny_bag()[:-1])
            with self.assertRaisesRegex(bag_decoder.BagError, "truncated record data"):
                bag_decoder.load_bag(path)

    def test_compressed_chunk_fails_with_clear_message(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "compressed.bag"
            path.write_bytes(tiny_bag(b"lz4"))
            with self.assertRaisesRegex(bag_decoder.BagError, "unsupported ROS1 chunk compression: lz4"):
                bag_decoder.load_bag(path)

    def test_message_length_and_extra_bytes_are_checked(self):
        decoder = bag_decoder.Decoder("std_msgs/String", "string data\n")
        with self.assertRaisesRegex(bag_decoder.BagError, "truncated ROS string"):
            decoder.decode(struct.pack("<I", 10) + b"abc", "std_msgs/String")
        with self.assertRaisesRegex(bag_decoder.BagError, "extra message bytes"):
            decoder.decode(struct.pack("<I", 1) + b"ab", "std_msgs/String")


class PacketAndContinuityTests(unittest.TestCase):
    def test_packet_checksum_and_decoded_json_consistency(self):
        frame = frame3_json()
        self.assertEqual(audit_bags.validate_frame3(json.dumps(frame))["nodes"][0]["distance_m"], 1.234)
        broken = dict(frame)
        packet = bytearray.fromhex(frame["packet_hex"])
        packet[23] ^= 1
        broken["packet_hex"] = packet.hex()
        with self.assertRaisesRegex(bag_decoder.BagError, "checksum"):
            audit_bags.validate_frame3(json.dumps(broken))
        frame["nodes"][0]["distance_m"] = 9.
        with self.assertRaisesRegex(bag_decoder.BagError, "distance mismatch"):
            audit_bags.validate_frame3(json.dumps(frame))

    def test_discontinuities_remain_visible(self):
        timing = audit_bags.intervals([0, 20_000_000, 20_000_000, 10_000_000, 1_100_000_000])
        self.assertEqual(timing["duplicates"], 1)
        self.assertEqual(timing["backwards"], 1)
        self.assertEqual(timing["gaps_over_1s"], 1)


class InputGuardTests(unittest.TestCase):
    def test_all_hashes_checked_before_any_decode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extracted = root / "data/extracted/bags"
            extracted.mkdir(parents=True)
            blob = tiny_bag()
            (extracted / "one.bag").write_bytes(blob)
            (extracted / "two.bag").write_bytes(blob)
            manifest = {"formal_bags": [
                {"id": "T08", "relative_path": "one.bag", "sha256": hashlib.sha256(blob).hexdigest(), "expected_messages": 2},
                {"id": "T09", "relative_path": "two.bag", "sha256": "0" * 64, "expected_messages": 2}]}
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            with mock.patch.object(audit_bags, "audit") as parse, contextlib.redirect_stderr(io.StringIO()):
                code = audit_bags.main(["--data-root", str(root / "data"), "--manifest", str(manifest_path),
                                        "--output", str(root / "out")])
            self.assertEqual(code, 2)
            parse.assert_not_called()
            self.assertFalse((root / "out").exists())

    def test_refuse_traversal_manifest_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(bag_decoder.BagError, "unsafe manifest bag relative_path"):
                audit_bags.input_plan(Path(temporary), {"formal_bags": [
                    {"id": "T08", "relative_path": "../outside.bag", "sha256": "0" * 64}]})

    def test_refuse_symlink_escape_using_python38_path_api(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extracted = root / "data/extracted/bags"
            extracted.mkdir(parents=True)
            outside = root / "outside.bag"
            outside.write_bytes(tiny_bag())
            (extracted / "escape.bag").symlink_to(outside)
            with self.assertRaisesRegex(bag_decoder.BagError, "bag path escapes data-root"):
                audit_bags.input_plan(root / "data", {"formal_bags": [
                    {"id": "T08", "relative_path": "escape.bag", "sha256": "0" * 64}]})

    def test_existing_output_is_preserved_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sentinel = root / "bag_qc.json"
            sentinel.write_text("keep existing result")
            with contextlib.redirect_stderr(io.StringIO()):
                code = audit_bags.main(["--data-root", "missing", "--output", str(root)])
            self.assertEqual(code, 2)
            self.assertEqual(sentinel.read_text(), "keep existing result")


if __name__ == "__main__":
    unittest.main()
