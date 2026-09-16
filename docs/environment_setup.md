# ROS 1 environment check

Run these checks in the robot-vendor Ubuntu virtual machine, not in an arbitrary
development container. They are read-only and do not alter the vendor's ROS
installation.

## Confirmed target environment

The operator reported the following target environment on 2026-09-16:

- Ubuntu 18.04
- ROS Melodic

This is a report about the vendor VM, not a ROS runtime result from the
repository's development container. The exact outputs of `rosversion -d` and
`rosversion ros` should still be retained with the experiment notes when they
are available.

## Step 1: identify the ROS distribution

Open a terminal and run:

```bash
rosversion -d
```

This asks the active ROS environment for its distribution name (for example,
`melodic` or `noetic`). The success criterion is one distribution name with no
error message.

Then run:

```bash
rosversion ros
```

This prints the installed ROS core version. Save both command outputs exactly;
do not install or upgrade ROS in response to an error.

If `rosversion` is not found, inspect the installed distributions without
changing the environment:

```bash
find /opt/ros -mindepth 1 -maxdepth 1 -type d -printf '%f\n'
```

This lists distribution directories under `/opt/ros`. If it prints a directory
such as `noetic`, open a fresh terminal that sources the vendor setup, or source
the matching setup file only after confirming that it is the intended vendor
environment. Report the output before continuing.

## Result in the current development container

Checked on 2026-09-16:

```text
ROS_DISTRO=<unset>
ROS_VERSION=<unset>
ROS_PACKAGE_PATH=<unset>
rosversion not found
/opt/ros not found
```

Therefore ROS runtime checks cannot be performed in the development container.
That result does not contradict the operator-confirmed vendor VM configuration
and must not be used to select dependencies for the vendor VM.

## Step 2: check Python without changing it

Run this command in the vendor VM:

```bash
printf '%s\n' '--- ROS ---'; rosversion -d; rosversion ros; \
printf '%s\n' '--- Python ---'; python --version 2>&1; python3 --version 2>&1
```

It prints the ROS distribution, ROS core version, and both Python interpreter
versions. The `2>&1` parts only make version output easier to copy; they do not
modify either interpreter. Do not change `/usr/bin/python`, install packages, or
run `update-alternatives` at this stage.

Copy the complete output into the project notes before proceeding to the
read-only workspace inspection.

### Recorded Python result

The operator reported these versions from the vendor VM on 2026-09-16:

```text
Python 2.7.17
Python 3.6.9
```

ROS Melodic commonly uses Python 2, so initial ROS scripts should remain Python
2.7 compatible until the interpreter used by the active ROS installation is
verified. Do not repoint `python` to Python 3.

## Step 3: inspect existing workspaces without changing them

Run this single command in a fresh vendor-VM terminal:

```bash
printf '%s\n' '--- current directory ---'; pwd; \
printf '%s\n' '--- ROS_PACKAGE_PATH ---' "${ROS_PACKAGE_PATH:-<unset>}"; \
printf '%s\n' '--- CMAKE_PREFIX_PATH ---' "${CMAKE_PREFIX_PATH:-<unset>}"; \
printf '%s\n' '--- catkin workspace markers under HOME ---'; \
find "$HOME" -maxdepth 4 -type f -name .catkin_workspace -print 2>/dev/null
```

The command prints the current directory, the environment paths used by ROS and
CMake, and any `.catkin_workspace` marker files within four levels of the home
directory. It does not source, build, create, or modify a workspace.

Copy the complete output before proceeding. In particular, do not run
`catkin_make`, edit `.bashrc`, or create the new workspace yet.

### Recorded workspace result

The operator reported the following active overlay order on 2026-09-16:

1. `/home/wheeltec-client/wheeltec_hector`
2. `/home/wheeltec-client/wheeltec_stepper_arm`
3. `/home/wheeltec-client/wheeltec_table_arm`
4. `/home/wheeltec-client/wheeltec_robot`
5. `/opt/ros/melodic`

Catkin workspace markers were found in `wheeltec_hector`, `wheeltec_arm`,
`wheeltec_robot`, `wheeltec_table_arm`, and `wheeltec_stepper_arm`. The new UWB
workspace must not be placed inside or built from any of those directories.

Continue with [`workspace_setup.md`](workspace_setup.md).
