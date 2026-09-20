# UWB Cooperative Localization for ROS 1

This repository will contain a modular ROS 1 experiment platform for UWB-assisted
cooperative localization. Development is deliberately incremental: raw data
acquisition and repeatable experiments take priority over advanced fusion
algorithms.

## Current status

The target vendor virtual machine is Ubuntu 18.04 with ROS Melodic. The vendor
VM provides Python 2.7.17 and Python 3.6.9, and the verified catkin build uses
`/usr/bin/python2`. Initial ROS nodes will therefore remain Python 2.7
compatible.

The repository-owned `ros_ws` workspace has been initialized and built without
modifying the existing Wheeltec workspaces. The `uwb_coop_localization` package
has also been created and successfully built with `rospy`, `std_msgs`, and
`geometry_msgs`.

The package uses the MIT License. Hardware-independent `UwbRange` and
`UwbRangeArray` messages have been generated and verified with Python 2.7. A
configuration-driven four-Anchor simulation map and an ideal stationary-Tag
UWB simulator are now available.

The simulator publishes `uwb_coop_localization/UwbRangeArray` on
`/uwb/tag1/ranges`. In the vendor VM it produced the expected four geometric
ranges at a stable rate of approximately 10 Hz.

A Python 2.7-compatible logger now writes each Anchor measurement to CSV using
the columns `timestamp,tag_id,anchor_id,range,quality`. It preserves the ROS
acquisition timestamp, flushes each message batch by default, appends to
existing files without repeating the header, and creates missing output
directories.

A simple unweighted 2D least-squares localizer now converts configured
Anchor-to-Tag ranges into `geometry_msgs/PoseStamped` messages on
`/uwb/tag1/pose`. It was verified with three and four Anchors, invalid-input
filtering, degenerate-geometry rejection, and a live 10 Hz simulator data path.

RViz visualization now displays labeled Anchor markers, simulated Tag ground
truth, the UWB position estimate, and a bounded estimated path in the `uwb_map`
frame. The ideal estimate and simulated truth overlap as expected. No real UWB
driver, filtering, odometry/IMU fusion, or cooperative EKF has been implemented
yet. The next gate is field-test preparation and real UWB hardware
identification.

The continuing LinkTrack P hardware investigation, safety constraints, captured
evidence, and unresolved field-test tasks are maintained in
[`docs/field_test_handoff.md`](docs/field_test_handoff.md). Update that record at
the end of each hardware investigation stage rather than relying on chat history.

A Python 2.7-compatible parser and read-only ROS serial node now support the
field-verified LinkTrack `Node_Frame3` stream. They have hardware-independent
tests using real captured frames, but have not yet been built or run against ROS
on the target VM. See [`docs/linktrack_driver.md`](docs/linktrack_driver.md) for
the required port selection, current limitations, and staged vehicle checks.

## Development order

1. Verify the ROS 1 virtual-machine environment.
2. Verify Python and inspect existing catkin workspaces.
3. Create an independent UWB catkin workspace and ROS package.
4. Define a hardware-independent UWB range message.
5. Add a UWB simulator using configuration-driven anchor coordinates.
6. Add raw range logging.
7. Add simple 2D least-squares trilateration.
8. Add RViz visualization.

EKF and factor-graph work are intentionally deferred until the basic data path
has been validated with repeatable experiments.
