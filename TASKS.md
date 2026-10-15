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
- **DONE — Validate initial one-car UWB ranging experiments.**
  - **DONE — EXP001 Car1 static LOS acquisition.** Vehicle-mounted P-B
    published real N1-to-N0 ranges at approximately 50 Hz through the remote
    vehicle ROS Master; the VMware client recorded 7,039 `/uwb/ranges`
    messages over approximately 2 min 20 s. The rosbag remains local and the
    experiment record is stored under `docs/field_tests/`.
  - **DONE — EXP002 static human NLOS, EXP003 manual-push LOS, and EXP004
    manual-push human NLOS.** Reports preserve raw spikes and distinguish
    usable-target message percentage from accuracy or radio packet delivery.
  - Offline analysis exports raw CSV, summary CSV/JSON/text, SHA256, and PNG
    using bag reception time. Final field acceptance passed on the retained
    bags without committing them to Git.
- **DONE — Validate initial static ranging between two cars.**
  - See the September 27 field summary and archived analysis artifacts.
- **DONE — Prepare the two-car field session off-site.**
  - Added a namespaced two-car simulator with configurable range noise,
    positive NLOS bias, dropouts, and timestamp offset.
  - Preserved LinkTrack Frame3 device time, voltage, FP RSSI, and RX RSSI on a
    diagnostic topic without changing the existing range topic.
  - Defined EXP005--008 truth, recording, evidence, and stop criteria.
  - Added an EXP005 runbook with per-host read-only snapshots, serial and topic
    checks, shared/separate ROS Master recording templates, and immediate bag
    verification commands.
  - Target Melodic VM validation (2026-09-23): all 19 Python 2 unit tests
    passed, the catkin message build reached 100%, and both simulated UWB
    streams held approximately 20 Hz.
  - A clean 11.3 s smoke bag contained 1,138 messages and produced 228/228
    usable Car1 target ranges. A 14.5 s stress bag detected the injected
    behavior: 17.18%/23.79% missing Car1/Car2 target ranges, an approximately
    -49.3 ms Car2 bag/header offset, and 33.50%/35.50% jumps above 0.25 m.
  - Live two-car `/uwb/frame3` publication and EXP005--008 remain field-test
    acceptance items; they are not implied by the completed simulator work.
- **DONE — Add reproducible two-car rosbag comparison.**
  - Pair reciprocal Car1/Car2 UWB messages by bag reception time without
    silently correcting timestamps or filtering ranges.
  - Report bilateral range differences, dropout combinations, header-time
    differences, and optional simulation or tape-measure truth errors.
  - Keep odometry-derived distance out of this stage until a shared coordinate
    frame and initial relative pose have been demonstrated.
  - Target Melodic VM validation (2026-09-24): all 24 Python 2 unit tests and
    the catkin build passed. The saved smoke bag produced 227 pairs with zero
    header-time offset and a 0.0213 m reciprocal-mean truth RMSE.
  - The saved stress bag produced 290 pairs, detected the injected 50 ms Car2
    header offset, retained 61.38% both-usable pairs under independent
    dropouts, and increased reciprocal absolute difference P95 from 0.0885 m
    to 0.4407 m under NLOS injection. The generated plot passed visual review.
- **TODO — Record both cars' UWB, odom, IMU, and tf streams.**
- **TODO — Quantify and handle inter-computer/ROS time synchronization.**
- **TODO — Validate two independently namespaced cars and TF trees.**
- **TODO — Establish an odometry/IMU baseline.**
- **TODO — Implement a centralized 2D EKF only after the data path is stable.**
- **TODO — Establish a controlled EKF-versus-graph comparison.**
  - The October offline graph pilot below precedes this comparison; it does
    not establish online EKF or cooperative-system acceptance.

## October field archive and offline single-car pilots

- **DONE — Audit and archive the October 10–11 session.**
  - All 28 bags / 126,830 messages were read offline; 11 previously reported
    hashes match. Preserve all bag hashes, source notes, four original scripts,
    corrected P5 reference, failed attempts, and calibration provenance.
- **DONE — Establish a short Car2 powered-motion Odom baseline.**
  - Two approximately 1 m forward runs and a return run have endpoint references.
    The return length is inferred from prior measurements rather than measured
    independently. Manual pushing is retained as diagnostic data.
- **DONE — Preserve and reproduce the 1D filtering/graph pilots.**
  - Six historical summaries reproduced to their reported precision; IMU is
    diagnostic and the graph is full-history reoptimization, not iSAM2.
- **DONE — Run an offline fixed-height 2D UWB/Odom graph on two L-shaped bags.**
  - Modern Python validation on uploaded original bags; endpoint-only manual
    references, three active surveyed nodes, no endpoint factors or fitting.
    Fusion does not outperform Odom on both runs. No real-time or cooperative
    accuracy acceptance is implied.
- **DONE — Accept the new offline program on the target Melodic VM.**
  - On 2026-10-15, Python 2 self-test and all seven new unit tests passed;
    28 original bags passed configured SHA/calibration checks. Both real L
    results and guarded-start/tail diagnostics reproduced. This is offline
    acceptance, not catkin-node, hardware, or online-fusion acceptance.
- **TODO — Survey the tag-to-base lever arm and verify room/Odom alignment.**
- **TODO — Restore/verify N8 visibility and quantify manual reference uncertainty.**
- **TODO — Check stable post-stop motion/angle and resolve battery reliability.**
- **TODO — Validate online fusion and independent timing before two-car fusion.**

Details: `docs/field_tests/20261010_11/README.md`.
