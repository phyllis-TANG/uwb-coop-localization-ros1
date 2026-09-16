# Tasks

Task states use `TODO`, `IN PROGRESS`, `BLOCKED`, and `DONE`. A task is marked
`DONE` only after its success criterion has been checked in the target
environment or explicitly confirmed by its operator.

## Stage 0 — environment and repository

- **DONE — Identify the operating system and ROS 1 distribution in the vendor
  virtual machine.**
  - Success criterion: `rosversion -d` prints a distribution name and
    `rosversion ros` prints the installed ROS version.
  - Operator report (2026-09-16): Ubuntu 18.04 with ROS Melodic.
  - Evidence still to record: exact output of `rosversion -d` and
    `rosversion ros` from the vendor VM.
- **DONE — Verify the available Python interpreters in the vendor VM.**
  - Success criterion: record the complete outputs of `python --version` and
    `python3 --version` without changing the system interpreter.
  - Operator report (2026-09-16): Python 2.7.17 and Python 3.6.9.
- **DONE — Inspect existing ROS workspaces without modifying them.**
  - Success criterion: record `ROS_PACKAGE_PATH`, `CMAKE_PREFIX_PATH`, the
    current directory, and catkin workspace markers found under the home
    directory.
  - Operator result (2026-09-16): four Wheeltec workspaces are active overlays;
    five catkin workspace markers exist under `/home/wheeltec-client`.
- **IN PROGRESS — Create an independent UWB catkin workspace.**
  - Success criterion: from the repository root, `catkin_make -C ros_ws`
    completes successfully without changing any Wheeltec workspace.
- **TODO — Create the `uwb_coop_localization` ROS package.**
- **TODO — Establish the remaining repository directories.**

## Stage 1 — simulated UWB data path

- **TODO — Define one hardware-independent ROS range message.**
- **TODO — Add configuration-driven `anchors.yaml`.**
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
