#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Publish UWB Anchor, Tag, estimate, and trajectory visualization topics."""

from __future__ import print_function

from collections import deque

import rospy

from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from visualization_msgs.msg import Marker
from visualization_msgs.msg import MarkerArray


def make_marker(
        frame_id,
        namespace,
        marker_id,
        marker_type,
        x,
        y,
        z,
        scale_x,
        scale_y,
        scale_z,
        red,
        green,
        blue,
        alpha=1.0):
    marker = Marker()
    marker.header.frame_id = frame_id
    marker.header.stamp = rospy.Time.now()
    marker.ns = namespace
    marker.id = marker_id
    marker.type = marker_type
    marker.action = Marker.ADD

    marker.pose.position.x = x
    marker.pose.position.y = y
    marker.pose.position.z = z
    marker.pose.orientation.w = 1.0

    marker.scale.x = scale_x
    marker.scale.y = scale_y
    marker.scale.z = scale_z

    marker.color.r = red
    marker.color.g = green
    marker.color.b = blue
    marker.color.a = alpha

    return marker


class UwbVisualizer(object):
    def __init__(self):
        self.frame_id = rospy.get_param("~frame_id", "uwb_map")
        self.anchors = rospy.get_param("~anchors")

        self.ground_truth_topic = rospy.get_param(
            "~ground_truth_topic",
            "/uwb/tag1/ground_truth_pose",
        )
        self.estimate_topic = rospy.get_param(
            "~estimate_topic",
            "/uwb/tag1/pose",
        )
        self.path_topic = rospy.get_param(
            "~path_topic",
            "/uwb/tag1/path",
        )
        self.max_path_points = int(
            rospy.get_param("~max_path_points", 1000)
        )

        if not isinstance(self.anchors, list) or not self.anchors:
            raise ValueError("~anchors must be a non-empty list")

        if self.max_path_points <= 0:
            raise ValueError("~max_path_points must be greater than zero")

        self.path_poses = deque(maxlen=self.max_path_points)

        self.anchor_publisher = rospy.Publisher(
            "/uwb/anchors/markers",
            MarkerArray,
            queue_size=1,
            latch=True,
        )
        self.ground_truth_marker_publisher = rospy.Publisher(
            "/uwb/tag1/ground_truth_marker",
            Marker,
            queue_size=10,
        )
        self.estimate_marker_publisher = rospy.Publisher(
            "/uwb/tag1/estimate_marker",
            Marker,
            queue_size=10,
        )
        self.path_publisher = rospy.Publisher(
            self.path_topic,
            Path,
            queue_size=10,
        )

        self.ground_truth_subscriber = rospy.Subscriber(
            self.ground_truth_topic,
            PoseStamped,
            self.handle_ground_truth,
            queue_size=10,
        )
        self.estimate_subscriber = rospy.Subscriber(
            self.estimate_topic,
            PoseStamped,
            self.handle_estimate,
            queue_size=10,
        )

        self.publish_anchor_markers()

        rospy.loginfo(
            "Visualizing %d Anchors, ground truth %s, estimate %s, and path %s",
            len(self.anchors),
            self.ground_truth_topic,
            self.estimate_topic,
            self.path_topic,
        )

    def publish_anchor_markers(self):
        marker_array = MarkerArray()

        for index, anchor in enumerate(self.anchors):
            anchor_id = str(anchor["id"])
            x = float(anchor["x"])
            y = float(anchor["y"])
            z = float(anchor["z"])

            sphere = make_marker(
                self.frame_id,
                "uwb_anchors",
                index * 2,
                Marker.SPHERE,
                x,
                y,
                z,
                0.25,
                0.25,
                0.25,
                0.1,
                0.4,
                1.0,
            )
            marker_array.markers.append(sphere)

            label = make_marker(
                self.frame_id,
                "uwb_anchor_labels",
                index * 2 + 1,
                Marker.TEXT_VIEW_FACING,
                x,
                y,
                z + 0.35,
                0.0,
                0.0,
                0.25,
                1.0,
                1.0,
                1.0,
            )
            label.text = anchor_id
            marker_array.markers.append(label)

        self.anchor_publisher.publish(marker_array)

    def handle_ground_truth(self, message):
        marker = make_marker(
            self.frame_id,
            "uwb_ground_truth",
            0,
            Marker.CUBE,
            message.pose.position.x,
            message.pose.position.y,
            message.pose.position.z,
            0.28,
            0.28,
            0.28,
            0.1,
            1.0,
            0.1,
            0.35,
        )
        marker.header.stamp = message.header.stamp
        self.ground_truth_marker_publisher.publish(marker)

    def handle_estimate(self, message):
        marker = make_marker(
            self.frame_id,
            "uwb_estimate",
            0,
            Marker.SPHERE,
            message.pose.position.x,
            message.pose.position.y,
            message.pose.position.z,
            0.20,
            0.20,
            0.20,
            1.0,
            0.1,
            0.1,
        )
        marker.header.stamp = message.header.stamp
        self.estimate_marker_publisher.publish(marker)

        self.path_poses.append(message)

        path = Path()
        path.header.stamp = message.header.stamp
        path.header.frame_id = self.frame_id
        path.poses = list(self.path_poses)
        self.path_publisher.publish(path)


def main():
    rospy.init_node("uwb_visualizer")

    try:
        UwbVisualizer()
    except (KeyError, TypeError, ValueError) as error:
        rospy.logfatal(
            "Invalid UWB visualization configuration: %s",
            error,
        )
        return 1

    rospy.spin()
    return 0


if __name__ == "__main__":
    main()
