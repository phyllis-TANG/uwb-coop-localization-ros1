#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Publish an Isaac Lab Moon_1 replay through the existing ROS 1 UWB topics."""

from __future__ import division

import csv

import rospy
from std_msgs.msg import Float64
from uwb_coop_localization.msg import UwbRangeArray
from nav_msgs.msg import Odometry

from two_car_model import Pose2D
from two_car_uwb_simulator import make_odometry, make_range_packet


def sampled(row, prefix):
    value = row[prefix + "_range_m"]
    if value == "":
        return None
    quality = float(row[prefix + "_quality"])
    return float(value), quality, quality == 0.0


def publish_odom(publisher, stamp, row, prefix, frame_id):
    pose = Pose2D(row[prefix + "_x"], row[prefix + "_y"], row[prefix + "_yaw"])
    message = make_odometry(stamp, frame_id, prefix + "/uwb_antenna", pose, 0.0, 0.0)
    message.pose.pose.position.z = float(row[prefix + "_z"])
    publisher.publish(message)


def main():
    rospy.init_node("replay_moon1_uwb")
    path = rospy.get_param("~replay_csv")
    frame_id = rospy.get_param("~frame_id", "moon_map")
    car1_id = rospy.get_param("~car1_id", "node_0")
    car2_id = rospy.get_param("~car2_id", "node_1")
    loop = bool(rospy.get_param("~loop", False))
    car2_offset = float(rospy.get_param("~car2_time_offset_s", 0.0))
    odom1 = rospy.Publisher("/car1/odom", Odometry, queue_size=20)
    odom2 = rospy.Publisher("/car2/odom", Odometry, queue_size=20)
    range1 = rospy.Publisher("/car1/uwb/ranges", UwbRangeArray, queue_size=20)
    range2 = rospy.Publisher("/car2/uwb/ranges", UwbRangeArray, queue_size=20)
    truth = rospy.Publisher("/simulation/inter_car_range_truth", Float64, queue_size=20)
    while not rospy.is_shutdown():
        with open(path, "r") as stream:
            rows = csv.DictReader(stream)
            previous = None
            for row in rows:
                if rospy.is_shutdown():
                    return
                current = float(row["time_s"])
                if previous is not None:
                    rospy.sleep(max(0.0, current - previous))
                previous = current
                stamp = rospy.Time.now()
                second_stamp = stamp + rospy.Duration.from_sec(car2_offset)
                publish_odom(odom1, stamp, row, "car1", frame_id)
                publish_odom(odom2, second_stamp, row, "car2", frame_id)
                range1.publish(make_range_packet(stamp, "car1/uwb_linktrack", car1_id,
                                                car2_id, sampled(row, "car1")))
                range2.publish(make_range_packet(second_stamp, "car2/uwb_linktrack", car2_id,
                                                car1_id, sampled(row, "car2")))
                truth.publish(Float64(data=float(row["true_range_m"])))
        if not loop:
            break
    rospy.loginfo("Moon_1 replay complete: %s", path)


if __name__ == "__main__":
    main()
