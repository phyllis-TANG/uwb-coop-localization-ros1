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
- **DONE — Add configuration-driven `anchors.yaml`.**
  - Verified four unique simulation Anchors in the `uwb_map` frame.
  - Coordinates remain simulation-only until the field layout is surveyed.
- **DONE — Implement and test `uwb_simulator.py`.**
  - Verified Python 2.7 syntax and executable permission.
  - Verified `catkin_make`, launch parameter loading, and node startup.
  - Verified four ideal ranges for Tag position `(2.0, 2.0, 0.0)`.
  - Verified `/uwb/tag1/ranges` at approximately 10 Hz.
- **DONE — Implement and test `uwb_logger.py`.**
  - Verified Python 2.7 syntax, launch configuration, and catkin integration.
  - Verified the CSV header and five-column row format.
  - Verified 8,383 initial packets and 33,532 measurement rows.
  - Verified append mode added complete four-Anchor packets without repeating
    the CSV header.
  - Verified flush and clean file closure during ROS shutdown.
- **DONE — Implement and test simple 2D least-squares trilateration.**
  - Verified exact `(2.0, 2.0)` solutions with three and four Anchors.
  - Verified filtering of unknown Anchor IDs and invalid negative ranges.
  - Verified rejection of fewer than three ranges and collinear Anchor layouts.
  - Verified live `PoseStamped` output in `uwb_map` at approximately 10 Hz.
  - Orientation remains an unobserved default unit quaternion, not a UWB yaw
    estimate.
- **DONE — Display anchors, tag, estimate, and trajectory in RViz.**
  - Verified eight Anchor sphere/label markers in `uwb_map`.
  - Verified simulated ground truth and UWB estimate markers at `(2.0, 2.0)`.
  - Verified a bounded `nav_msgs/Path` with at most 1,000 poses.
  - Verified the saved RViz configuration and combined demo launch.
  - Ground truth is explicitly simulation-only and must not be claimed in
    real experiments without an independent reference system.

## Deferred stages

- **DONE — Identify and integrate the real UWB hardware.**
  - Field result (2026-09-19): two handheld LinkTrack nodes established a real
    `DR_MODE0` ranging link after their backed-up configurations were aligned.
  - Offline implementation: added a Python 2.7-compatible `Node_Frame3` stream
    parser and read-only ROS serial node with real-frame unit tests.
  - Field verification (2026-09-20): Python 2.7 tests and catkin build passed;
    the live ROS topic reported N1-to-N0 ranges at 50.004 Hz with 14--26 ms
    inter-message intervals after removing serial timeout batching.
  - Vehicle integration (2026-09-20): onboard `cdc_acm` exposed P-B as the
    stable path `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B2E110223-if00`;
    the read-only driver opened it after the `wheeltec` user joined `dialout`.
- **IN PROGRESS — Validate one-car UWB experiments.**
  - **DONE — EXP001 Car1 static LOS acquisition.** Vehicle-mounted P-B
    published real N1-to-N0 ranges at approximately 50 Hz through the remote
    vehicle ROS Master; the VMware client recorded 7,039 `/uwb/ranges`
    messages over approximately 2 min 20 s. The rosbag remains local and the
    experiment record is stored under `docs/field_tests/`.
  - Next experiment: `EXP002_car1_static_human_NLOS`, changing only human-body
    LOS obstruction while keeping both nodes and the vehicle stationary.
- **TODO — Validate two independently namespaced cars and TF trees.**
- **TODO — Establish an odometry/IMU baseline.**
- **TODO — Implement a centralized 2D EKF only after the data path is stable.**
- **TODO — Evaluate a factor graph only after the EKF baseline is stable.**
