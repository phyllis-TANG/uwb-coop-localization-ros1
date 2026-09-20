#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Publish LinkTrack Node Frame3 measurements from a read-only serial link."""

from __future__ import print_function

import rospy
import serial

from linktrack_frame3 import Frame3StreamParser
from uwb_coop_localization.msg import UwbRange
from uwb_coop_localization.msg import UwbRangeArray


class LinkTrackDriver(object):
    def __init__(self):
        self.port = rospy.get_param("~port")
        self.baudrate = int(rospy.get_param("~baudrate", 921600))
        self.topic = rospy.get_param("~topic", "/uwb/ranges")
        self.frame_id = rospy.get_param("~frame_id", "uwb_linktrack")
        self.node_prefix = rospy.get_param("~node_prefix", "node_")
        self.read_size = int(rospy.get_param("~read_size", 4096))
        self.timeout = float(rospy.get_param("~timeout", 0.1))
        self.reconnect_delay = float(
            rospy.get_param("~reconnect_delay", 1.0)
        )

        if not self.port:
            raise ValueError("~port must name a serial device")
        if self.baudrate <= 0:
            raise ValueError("~baudrate must be positive")
        if self.read_size <= 0:
            raise ValueError("~read_size must be positive")
        if self.timeout <= 0.0:
            raise ValueError("~timeout must be positive")
        if self.reconnect_delay <= 0.0:
            raise ValueError("~reconnect_delay must be positive")

        self.publisher = rospy.Publisher(
            self.topic,
            UwbRangeArray,
            queue_size=100,
        )
        self.parser = Frame3StreamParser()
        self.serial_port = None

        rospy.on_shutdown(self.close)
        rospy.loginfo(
            "Reading LinkTrack Frame3 data from %s at %d baud onto %s",
            self.port,
            self.baudrate,
            self.topic,
        )

    def open(self):
        self.serial_port = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
        )
        rospy.loginfo("Opened LinkTrack serial port: %s", self.port)

    def close(self):
        if self.serial_port is not None and self.serial_port.isOpen():
            self.serial_port.close()
            rospy.loginfo("Closed LinkTrack serial port: %s", self.port)

    def read_chunk(self):
        """Wait for one byte, then drain only bytes already buffered.

        Asking pyserial for the full configured read size with a timeout makes
        it wait for that size or the timeout.  At 50 Hz this groups several
        complete frames into a burst and gives them nearly identical ROS
        timestamps.  Waiting for one byte preserves the reconnect-friendly
        timeout while draining the immediately available remainder keeps
        latency low.
        """
        data = self.serial_port.read(1)
        if not data or self.read_size == 1:
            return data

        waiting = self.serial_port.inWaiting()
        if waiting > 0:
            data += self.serial_port.read(min(waiting, self.read_size - 1))
        return data

    def publish_frame(self, frame):
        message = UwbRangeArray()
        message.header.stamp = rospy.Time.now()
        message.header.frame_id = self.frame_id
        message.tag_id = self.node_prefix + str(frame.node_id)

        for node in frame.measurements:
            measurement = UwbRange()
            measurement.anchor_id = self.node_prefix + str(node.node_id)
            measurement.range = node.distance_m
            measurement.quality = float("nan")
            message.ranges.append(measurement)

        self.publisher.publish(message)

    def run(self):
        while not rospy.is_shutdown():
            try:
                if self.serial_port is None or not self.serial_port.isOpen():
                    self.open()

                data = self.read_chunk()
                for frame in self.parser.feed(data):
                    self.publish_frame(frame)
            except (OSError, serial.SerialException) as error:
                rospy.logerr_throttle(
                    5.0,
                    "LinkTrack serial error on %s: %s",
                    self.port,
                    error,
                )
                self.close()
                self.serial_port = None
                rospy.sleep(self.reconnect_delay)


def main():
    rospy.init_node("uwb_linktrack_driver")

    try:
        driver = LinkTrackDriver()
    except (KeyError, TypeError, ValueError) as error:
        rospy.logfatal("Invalid LinkTrack driver configuration: %s", error)
        return 1

    driver.run()
    return 0


if __name__ == "__main__":
    main()
