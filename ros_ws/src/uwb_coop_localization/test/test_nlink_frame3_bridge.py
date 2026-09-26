#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

import math
import os
import sys
import unittest


SCRIPT_DIRECTORY = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts")
)
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from nlink_frame3_bridge import frame3_to_range_array
from nlink_frame3_bridge import node_name


class FakeHeader(object):
    def __init__(self, seq=0, stamp=None, frame_id=""):
        self.seq = seq
        self.stamp = stamp
        self.frame_id = frame_id


class FakeNode(object):
    def __init__(self, node_id, distance):
        self.id = node_id
        self.dis = distance


class FakeFrame3(object):
    def __init__(self):
        self.header = FakeHeader(seq=7, stamp=12.5, frame_id="raw_linktrack")
        self.id = 4
        self.nodes = [FakeNode(1, 2.75), FakeNode(9, 4.125)]


class FakeRange(object):
    def __init__(self):
        self.anchor_id = ""
        self.range = 0.0
        self.quality = 0.0


class FakeRangeArray(object):
    def __init__(self):
        self.header = FakeHeader()
        self.tag_id = ""
        self.ranges = []


class NlinkFrame3BridgeTest(unittest.TestCase):
    def test_node_name_uses_prefix_and_numeric_id(self):
        self.assertEqual("node_7", node_name("node_", 7))

    def test_converts_ids_ranges_header_and_unavailable_quality(self):
        source = FakeFrame3()
        output = frame3_to_range_array(
            source,
            FakeRangeArray,
            FakeRange,
            node_prefix="node_",
            frame_id="car2/uwb_linktrack",
        )

        self.assertEqual("node_4", output.tag_id)
        self.assertEqual(7, output.header.seq)
        self.assertEqual(12.5, output.header.stamp)
        self.assertEqual("car2/uwb_linktrack", output.header.frame_id)
        self.assertEqual("raw_linktrack", source.header.frame_id)
        self.assertEqual(2, len(output.ranges))
        self.assertEqual("node_1", output.ranges[0].anchor_id)
        self.assertAlmostEqual(2.75, output.ranges[0].range)
        self.assertTrue(math.isnan(output.ranges[0].quality))
        self.assertEqual("node_9", output.ranges[1].anchor_id)
        self.assertAlmostEqual(4.125, output.ranges[1].range)

    def test_preserves_source_frame_id_when_override_is_empty(self):
        output = frame3_to_range_array(
            FakeFrame3(), FakeRangeArray, FakeRange)

        self.assertEqual("raw_linktrack", output.header.frame_id)


if __name__ == "__main__":
    unittest.main()
