#!/usr/bin/env python3
"""Generate repeatable two-car UWB samples for Isaac Lab and the ROS 1 bridge."""

import argparse
import csv
from pathlib import Path
import random
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "ros_ws/src/uwb_coop_localization/scripts"))
from two_car_model import sample_range  # noqa: E402


FIELDS = [
    "time_s", "car1_x", "car1_y", "car1_z", "car1_yaw",
    "car2_x", "car2_y", "car2_z", "car2_yaw", "true_range_m",
    "car1_range_m", "car1_quality", "car2_range_m", "car2_quality",
]


def resample(times, xyz, tick):
    coordinates = np.array([np.interp(tick, times, xyz[:, col]) for col in range(3)]).T
    velocity = np.gradient(coordinates[:, :2], tick, axis=0)
    yaw = np.unwrap(np.arctan2(velocity[:, 1], velocity[:, 0]))
    return coordinates, yaw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rate", type=float, default=20.0)
    parser.add_argument("--noise", type=float, default=0.03)
    parser.add_argument("--bias", type=float, default=0.0)
    parser.add_argument("--nlos-probability", type=float, default=0.0)
    parser.add_argument("--nlos-bias", type=float, default=0.4)
    parser.add_argument("--dropout-probability", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    if args.rate <= 0:
        parser.error("--rate must be positive")
    data = np.load(args.scene)
    times = data["sim_time"]
    tick = np.arange(0.0, times[-1] + 1e-9, 1.0 / args.rate)
    leader, leader_yaw = resample(times, data["leader"], tick)
    follower, follower_yaw = resample(times, data["follower"], tick)
    random_generator = random.Random(args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for i, t in enumerate(tick):
            distance = float(np.linalg.norm(leader[i] - follower[i]))
            a = sample_range(distance, random_generator, args.noise, args.bias,
                             args.nlos_probability, args.nlos_bias, args.dropout_probability)
            b = sample_range(distance, random_generator, args.noise, args.bias,
                             args.nlos_probability, args.nlos_bias, args.dropout_probability)
            writer.writerow(dict(zip(FIELDS, [
                "%.6f" % t,
                *["%.6f" % v for v in leader[i]], "%.6f" % leader_yaw[i],
                *["%.6f" % v for v in follower[i]], "%.6f" % follower_yaw[i],
                "%.6f" % distance,
                "" if a is None else "%.6f" % a[0], "" if a is None else a[1],
                "" if b is None else "%.6f" % b[0], "" if b is None else b[1],
            ])))
    print("Wrote %d UWB ticks to %s" % (len(tick), args.output))


if __name__ == "__main__":
    main()
