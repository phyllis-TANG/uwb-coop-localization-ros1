#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Publish two simulated car odometries and reciprocal UWB ranges."""

from __future__ import division
from __future__ import print_function

import math
import random

import rospy

from nav_msgs.msg import Odometry
from std_msgs.msg import Float64
from uwb_coop_localization.msg import UwbRange
from uwb_coop_localization.msg import UwbRangeArray

from two_car_model import advance_unicycle
from two_car_model import planar_distance
from two_car_model import Pose2D
from two_car_model import sample_range


def get_pose(prefix, default_x, default_y, default_yaw):
    return Pose2D(
        rospy.get_param("~%s_x" % prefix, default_x),
        rospy.get_param("~%s_y" % prefix, default_y),
        rospy.get_param("~%s_yaw" % prefix, default_yaw),
    )


def make_odometry(stamp, frame_id, child_frame_id, pose, linear, angular):
    message = Odometry()
    message.header.stamp = stamp
    message.header.frame_id = frame_id
    message.child_frame_id = child_frame_id
    message.pose.pose.position.x = pose.x
    message.pose.pose.position.y = pose.y
    message.pose.pose.orientation.z = math.sin(0.5 * pose.yaw)
    message.pose.pose.orientation.w = math.cos(0.5 * pose.yaw)
    message.twist.twist.linear.x = linear
    message.twist.twist.angular.z = angular
    return message


def make_range_packet(stamp, frame_id, source_id, target_id, sampled):
    packet = UwbRangeArray()
    packet.header.stamp = stamp
    packet.header.frame_id = frame_id
    packet.tag_id = source_id

    if sampled is not None:
        value, quality, unused_is_nlos = sampled
        measurement = UwbRange()
        measurement.anchor_id = target_id
        measurement.range = value
        measurement.quality = quality
        packet.ranges.append(measurement)

    return packet


def main():
    rospy.init_node("two_car_uwb_simulator")

    frame_id = rospy.get_param("~frame_id", "sim_map")
    car1_id = rospy.get_param("~car1_id", "node_0")
    car2_id = rospy.get_param("~car2_id", "node_1")
    publish_rate = float(rospy.get_param("~publish_rate", 20.0))
    if publish_rate <= 0.0:
        raise ValueError("~publish_rate must be positive")

    car1_pose = get_pose("car1", 0.0, 0.0, 0.0)
    car2_pose = get_pose("car2", 2.0, 0.0, 0.0)
    car1_linear = float(rospy.get_param("~car1_linear_velocity", 0.0))
    car1_angular = float(rospy.get_param("~car1_angular_velocity", 0.0))
    car2_linear = float(rospy.get_param("~car2_linear_velocity", 0.15))
    car2_angular = float(rospy.get_param("~car2_angular_velocity", 0.08))

    noise_stddev = float(rospy.get_param("~range_noise_stddev", 0.03))
    range_bias = float(rospy.get_param("~range_bias", 0.0))
    nlos_probability = float(rospy.get_param("~nlos_probability", 0.0))
    nlos_bias = float(rospy.get_param("~nlos_bias", 0.40))
    dropout_probability = float(
        rospy.get_param("~dropout_probability", 0.0)
    )
    random_seed = int(rospy.get_param("~random_seed", 7))
    bidirectional = bool(rospy.get_param("~bidirectional", True))
    car2_time_offset = float(rospy.get_param("~car2_time_offset_s", 0.0))

    car1_odom_publisher = rospy.Publisher(
        rospy.get_param("~car1_odom_topic", "/car1/odom"),
        Odometry,
        queue_size=20,
    )
    car2_odom_publisher = rospy.Publisher(
        rospy.get_param("~car2_odom_topic", "/car2/odom"),
        Odometry,
        queue_size=20,
    )
    car1_range_publisher = rospy.Publisher(
        rospy.get_param("~car1_range_topic", "/car1/uwb/ranges"),
        UwbRangeArray,
        queue_size=20,
    )
    car2_range_publisher = rospy.Publisher(
        rospy.get_param("~car2_range_topic", "/car2/uwb/ranges"),
        UwbRangeArray,
        queue_size=20,
    )
    truth_publisher = rospy.Publisher(
        rospy.get_param(
            "~truth_range_topic",
            "/simulation/inter_car_range_truth",
        ),
        Float64,
        queue_size=20,
    )

    random_generator = random.Random(random_seed)
    period = 1.0 / publish_rate
    rate = rospy.Rate(publish_rate)

    rospy.loginfo(
        "Two-car UWB simulation: %s <-> %s at %.1f Hz",
        car1_id,
        car2_id,
        publish_rate,
    )

    while not rospy.is_shutdown():
        stamp = rospy.Time.now()
        car2_stamp = stamp + rospy.Duration.from_sec(car2_time_offset)
        true_range = planar_distance(car1_pose, car2_pose)

        car1_odom_publisher.publish(make_odometry(
            stamp,
            frame_id,
            "car1/base_link",
            car1_pose,
            car1_linear,
            car1_angular,
        ))
        car2_odom_publisher.publish(make_odometry(
            car2_stamp,
            frame_id,
            "car2/base_link",
            car2_pose,
            car2_linear,
            car2_angular,
        ))

        car1_sample = sample_range(
            true_range,
            random_generator,
            noise_stddev,
            range_bias,
            nlos_probability,
            nlos_bias,
            dropout_probability,
        )
        car1_range_publisher.publish(make_range_packet(
            stamp,
            "car1/uwb_linktrack",
            car1_id,
            car2_id,
            car1_sample,
        ))

        if bidirectional:
            car2_sample = sample_range(
                true_range,
                random_generator,
                noise_stddev,
                range_bias,
                nlos_probability,
                nlos_bias,
                dropout_probability,
            )
            car2_range_publisher.publish(make_range_packet(
                car2_stamp,
                "car2/uwb_linktrack",
                car2_id,
                car1_id,
                car2_sample,
            ))

        truth_publisher.publish(Float64(data=true_range))
        car1_pose = advance_unicycle(
            car1_pose,
            car1_linear,
            car1_angular,
            period,
        )
        car2_pose = advance_unicycle(
            car2_pose,
            car2_linear,
            car2_angular,
            period,
        )
        rate.sleep()


if __name__ == "__main__":
    main()
