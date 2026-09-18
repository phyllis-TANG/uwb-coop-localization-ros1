#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Publish ideal UWB ranges for one stationary simulated Tag."""

from __future__ import print_function

import math

import rospy

from uwb_coop_localization.msg import UwbRange
from uwb_coop_localization.msg import UwbRangeArray


def calculate_range(anchor, tag_x, tag_y, tag_z):
    """Return the three-dimensional Euclidean distance in metres."""
    dx = tag_x - float(anchor["x"])
    dy = tag_y - float(anchor["y"])
    dz = tag_z - float(anchor["z"])
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def main():
    rospy.init_node("uwb_simulator")

    anchors = rospy.get_param("~anchors")
    frame_id = rospy.get_param("~frame_id", "uwb_map")
    tag_id = rospy.get_param("~tag_id", "tag1")
    tag_x = float(rospy.get_param("~tag_x", 2.0))
    tag_y = float(rospy.get_param("~tag_y", 2.0))
    tag_z = float(rospy.get_param("~tag_z", 0.0))
    publish_rate = float(rospy.get_param("~publish_rate", 10.0))
    topic = rospy.get_param("~topic", "/uwb/tag1/ranges")

    if not isinstance(anchors, list) or not anchors:
        raise ValueError("~anchors must be a non-empty list")

    publisher = rospy.Publisher(topic, UwbRangeArray, queue_size=10)
    rate = rospy.Rate(publish_rate)

    rospy.loginfo(
        "Publishing %d ideal UWB ranges for %s on %s",
        len(anchors),
        tag_id,
        topic,
    )

    while not rospy.is_shutdown():
        packet = UwbRangeArray()
        packet.header.stamp = rospy.Time.now()
        packet.header.frame_id = frame_id
        packet.tag_id = tag_id

        for anchor in anchors:
            measurement = UwbRange()
            measurement.anchor_id = str(anchor["id"])
            measurement.range = calculate_range(
                anchor,
                tag_x,
                tag_y,
                tag_z,
            )
            measurement.quality = 1.0
            packet.ranges.append(measurement)

        publisher.publish(packet)
        rate.sleep()


if __name__ == "__main__":
    main()
