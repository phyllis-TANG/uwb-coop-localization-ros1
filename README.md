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
`UwbRangeArray` messages have been generated and verified with Python 2.7.
No real UWB driver, simulator, logger, localizer, or fusion algorithm has been
implemented yet. The next gate is a configuration-driven Anchor map followed
by the UWB simulator.

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
