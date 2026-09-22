#!/usr/bin/env bash

# Collect read-only host, time, ROS, and serial evidence for a field session.
# This script does not open serial ports or change any system/device setting.

set -u

snapshot_root="${1:-/tmp}"
snapshot_stamp="$(date +%Y%m%d_%H%M%S)"
snapshot_file="${snapshot_root%/}/uwb_field_snapshot_${snapshot_stamp}.txt"

mkdir -p "$snapshot_root"

run_section() {
  section_title="$1"
  shift
  {
    printf '\n## %s\n' "$section_title"
    "$@" 2>&1 || true
  } >> "$snapshot_file"
}

{
  printf '# UWB field snapshot\n'
  printf 'generated_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'hostname=%s\n' "$(hostname)"
  printf 'user=%s\n' "$(id -un)"
  printf 'ROS_MASTER_URI=%s\n' "${ROS_MASTER_URI:-unset}"
  printf 'ROS_IP=%s\n' "${ROS_IP:-unset}"
  printf 'ROS_HOSTNAME=%s\n' "${ROS_HOSTNAME:-unset}"
} > "$snapshot_file"

run_section "Kernel" uname -a
run_section "Operating system" lsb_release -a
run_section "Python 2" python2 --version
run_section "Python 3" python3 --version
run_section "Network addresses" ip -brief address
run_section "Routes" ip route
run_section "System time" timedatectl status
run_section "chrony tracking" chronyc tracking
run_section "chrony sources" chronyc sources -v
run_section "USB devices" lsusb
run_section "Stable serial paths" ls -l /dev/serial/by-id
run_section "Loaded serial drivers" sh -c "lsmod | grep -E 'ch343|cdc_acm'"
run_section "ROS nodes" rosnode list
run_section "ROS topics" rostopic list -v
run_section "ROS use_sim_time" rosparam get /use_sim_time

printf '%s\n' "$snapshot_file"
