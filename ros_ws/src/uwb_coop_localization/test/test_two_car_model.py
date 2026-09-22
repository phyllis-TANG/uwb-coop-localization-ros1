#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

import math
import os
import random
import sys
import unittest


SCRIPT_DIRECTORY = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts")
)
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from two_car_model import advance_unicycle
from two_car_model import planar_distance
from two_car_model import Pose2D
from two_car_model import sample_range
from two_car_model import wrap_angle


class TwoCarModelTest(unittest.TestCase):
    def test_planar_distance(self):
        self.assertAlmostEqual(
            5.0,
            planar_distance(Pose2D(0, 0, 0), Pose2D(3, 4, 0)),
        )

    def test_straight_unicycle_step(self):
        pose = advance_unicycle(Pose2D(1, 2, 0), 0.5, 0.0, 2.0)
        self.assertAlmostEqual(2.0, pose.x)
        self.assertAlmostEqual(2.0, pose.y)
        self.assertAlmostEqual(0.0, pose.yaw)

    def test_turning_step_wraps_yaw(self):
        pose = advance_unicycle(
            Pose2D(0, 0, math.pi - 0.1),
            0.0,
            0.2,
            1.0,
        )
        self.assertAlmostEqual(-math.pi + 0.1, pose.yaw)
        self.assertGreaterEqual(pose.yaw, -math.pi)
        self.assertLess(pose.yaw, math.pi)
        self.assertAlmostEqual(pose.yaw, wrap_angle(math.pi + 0.1))

    def test_sample_range_without_noise(self):
        sampled = sample_range(2.0, random.Random(4), bias=0.1)
        self.assertEqual((2.1, 1.0, False), sampled)

    def test_forced_nlos_adds_positive_bias(self):
        sampled = sample_range(
            2.0,
            random.Random(4),
            nlos_probability=1.0,
            nlos_bias=0.4,
        )
        self.assertEqual((2.4, 0.0, True), sampled)

    def test_forced_dropout(self):
        self.assertIsNone(sample_range(
            2.0,
            random.Random(4),
            dropout_probability=1.0,
        ))

    def test_invalid_probability_is_rejected(self):
        with self.assertRaises(ValueError):
            sample_range(
                2.0,
                random.Random(4),
                dropout_probability=1.1,
            )


if __name__ == "__main__":
    unittest.main()
