#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Estimate a 2D Tag position from Anchor-to-Tag UWB ranges."""

from __future__ import print_function

import math

import rospy

from geometry_msgs.msg import PoseStamped
from uwb_coop_localization.msg import UwbRangeArray


try:
    string_types = (basestring,)
except NameError:
    string_types = (str,)


def is_finite(value):
    return not math.isnan(value) and not math.isinf(value)


def build_anchor_map(raw_anchors):
    """Validate ROS Anchor parameters and index them by string ID."""
    if not isinstance(raw_anchors, list) or len(raw_anchors) < 3:
        raise ValueError("~anchors must contain at least three Anchors")

    anchor_map = {}

    for index, anchor in enumerate(raw_anchors):
        if not isinstance(anchor, dict):
            raise ValueError(
                "Anchor {} must be a mapping".format(index)
            )

        anchor_id = anchor.get("id")
        if not isinstance(anchor_id, string_types) or not anchor_id:
            raise ValueError(
                "Anchor {} must have a non-empty string id".format(
                    index
                )
            )

        if anchor_id in anchor_map:
            raise ValueError(
                "duplicate Anchor id: {}".format(anchor_id)
            )

        try:
            x = float(anchor["x"])
            y = float(anchor["y"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                "Anchor {} must contain numeric x and y".format(
                    anchor_id
                )
            )

        if not is_finite(x) or not is_finite(y):
            raise ValueError(
                "Anchor {} coordinates must be finite".format(
                    anchor_id
                )
            )

        anchor_map[anchor_id] = (x, y)

    return anchor_map


def collect_measurements(anchor_map, ranges):
    """Return unique, valid measurements for configured Anchors."""
    measurements = {}
    unknown_anchor_ids = []

    for measurement in ranges:
        anchor_id = measurement.anchor_id

        if anchor_id not in anchor_map:
            unknown_anchor_ids.append(anchor_id)
            continue

        measured_range = float(measurement.range)

        if not is_finite(measured_range) or measured_range < 0.0:
            continue

        measurements[anchor_id] = measured_range

    return measurements, unknown_anchor_ids


def solve_2d_position(anchor_map, measurements):
    """Solve the unweighted 2D linear least-squares problem."""
    anchor_ids = sorted(measurements.keys())

    if len(anchor_ids) < 3:
        raise ValueError(
            "at least three configured valid ranges are required"
        )

    reference_id = anchor_ids[0]
    x0, y0 = anchor_map[reference_id]
    r0 = measurements[reference_id]

    ata_00 = 0.0
    ata_01 = 0.0
    ata_11 = 0.0
    atb_0 = 0.0
    atb_1 = 0.0

    for anchor_id in anchor_ids[1:]:
        xi, yi = anchor_map[anchor_id]
        ri = measurements[anchor_id]

        row_0 = 2.0 * (xi - x0)
        row_1 = 2.0 * (yi - y0)
        value = (
            r0 * r0
            - ri * ri
            + xi * xi
            + yi * yi
            - x0 * x0
            - y0 * y0
        )

        ata_00 += row_0 * row_0
        ata_01 += row_0 * row_1
        ata_11 += row_1 * row_1
        atb_0 += row_0 * value
        atb_1 += row_1 * value

    determinant = ata_00 * ata_11 - ata_01 * ata_01

    scale = max(ata_00 * ata_11, 1.0)
    if abs(determinant) <= 1e-12 * scale:
        raise ValueError(
            "Anchor geometry is degenerate for 2D localization"
        )

    x = (
        atb_0 * ata_11
        - ata_01 * atb_1
    ) / determinant

    y = (
        ata_00 * atb_1
        - ata_01 * atb_0
    ) / determinant

    if not is_finite(x) or not is_finite(y):
        raise ValueError("2D solution is not finite")

    return x, y


class UwbLocalizer(object):
    def __init__(self):
        self.input_topic = rospy.get_param(
            "~input_topic",
            "/uwb/tag1/ranges",
        )
        self.output_topic = rospy.get_param(
            "~output_topic",
            "/uwb/tag1/pose",
        )
        self.frame_id = rospy.get_param(
            "~frame_id",
            "uwb_map",
        )
        self.anchor_map = build_anchor_map(
            rospy.get_param("~anchors")
        )

        self.publisher = rospy.Publisher(
            self.output_topic,
            PoseStamped,
            queue_size=10,
        )
        self.subscriber = rospy.Subscriber(
            self.input_topic,
            UwbRangeArray,
            self.handle_ranges,
            queue_size=10,
        )

        rospy.loginfo(
            "Localizing from %s to %s using %d configured Anchors",
            self.input_topic,
            self.output_topic,
            len(self.anchor_map),
        )

    def handle_ranges(self, message):
        measurements, unknown_anchor_ids = collect_measurements(
            self.anchor_map,
            message.ranges,
        )

        if unknown_anchor_ids:
            rospy.logwarn_throttle(
                5.0,
                "Ignoring unconfigured Anchor IDs: %s",
                ", ".join(sorted(set(unknown_anchor_ids))),
            )

        try:
            x, y = solve_2d_position(
                self.anchor_map,
                measurements,
            )
        except ValueError as error:
            rospy.logwarn_throttle(
                5.0,
                "Unable to compute UWB position: %s",
                error,
            )
            return

        pose = PoseStamped()
        pose.header.stamp = message.header.stamp
        pose.header.frame_id = self.frame_id
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        pose.pose.orientation.x = 0.0
        pose.pose.orientation.y = 0.0
        pose.pose.orientation.z = 0.0
        pose.pose.orientation.w = 1.0

        self.publisher.publish(pose)


def main():
    rospy.init_node("uwb_localizer")

    try:
        UwbLocalizer()
    except (KeyError, ValueError) as error:
        rospy.logfatal(
            "Invalid UWB localizer configuration: %s",
            error,
        )
        return 1

    rospy.spin()
    return 0


if __name__ == "__main__":
    main()
