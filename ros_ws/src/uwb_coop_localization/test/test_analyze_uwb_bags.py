#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

import math
import os
import sys
import unittest


SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from analyze_uwb_bags import extract_target_range
from analyze_uwb_bags import percentile
from analyze_uwb_bags import summarize_records


class Object(object):
    pass


def record(index, value, offset=57902871.0):
    return {
        "message_index": index,
        "bag_time_s": 100.0 + index * 0.02,
        "elapsed_bag_time_s": index * 0.02,
        "header_time_s": 100.0 + index * 0.02 - offset,
        "bag_header_offset_s": offset,
        "range_m": value,
    }


class AnalyzeUwbBagsTest(unittest.TestCase):
    def test_percentile_uses_linear_interpolation(self):
        self.assertAlmostEqual(2.5, percentile([1.0, 2.0, 3.0, 4.0], 50))
        self.assertAlmostEqual(3.85, percentile([1.0, 2.0, 3.0, 4.0], 95))

    def test_summary_retains_missing_frames_and_uses_population_std(self):
        summary = summarize_records([
            record(0, 1.0), record(1, None), record(2, 2.0), record(3, 4.0)])
        self.assertEqual(4, summary["frames"])
        self.assertEqual(1, summary["no_usable_target"])
        self.assertEqual(3, summary["usable_target_frames"])
        self.assertAlmostEqual(7.0 / 3.0, summary["mean_m"])
        expected_std = math.sqrt(((1 - 7.0 / 3) ** 2 +
                                  (2 - 7.0 / 3) ** 2 +
                                  (4 - 7.0 / 3) ** 2) / 3)
        self.assertAlmostEqual(expected_std, summary["std_m"])
        self.assertAlmostEqual(50.0, summary["frequency_hz"])
        self.assertEqual("adjacent_valid_target_measurements",
                         summary["jump_definition"])
        self.assertEqual(2, summary["jump_count"])
        self.assertEqual(2.0, summary["jump_max_m"])
        self.assertAlmostEqual(57902871.0,
                               summary["bag_header_offset_mean_s"])

    def test_target_extraction_ignores_nan_quality(self):
        message = Object()
        message.tag_id = "node_1"
        target = Object()
        target.anchor_id = "node_0"
        target.range = 1.25
        target.quality = float("nan")
        message.ranges = [target]
        self.assertEqual(1.25, extract_target_range(message, "node_1", "node_0"))

    def test_target_extraction_rejects_missing_or_nonfinite_range(self):
        message = Object()
        message.tag_id = "node_1"
        message.ranges = []
        self.assertIsNone(extract_target_range(message, "node_1", "node_0"))
        target = Object()
        target.anchor_id = "node_0"
        target.range = float("nan")
        message.ranges = [target]
        self.assertIsNone(extract_target_range(message, "node_1", "node_0"))


if __name__ == "__main__":
    unittest.main()
