#!/usr/bin/env python3
"""Preregistered two-car synthetic inputs; truth and labels stay separate.

The source_file_sha256 in an event identifies the synthetic generation
specification, not a ROS bag.  The output manifest separately hashes every
actual input file.  Calling make_case with the same seed and a different
scenario consumes exactly the same random draws.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config.json"
EPOCH_NS = 1_790_000_000_000_000_000
STEP_NS = 50_000_000
DURATION_NS = 64_000_000_000
SCENARIOS = ("nominal", "peer_bias", "wall_bias", "peer_gap")
CARS = ("car1", "car2")
DEVELOPMENT_SEEDS = (7, 8)
FORMAL_SEEDS = (101, 211, 307)


def canonical(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rotation(theta):
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, -s], [s, c]])


def true_pose(t, car, model):
    """Analytic room pose; t=1 is the independently specified initial prior.

    The two base trajectories span two dimensions and have changing headings.
    Nothing in their construction uses a measured or simulated endpoint.
    """
    u = float(t) - 1.0
    theta0 = math.radians(model["initial_heading_deg"])
    base0 = np.asarray(model["start_antenna_xyz_m"][:2]) - rotation(theta0) @ np.asarray(
        model["base_to_antenna_body_xy_m"]
    )
    if car == "car1":
        displacement = [0.85 * math.sin(0.055 * u) + 0.25 * math.sin(0.16 * u),
                        0.45 * math.sin(0.09 * u)]
        yaw = theta0 + 0.5 * math.sin(0.1 * u) + 0.2 * math.sin(0.18 * u)
    elif car == "car2":
        displacement = [0.65 * math.sin(0.08 * u),
                        0.8 * math.sin(0.06 * u) + 0.15 * math.sin(0.19 * u)]
        yaw = theta0 - 0.45 * math.sin(0.085 * u) + 0.18 * math.sin(0.17 * u)
    else:
        raise ValueError("unknown vehicle")
    return np.r_[base0 + displacement, yaw]


def antenna_xyz(pose, model):
    xy = np.asarray(pose[:2]) + rotation(float(pose[2])) @ np.asarray(
        model["base_to_antenna_body_xy_m"]
    )
    return np.r_[xy, model["antenna_height_m"]]


def make_case(seed, scenario):
    """Return (config, events, truth, labels), all strict-JSON serializable.

    Formal seeds are callable after the caller has frozen source/config; this
    module does not run them at import, in tests, or as an implicit default.
    """
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if scenario not in SCENARIOS:
        raise ValueError("unknown preregistered scenario")
    template = json.loads(CONFIG.read_text())
    config = copy.deepcopy(template)
    rng = np.random.default_rng(seed)
    count = DURATION_NS // STEP_NS + 1
    sample_times = np.arange(count, dtype=float) * (STEP_NS / 1e9)
    poses, antennas, odometry, range_noise = {}, {}, {}, {}

    # Draw every random array independently of the scenario and before applying
    # any fault. Deleting peer fields must not shift subsequent noise draws.
    for car in CARS:
        m = template["models"][car]
        config["models"][car]["start_antenna_xyz_m"][:2] = (
            np.asarray(m["start_antenna_xyz_m"][:2]) + rng.normal(0, 0.08, 2)
        ).tolist()
        config["models"][car]["initial_heading_deg"] = float(
            m["initial_heading_deg"] + rng.normal(0, 2.0)
        )
        poses[car] = np.array([true_pose(t, car, m) for t in sample_times])
        antennas[car] = np.array([antenna_xyz(p, m) for p in poses[car]])
        step_noise = rng.normal(size=(count - 1, 3)) * np.array([0.002, 0.002, 0.0008])
        odometry[car] = np.zeros((count, 3))
        for i in range(1, count):
            before, after = poses[car][i - 1], poses[car][i]
            body = rotation(-float(before[2])) @ (after[:2] - before[:2])
            previous = odometry[car][i - 1]
            odometry[car][i, :2] = previous[:2] + rotation(float(previous[2])) @ (
                body + step_noise[i - 1, :2]
            )
            odometry[car][i, 2] = previous[2] + after[2] - before[2] + step_noise[i - 1, 2]
        range_noise[car] = rng.normal(0, 0.04, (count, 5))

    case_id = f"synthetic_seed{seed}_{scenario}"
    source_specification = {
        "source_kind": "synthetic_generation_specification_not_bag",
        "generator_sha256": sha(__file__),
        "template_sha256": sha(CONFIG),
        "seed": seed,
        "scenario": scenario,
        "epoch_ns": EPOCH_NS,
        "sample_step_ns": STEP_NS,
        "duration_ns": DURATION_NS,
    }
    source_sha = hashlib.sha256(canonical(source_specification).encode()).hexdigest()
    events = [{
        "case_id": case_id,
        "kind": "clock",
        "vehicle_id": None,
        "header_epoch_ns": EPOCH_NS,
        "receive_epoch_ns": EPOCH_NS,
        "source_file_sha256": source_sha,
        "source_observation_id": "synthetic_clock_start",
        "topic": "/synthetic/clock",
        "value": {"clock_epoch_ns": EPOCH_NS},
    }]
    peer_keys = {"car1": "node_0", "car2": "node_1"}
    for i in range(count):
        header_ns = EPOCH_NS + i * STEP_NS
        fault_active = 24_000_000_000 <= i * STEP_NS < 38_000_000_000
        distance = float(np.linalg.norm(antennas["car1"][i] - antennas["car2"][i]))
        for car_index, car in enumerate(CARS):
            model = template["models"][car]
            values = {}
            for j, anchor in enumerate(sorted(model["anchors_xyz_m"])):
                raw = float(np.linalg.norm(
                    antennas[car][i] - np.asarray(model["anchors_xyz_m"][anchor])
                ) + range_noise[car][i, j])
                if scenario == "wall_bias" and fault_active and car == "car1" and anchor == "node_2":
                    raw += 1.2
                values[anchor] = raw
            peer = distance + float(range_noise[car][i, 4])
            if scenario == "peer_bias" and fault_active and car == "car1":
                peer += 1.2
            if not (scenario == "peer_gap" and fault_active):
                values[peer_keys[car]] = peer
            for kind_index, (kind, value) in enumerate((
                ("odom", {"pose": odometry[car][i].tolist()}),
                ("uwb", values),
            )):
                stream = 2 * car_index + kind_index
                delay_ns = (10 + ((7 * i + 5 * stream) % 31)) * 1_000_000
                event = {
                    "case_id": case_id,
                    "vehicle_id": car,
                    "kind": kind,
                    "header_epoch_ns": header_ns,
                    "receive_epoch_ns": header_ns + delay_ns,
                    "source_file_sha256": source_sha,
                    "source_observation_id": f"{car}:{kind}:{i}",
                    "topic": f"/{car}/odom" if kind == "odom" else f"/{car}/uwb/ranges",
                    "value": value,
                }
                if kind == "uwb":
                    event["representation"] = "bridge"
                events.append(event)
    events.sort(key=lambda event: event["receive_epoch_ns"])
    for index, event in enumerate(events):
        event["record_index"] = index

    truth = []
    for t in range(65):
        cars = {}
        for car in CARS:
            pose = true_pose(t, car, template["models"][car])
            cars[car] = {
                "pose": pose.tolist(),
                "antenna_xyz_m": antenna_xyz(pose, template["models"][car]).tolist(),
            }
        truth.append({"state_epoch_ns": EPOCH_NS + t * 1_000_000_000,
                      "time_s": float(t), "cars": cars})
    labels = {
        "schema_version": 1,
        "case_id": case_id,
        "seed": seed,
        "scenario": scenario,
        "source_specification": source_specification,
        "source_identity_sha256": source_sha,
        "source_identity_semantics": "hash of synthetic generation specification, not a bag hash",
        "fault": None if scenario == "nominal" else {
            "interval_s": [24.0, 38.0],
            "interval_convention": "left_closed_right_open",
            "kind": scenario,
            "affected_stream": {
                "peer_bias": "car1_to_car2_only; reverse_diagnostic_unmodified",
                "wall_bias": "car1/node_2_only",
                "peer_gap": "both_peer_directions_removed; wall_messages_retained",
            }[scenario],
            "additive_bias_m": 1.2 if scenario in ("peer_bias", "wall_bias") else None,
        },
        "clock": {"kind": "exact_shared_synthetic_clock", "epoch_origin_ns": EPOCH_NS,
                  "receipt_delay_min_ns": 10_000_000, "receipt_delay_max_ns": 40_000_000,
                  "first_clock_event_ns": EPOCH_NS,
                  "last_real_receipt_ns": events[-1]["receive_epoch_ns"],
                  "eof_advanced": False},
        "truth_convention": "room base XY/yaw and 3D antenna centers; integer seconds 0..64",
        "initial_prior": "room antenna and heading at t=1 plus seed noise; no endpoint use",
        "noise": {"raw_range_sigma_m": 0.04, "odom_body_step_xy_sigma_m": 0.002,
                  "odom_step_yaw_sigma_rad": 0.0008, "initial_xy_sigma_m": 0.08,
                  "initial_yaw_sigma_deg": 2.0},
    }
    # Fail here if an implementation change introduces NaN, numpy scalars, etc.
    canonical([config, events, truth, labels])
    return config, events, truth, labels


def write_case(root, seed, scenario):
    """Write one immutable case into a new directory and return its manifest."""
    root = Path(root)
    repo = HERE.parents[1]
    resolved = root.resolve()
    if resolved == repo or repo in resolved.parents:
        raise ValueError("synthetic input artifacts must be outside the Git worktree")
    config, events, truth, labels = make_case(seed, scenario)
    root.mkdir(parents=True, exist_ok=False)
    event_bytes = ("\n".join(canonical(event) for event in events) + "\n").encode()
    # Empty gzip filename and fixed mtime make paired hashes reproducible.
    with (root / "events.jsonl.gz").open("xb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
            stream.write(event_bytes)
    (root / "truth.jsonl").write_text("\n".join(canonical(row) for row in truth) + "\n")
    (root / "labels.json").write_text(json.dumps(labels, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (root / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True, allow_nan=False) + "\n")
    manifest = {
        "schema_version": 1, "case_id": labels["case_id"], "seed": seed,
        "scenario": scenario, "event_count": len(events), "truth_count": len(truth),
        "source_specification": labels["source_specification"],
        "source_identity_sha256": labels["source_identity_sha256"],
        "first_receive_epoch_ns": events[0]["receive_epoch_ns"],
        "last_receive_epoch_ns": events[-1]["receive_epoch_ns"],
        "files": {name: sha(root / name) for name in
                  ("events.jsonl.gz", "truth.jsonl", "labels.json", "config.json")},
        "paired_arms": ["D0", "D1"],
        "truth_and_labels_are_estimator_inputs": False,
    }
    (root / "input_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    args = parser.parse_args(argv)
    manifest = write_case(args.output, args.seed, args.scenario)
    print(canonical(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
