# Tasks

Task states use `TODO`, `IN PROGRESS`, `BLOCKED`, and `DONE`. A task is marked
`DONE` only after its success criterion has been checked in the target
environment or explicitly confirmed by its operator.

## Stage 0 — environment and repository

- **DONE — Identify the operating system and ROS 1 distribution in the vendor
  virtual machine.**
  - Operator result (2026-09-16): Ubuntu 18.04 with ROS Melodic.
- **DONE — Verify the available Python interpreters in the vendor VM.**
  - Operator result (2026-09-16): Python 2.7.17 and Python 3.6.9.
  - Build result (2026-09-17): catkin selected `/usr/bin/python2`.
- **DONE — Inspect existing ROS workspaces without modifying them.**
  - Operator result (2026-09-16): four Wheeltec workspaces are active overlays;
    five catkin workspace markers exist under `/home/wheeltec-client`.
- **DONE — Create an independent UWB catkin workspace.**
  - Operator result (2026-09-16): `catkin_make -C ros_ws` completed
    successfully and generated the isolated `build` and `devel` spaces.
- **DONE — Create the `uwb_coop_localization` ROS package.**
  - Operator result (2026-09-17): the package was created with `rospy`,
    `std_msgs`, and `geometry_msgs`.
  - Verification: `catkin_make -C ros_ws` completed successfully.
  - Metadata: MIT License, repository URL, description, and maintainer are set.
- **TODO — Add package directories when their first real files are introduced.**

## Stage 1 — simulated UWB data path

- **DONE — Define hardware-independent ROS range messages.**
- **IN PROGRESS — Add configuration-driven `anchors.yaml`.**
- **TODO — Implement and test `uwb_simulator.py`.**
- **TODO — Implement and test `uwb_logger.py`.**
- **TODO — Implement and test simple 2D least-squares trilateration.**
- **TODO — Display anchors, tag, estimate, and trajectory in RViz.**

## Deferred stages

- **TODO — Identify and integrate the real UWB hardware.**
- **TODO — Validate one-car UWB experiments.**
- **TODO — Validate two independently namespaced cars and TF trees.**
- **TODO — Establish an odometry/IMU baseline.**
- **TODO — Implement a centralized 2D EKF only after the data path is stable.**
- **TODO — Evaluate a factor graph only after the EKF baseline is stable.**
