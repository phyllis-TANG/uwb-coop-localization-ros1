#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

import os
import sys
import unittest


SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from analyze_two_car_bag import attach_constant_truth
from analyze_two_car_bag import build_pairs
from analyze_two_car_bag import pair_by_bag_time
from analyze_two_car_bag import summarize_pairs


def record(index, bag_time, header_time, value):
    return {
        "message_index": index,
        "bag_time_s": bag_time,
        "header_time_s": header_time,
        "bag_header_offset_s": bag_time - header_time,
        "range_m": value,
    }


class AnalyzeTwoCarBagTest(unittest.TestCase):
    def test_pairing_is_nearest_and_one_to_one(self):
        left = [record(0, 1.00, 1.00, 2.0),
                record(1, 1.05, 1.05, 2.1)]
        right = [record(0, 1.01, 1.01, 2.0),
                 record(1, 1.049, 1.049, 2.1)]
        self.assertEqual([(0, 0), (1, 1)],
                         pair_by_bag_time(left, right, 0.03))

    def test_pairing_rejects_messages_outside_tolerance(self):
        left = [record(0, 1.00, 1.00, 2.0)]
        right = [record(0, 1.04, 1.04, 2.0)]
        self.assertEqual([], pair_by_bag_time(left, right, 0.03))

    def test_summary_detects_time_offset_dropouts_and_truth_error(self):
        car1 = [record(0, 10.000, 10.000, 2.00),
                record(1, 10.050, 10.050, None),
                record(2, 10.100, 10.100, 2.10)]
        car2 = [record(0, 10.002, 10.052, 2.20),
                record(1, 10.052, 10.102, 2.30),
                record(2, 10.102, 10.152, None)]
        rows = build_pairs(car1, car2, 0.01)
        attach_constant_truth(rows, 2.0)
        summary = summarize_pairs(car1, car2, rows)

        self.assertEqual(3, summary["paired_frames"])
        self.assertEqual(1, summary["both_usable_pairs"])
        self.assertEqual(1, summary["car1_only_usable_pairs"])
        self.assertEqual(1, summary["car2_only_usable_pairs"])
        self.assertAlmostEqual(0.002, summary["bag_time_delta_mean_s"])
        self.assertAlmostEqual(0.052, summary["header_time_delta_mean_s"])
        self.assertAlmostEqual(0.20,
                               summary["reciprocal_abs_difference_mean_m"])
        self.assertAlmostEqual(0.05, summary["car1_truth_bias_m"])
        self.assertAlmostEqual(0.25, summary["car2_truth_bias_m"])
        self.assertAlmostEqual(0.10,
                               summary["reciprocal_mean_truth_bias_m"])

    def test_negative_tolerance_is_rejected(self):
        with self.assertRaises(ValueError):
            pair_by_bag_time([], [], -0.1)


if __name__ == "__main__":
    unittest.main()
