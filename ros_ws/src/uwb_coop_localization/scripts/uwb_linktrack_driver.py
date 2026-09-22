#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Publish LinkTrack Node Frame3 measurements from a read-only serial link."""

from __future__ import print_function

import rospy
import serial

from linktrack_frame3 import Frame3StreamParser
from linktrack_frame3 import read_serial_chunk
from uwb_coop_localization.msg import LinktrackFrame3
from uwb_coop_localization.msg import LinktrackNodeMeasurement
from uwb_coop_localization.msg import UwbRange
from uwb_coop_localization.msg import UwbRangeArray


class LinkTrackDriver(object):
    def __init__(self):
        self.port = rospy.get_param("~port")
        self.baudrate = int(rospy.get_param("~baudrate", 921600))
        self.topic = rospy.get_param("~topic", "/uwb/ranges")
        self.raw_topic = rospy.get_param("~raw_topic", "/uwb/frame3")
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
        self.raw_publisher = rospy.Publisher(
            self.raw_topic,
            LinktrackFrame3,
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
        return read_serial_chunk(self.serial_port, self.read_size)

    def publish_frame(self, frame):
        stamp = rospy.Time.now()
        message = UwbRangeArray()
        message.header.stamp = stamp
        message.header.frame_id = self.frame_id
        message.tag_id = self.node_prefix + str(frame.node_id)

        for node in frame.measurements:
            measurement = UwbRange()
            measurement.anchor_id = self.node_prefix + str(node.node_id)
            measurement.range = node.distance_m
            measurement.quality = float("nan")
            message.ranges.append(measurement)

        self.publisher.publish(message)

        raw_message = LinktrackFrame3()
        raw_message.header.stamp = stamp
        raw_message.header.frame_id = self.frame_id
        raw_message.role = frame.role
        raw_message.node_id = frame.node_id
        raw_message.local_time_ms = frame.local_time_ms
        raw_message.system_time_ms = frame.system_time_ms
        raw_message.voltage_v = frame.voltage_v

        for node in frame.measurements:
            raw_measurement = LinktrackNodeMeasurement()
            raw_measurement.role = node.role
            raw_measurement.node_id = node.node_id
            raw_measurement.distance_m = node.distance_m
            raw_measurement.fp_rssi_db = node.fp_rssi_db
            raw_measurement.rx_rssi_db = node.rx_rssi_db
            raw_message.measurements.append(raw_measurement)

        self.raw_publisher.publish(raw_message)

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
