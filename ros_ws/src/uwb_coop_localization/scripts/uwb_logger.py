#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Log UwbRangeArray messages to a row-oriented CSV file."""

from __future__ import print_function

import csv
import os

import rospy

from uwb_coop_localization.msg import UwbRangeArray


CSV_HEADER = [
    "timestamp",
    "tag_id",
    "anchor_id",
    "range",
    "quality",
]


def format_stamp(stamp):
    """Format ROS time without losing its nanosecond field."""
    return "{}.{:09d}".format(stamp.secs, stamp.nsecs)


def create_parent_directory(path):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        try:
            os.makedirs(parent)
        except OSError:
            if not os.path.isdir(parent):
                raise


class UwbLogger(object):
    def __init__(self):
        self.input_topic = rospy.get_param(
            "~input_topic",
            "/uwb/tag1/ranges",
        )
        configured_path = rospy.get_param(
            "~output_file",
            "~/.ros/uwb_logs/uwb_ranges.csv",
        )
        self.output_path = os.path.abspath(
            os.path.expanduser(configured_path)
        )
        self.flush_each_message = rospy.get_param(
            "~flush_each_message",
            True,
        )

        create_parent_directory(self.output_path)

        file_exists = os.path.isfile(self.output_path)
        file_is_empty = (not file_exists) or os.path.getsize(
            self.output_path
        ) == 0

        # Python 2's csv module expects a binary file to avoid blank rows.
        self.output_file = open(self.output_path, "ab")
        self.writer = csv.writer(self.output_file)

        if file_is_empty:
            self.writer.writerow(CSV_HEADER)
            self.output_file.flush()

        self.subscriber = rospy.Subscriber(
            self.input_topic,
            UwbRangeArray,
            self.handle_ranges,
            queue_size=100,
        )
        rospy.on_shutdown(self.close)

        rospy.loginfo(
            "Logging UWB ranges from %s to %s",
            self.input_topic,
            self.output_path,
        )

    def handle_ranges(self, message):
        timestamp = format_stamp(message.header.stamp)

        for measurement in message.ranges:
            self.writer.writerow(
                [
                    timestamp,
                    message.tag_id,
                    measurement.anchor_id,
                    "{:.12g}".format(measurement.range),
                    "{:.9g}".format(measurement.quality),
                ]
            )

        if self.flush_each_message:
            self.output_file.flush()

    def close(self):
        if not self.output_file.closed:
            self.output_file.flush()
            self.output_file.close()
            rospy.loginfo(
                "Closed UWB CSV log: %s",
                self.output_path,
            )


def main():
    rospy.init_node("uwb_logger")

    try:
        UwbLogger()
    except (IOError, OSError) as error:
        rospy.logfatal("Unable to open UWB CSV log: %s", error)
        return 1

    rospy.spin()
    return 0


if __name__ == "__main__":
    main()
