# UWB Cooperative Localization for ROS 1

This repository will contain a modular ROS 1 experiment platform for UWB-assisted
cooperative localization. Development is deliberately incremental: raw data
acquisition and repeatable experiments take priority over advanced fusion
algorithms.

## Current status

The target vendor virtual machine has been identified by its operator as Ubuntu
18.04 with ROS Melodic. The separate development container used to maintain this
repository does **not** contain ROS 1, so ROS runtime results must be collected
in the vendor VM rather than inferred from this container.

The vendor VM provides Python 2.7.17 and Python 3.6.9. Because ROS Melodic
commonly uses Python 2, the first ROS nodes will remain Python 2.7 compatible
until the active ROS Python interpreter is verified. No system interpreter will
be replaced or reconfigured.

The vendor environment currently overlays four Wheeltec workspaces before ROS
Melodic. Those workspaces must remain untouched. Before initializing `ros_ws`,
the repository has now been cloned into the vendor VM from
`phyllis-TANG/uwb-coop-localization-ros1`. The verified checkout is the clean
`main` branch at commit `e770d1e`. The first empty build of the repository-owned
`ros_ws` created the expected `build`, `devel`, and `src` directories without
touching the Wheeltec workspaces. Package creation is the next gate.

## Development order

1. Verify the ROS 1 virtual-machine environment.
2. Verify Python and inspect existing catkin workspaces.
3. Create an independent UWB catkin workspace and ROS package.
4. Add a UWB simulator using configuration-driven anchor coordinates.
5. Add raw range logging.
6. Add simple 2D least-squares trilateration.
7. Add RViz visualization.

EKF and factor-graph work are intentionally deferred until the basic data path
has been validated with repeatable experiments.
