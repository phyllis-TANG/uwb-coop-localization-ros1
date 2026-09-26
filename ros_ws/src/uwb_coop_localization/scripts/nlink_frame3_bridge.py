#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

import copy


def node_name(node_prefix, node_id):
    """Return the stable string identifier used by UwbRangeArray."""
    return "%s%d" % (node_prefix, int(node_id))


def frame3_to_range_array(frame, array_class, range_class,
                          node_prefix="node_", frame_id=""):
    """Convert nlink_parser/LinktrackNodeframe3 to UwbRangeArray.

    The class arguments keep this conversion independently testable without a
    running ROS installation or generated message modules.
    """
    output = array_class()
    output.header = copy.deepcopy(frame.header)
    if frame_id:
        output.header.frame_id = frame_id
    output.tag_id = node_name(node_prefix, frame.id)

    for node in frame.nodes:
        measurement = range_class()
        measurement.anchor_id = node_name(node_prefix, node.id)
        measurement.range = float(node.dis)
        measurement.quality = float("nan")
        output.ranges.append(measurement)

    return output


def main():
    import rospy
    from nlink_parser.msg import LinktrackNodeframe3
    from uwb_coop_localization.msg import UwbRange
    from uwb_coop_localization.msg import UwbRangeArray

    rospy.init_node("nlink_frame3_bridge")

    input_topic = rospy.get_param(
        "~input_topic", "nlink_linktrack_nodeframe3")
    output_topic = rospy.get_param("~output_topic", "uwb/ranges")
    node_prefix = rospy.get_param("~node_prefix", "node_")
    frame_id = rospy.get_param("~frame_id", "")
    queue_size = int(rospy.get_param("~queue_size", 200))

    publisher = rospy.Publisher(
        output_topic, UwbRangeArray, queue_size=queue_size)

    def callback(frame):
        publisher.publish(frame3_to_range_array(
            frame,
            UwbRangeArray,
            UwbRange,
            node_prefix=node_prefix,
            frame_id=frame_id,
        ))

    rospy.Subscriber(
        input_topic,
        LinktrackNodeframe3,
        callback,
        queue_size=queue_size,
    )
    rospy.loginfo(
        "Bridging %s to %s with node prefix %s",
        input_topic,
        output_topic,
        node_prefix,
    )
    rospy.spin()


if __name__ == "__main__":
    main()
