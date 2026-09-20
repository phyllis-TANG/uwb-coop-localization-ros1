#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

import os
import sys
import unittest


SCRIPT_DIRECTORY = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts")
)
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from linktrack_frame3 import decode_frame3
from linktrack_frame3 import Frame3StreamParser


FRAME_HEX = [
    "55 05 1d 00 00 01 27 3b 0d 00 38 3b 0d 00 00 00 00 00 "
    "4b 13 01 00 00 91 02 00 a2 9b 96",
    "55 05 1d 00 00 01 3b 3b 0d 00 4c 3b 0d 00 00 00 00 00 "
    "4b 13 01 00 00 81 02 00 a3 9b af",
    "55 05 1d 00 00 01 4f 3b 0d 00 60 3b 0d 00 00 00 00 00 "
    "4b 13 01 00 00 87 02 00 a2 9a db",
]


def from_hex(value):
    return bytearray(int(item, 16) for item in value.split())


class DecodeFrame3Test(unittest.TestCase):
    def test_decodes_real_field_frame(self):
        frame = decode_frame3(from_hex(FRAME_HEX[0]))

        self.assertEqual(1, frame.node_id)
        self.assertEqual(0x000d3b27, frame.local_time_ms)
        self.assertEqual(0x000d3b38, frame.system_time_ms)
        self.assertAlmostEqual(4.939, frame.voltage_v)
        self.assertEqual(1, len(frame.measurements))

        measurement = frame.measurements[0]
        self.assertEqual(0, measurement.node_id)
        self.assertAlmostEqual(0.657, measurement.distance_m)
        self.assertAlmostEqual(-81.0, measurement.fp_rssi_db)
        self.assertAlmostEqual(-77.5, measurement.rx_rssi_db)

    def test_rejects_bad_checksum(self):
        frame = from_hex(FRAME_HEX[0])
        frame[-1] ^= 0xff
        with self.assertRaises(ValueError):
            decode_frame3(frame)

    def test_decodes_signed_int24_distance(self):
        frame = from_hex(FRAME_HEX[0])
        frame[23:26] = bytearray([0xff, 0xff, 0xff])
        frame[-1] = sum(frame[:-1]) & 0xff

        decoded = decode_frame3(frame)
        self.assertAlmostEqual(-0.001, decoded.measurements[0].distance_m)


class Frame3StreamParserTest(unittest.TestCase):
    def test_accepts_fragmented_input(self):
        parser = Frame3StreamParser()
        raw = from_hex(FRAME_HEX[0])

        self.assertEqual([], parser.feed(raw[:3]))
        self.assertEqual([], parser.feed(raw[3:17]))
        frames = parser.feed(raw[17:])

        self.assertEqual(1, len(frames))
        self.assertEqual(0, len(parser.buffer))

    def test_recovers_after_garbage_and_bad_frame(self):
        parser = Frame3StreamParser()
        bad = from_hex(FRAME_HEX[0])
        bad[-1] ^= 0xff
        good = from_hex(FRAME_HEX[1])

        frames = parser.feed(bytearray([0x00, 0x55, 0x99]) + bad + good)

        self.assertEqual(1, len(frames))
        self.assertAlmostEqual(0.641, frames[0].measurements[0].distance_m)
        self.assertEqual(1, parser.bad_checksums)
        self.assertGreater(parser.discarded_bytes, 0)

    def test_decodes_multiple_frames_from_one_chunk(self):
        parser = Frame3StreamParser()
        raw = bytearray()
        for value in FRAME_HEX:
            raw.extend(from_hex(value))

        frames = parser.feed(raw)

        self.assertEqual(3, len(frames))
        self.assertEqual([0.657, 0.641, 0.647], [
            frame.measurements[0].distance_m for frame in frames
        ])


if __name__ == "__main__":
    unittest.main()
