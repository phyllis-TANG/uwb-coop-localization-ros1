#!/usr/bin/env bash
# Run in a sourced ROS1 environment. Only records; never commands vehicle motion.
# Override REQUIRED_TOPICS for single-car or differently named topics, e.g.:
# REQUIRED_TOPICS='/car1/imu /car1/odom /car1/uwb/ranges' bash record_session.sh car1_static /data
set -euo pipefail
label=${1:?Usage: bash record_session.sh RUN_LABEL OUTPUT_DIRECTORY}
out=${2:?Provide output directory}
[[ "$label" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Use letters, numbers, underscores or hyphens for RUN_LABEL' >&2; exit 1; }
for command in rosbag rostopic sha256sum; do command -v "$command" >/dev/null; done
read -r -a required <<< "${REQUIRED_TOPICS:-/car1/imu /car2/imu /car1/odom /car2/odom /car1/uwb/ranges /car2/uwb/ranges}"
available=$(rostopic list)
for topic in "${required[@]}"; do
  if ! printf '%s\n' "$available" | grep -Fxq -- "$topic"; then
    echo "Required topic absent: $topic. Verify actual topic names and ROS master." >&2; exit 1
  fi
done
mkdir -p "$out"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_${label}"
bag="$out/$run_id.bag"
[[ ! -e "$bag" && ! -e "$bag.active" ]] || { echo 'Output already exists' >&2; exit 1; }
printf '%s\n' "$available" > "$out/${run_id}_topics.txt"
printf 'Record host UTC: %s\nROS master: %s\n' "$(date -u +%FT%TZ)" "${ROS_MASTER_URI:-unset}" > "$out/${run_id}_session.txt"
extra=()
for topic in /tf /tf_static /car1/cmd_vel /car2/cmd_vel; do
  if printf '%s\n' "$available" | grep -Fxq -- "$topic"; then extra+=("$topic"); fi
done
# Catch Ctrl-C in the wrapper so the closed bag can be hashed after rosbag exits.
trap ':' INT
set +e
rosbag record -O "$bag" "${required[@]}" "${extra[@]}"
status=$?
set -e
trap - INT
if [[ -f "$bag" && ! -e "$bag.active" ]]; then
  rosbag info "$bag" > "$out/${run_id}_info.txt"
  sha256sum "$bag" > "$out/${run_id}_sha256.txt"
  echo "Saved $bag. Confirm nonzero counts in ${run_id}_info.txt."
else
  echo 'Bag was not finalized; inspect .active and recorder output before leaving.' >&2
  exit 1
fi
if [[ $status -ne 0 && $status -ne 130 ]]; then exit "$status"; fi
