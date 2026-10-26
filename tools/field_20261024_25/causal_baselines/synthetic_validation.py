#!/usr/bin/env python3
"""Fixed-seed noisy synthetic validation; never tunes or evaluates field errors."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

import model
import replay

CONFIG = Path(__file__).with_name("synthetic_config.json")
ORIGIN = 1792925285431466217


def controls(car, seconds):
    segment = min(int(seconds//3), 3)
    if car == "car1":
        return np.array([( .24, 0., .30), (-.18, 0., -.40), (0., 0., .8), (.20, 0., -.20)][segment])
    return np.array([(.18, 0., -.25), (-.12, 0., .30), (0., 0., -.5), (.24, 0., .15)][segment])


def move(pose, twist, seconds):
    return np.r_[pose[:2]+model.rotation(pose[2]) @ model.twist_translation(twist, seconds),
                 model.wrap(pose[2]+twist[2]*seconds)]


def fixture(config, seed, scenario):
    rng = np.random.default_rng(seed)
    p = config["validation_protocol"]
    period = p["odom_dt_ns"]
    count = int(p["duration_s"]*1e9)//period
    states = {c: [np.array(config["vehicles"][c]["initial_room_pose"]["value"])] for c in model.CARS}
    odometry = {c: [np.zeros(3)] for c in model.CARS}
    for k in range(count):
        for car in model.CARS:
            twist = controls(car, k*period/1e9)
            states[car].append(move(states[car][-1], twist, period/1e9))
            measured_delta = model.twist_translation(twist, period/1e9)+rng.normal(0, p["odom_increment_noise_sigma_m"], 2)
            previous = odometry[car][-1]
            odometry[car].append(np.r_[previous[:2]+model.rotation(previous[2]) @ measured_delta,
                model.wrap(previous[2]+twist[2]*period/1e9+rng.normal(0, p["odom_increment_noise_sigma_rad"]))])
    def truth(car, stamp):
        elapsed = stamp-ORIGIN
        k = min(max(int(elapsed//period), 0), count)
        return move(states[car][k], controls(car, k*period/1e9), (elapsed-k*period)/1e9)
    events = []
    record = 0
    data_hash = hashlib.sha256(f"synthetic:{seed}:{scenario}:v1".encode()).hexdigest()
    def common(car, stamp, receive, index):
        return dict(experiment_id="synthetic", vehicle_id=car, source_asset_id="synthetic_fixture",
            source_file_sha256=data_hash, receive_epoch_ns=receive, header_epoch_ns=stamp,
            record_index=index, header_seq=index)
    for k in range(count+1):
        stamp = ORIGIN+k*period
        seconds = k*period/1e9
        for car in model.CARS:
            index = record;record += 1
            if scenario == "noisy_delay_dropout" and car == "car2" and 9 <= seconds < 10:continue
            pose = odometry[car][k]
            velocity = controls(car, seconds)+rng.normal(0, [.005, .003, .008])
            receive = stamp+5_000_000
            if scenario == "noisy_delay_dropout" and index % 37 == 0 and k > 0:receive += 160_000_000
            row = common(car, stamp, receive, index)
            row.update(frame_id=car+"/odom", child_frame_id=car+"/base_footprint",
                position_x=float(pose[0]), position_y=float(pose[1]), position_z=-99. if car == "car2" else 0.,
                position_z_semantics="driver_yaw_related_not_height" if car == "car2" else "source_odom_z_not_antenna_height",
                orientation_x=0., orientation_y=0., orientation_z=math.sin(pose[2]/2), orientation_w=math.cos(pose[2]/2),
                linear_x=float(velocity[0]), linear_y=float(velocity[1]), angular_z=float(velocity[2]))
            events.append({"kind": "odom", "row": row})
    # Directed ranges are deliberately sampled at different times (10/30 ms).
    # A common noise component across directions models their correlation.
    for k in range(int(p["duration_s"]*10)):
        shared_noise = rng.normal(0, p["peer_shared_direction_noise_sigma_m"])
        for car, offset in [("car1", 10_000_000), ("car2", 30_000_000)]:
            stamp = ORIGIN+k*100_000_000+offset
            seconds = (stamp-ORIGIN)/1e9
            if scenario == "noisy_delay_dropout" and car == "car1" and 6 <= seconds < 8:continue
            receive = stamp+12_000_000
            if scenario == "noisy_delay_dropout" and k % 17 == 0:receive += 140_000_000
            index = record;record += 1
            own, _ = model.antenna_at(truth(car, stamp), np.zeros(3), 0., config["vehicles"][car])
            other_car = "car2" if car == "car1" else "car1"
            other, _ = model.antenna_at(truth(other_car, stamp), np.zeros(3), 0., config["vehicles"][other_car])
            for li, target in enumerate(list(model.WALLS)+[model.TAGS[other_car]]):
                peer = target == model.TAGS[other_car]
                value = float(np.linalg.norm(own-other if peer else own-np.array(config["anchors_xyz_m"]["value"][target])))
                value += shared_noise if peer else rng.normal(0, p["wall_range_noise_sigma_m"])
                row = common(car, stamp, receive, index)
                row.update(topic="/"+car+"/raw", link_index=li, tag_id=model.TAGS[car], target_id=target,
                    source="raw", primary_observation=1, valid=1, range_m=value,
                    raw_frame_id=f"synthetic:{index}", bridge_frame_id=f"synthetic_bridge:{index}", pairing_status="paired_equal",
                    device_local_time_ms=(stamp-ORIGIN)//1_000_000, device_system_time_ms=(stamp-ORIGIN)//1_000_000,
                    device_clock_id="synthetic_shared_master")
                events.append({"kind": "range", "row": row})
                if scenario == "noisy_delay_dropout" and index % 29 == 0:
                    events.append(copy.deepcopy(events[-1]))
                if k % 11 == 0:
                    bridge = dict(row, source="bridge", primary_observation=0, record_index=10_000+index)
                    events.append({"kind": "range", "row": bridge})
    rng.shuffle(events)
    return events, truth, ORIGIN, ORIGIN+int(p["duration_s"]*1e9)+250_000_000


def evaluate(estimates, truth):
    """Evaluation at each row's explicit state time, never at held publication time."""
    errors = {m: [] for m in model.METHODS}
    for row in estimates:
        if not row["valid"] or row["state_epoch_ns"] is None:continue
        target = truth(row["vehicle_id"], row["state_epoch_ns"])
        errors[row["method_id"]].append(float(np.linalg.norm(np.array([row["x_m"], row["y_m"]])-target[:2])))
    return {m: {"scope": "generated_synthetic_truth_only", "rows": len(e),
                "xy_rmse_m": float(np.sqrt(np.mean(np.square(e)))) if e else None,
                "xy_max_m": max(e) if e else None} for m, e in errors.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.monotonic();run = None
    try:
        run = replay.create_run(args.output, CONFIG, [sys.executable, __file__]+(list(argv) if argv is not None else sys.argv[1:]))
        config = json.loads(CONFIG.read_text())
        replay.atomic_json(args.output/"config.json", config)
        summary = []
        for scenario in config["validation_protocol"]["scenarios"]:
            for seed in config["validation_protocol"]["seeds"]:
                name = scenario+"_seed_"+str(seed)
                output = args.output/name
                output.mkdir()
                events, truth, origin, end = fixture(config, seed, scenario)
                identity = hashlib.sha256(json.dumps(sorted(events, key=replay.event_key), sort_keys=True, allow_nan=False).encode()).hexdigest()
                run["inputs"].append({"asset_id": "synthetic_fixture", "relative_path": name, "sha256": identity})
                child = copy.deepcopy(run)
                child.update(run_id=name, role="synthetic_baseline_trial", publications_completed=0,
                    inputs=[{"asset_id":"synthetic_fixture","relative_path":name,"sha256":identity}], outputs=[])
                replay.atomic_json(output/"run.json", child)
                child_started = time.monotonic()
                try:
                    diagnostics = replay.write_replay(output, events, config, "synthetic", origin, end, child, started+600)
                except Exception as error:
                    replay.finish(output, child, "FAILED", child_started, error)
                    raise
                with (output/"estimate.csv").open(newline="") as stream:
                    import csv
                    estimates = list(csv.DictReader(stream))
                for row in estimates:
                    row["valid"] = row["valid"] == "1"
                    row["state_epoch_ns"] = int(row["state_epoch_ns"]) if row["state_epoch_ns"] else None
                    row["x_m"] = float(row["x_m"]) if row["x_m"] else None
                    row["y_m"] = float(row["y_m"]) if row["y_m"] else None
                metrics = evaluate(estimates, truth)
                if any(v["xy_rmse_m"] is None or not math.isfinite(v["xy_rmse_m"]) for v in metrics.values()):raise ValueError("nonfinite synthetic result")
                replay.atomic_json(output/"evaluation.json", metrics)
                replay.finish(output, child, "DONE", child_started)
                summary.append({"run": name, "seed": seed, "scenario": scenario, "fixture_sha256": identity,
                    "metrics": metrics, "event_status": {m: d["events"] for m, d in diagnostics["methods"].items()}})
                replay.atomic_json(args.output/"synthetic_summary.json", {"scope": "synthetic_only", "runs": summary})
                print(name, metrics, flush=True)
        run["publications_completed"] = 0
        for p in args.output.glob("*/tick_diagnostics.jsonl"):
            with p.open() as stream:run["publications_completed"] += sum(1 for line in stream)
        replay.finish(args.output, run, "DONE", started)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        if run is not None:replay.finish(args.output, run, "FAILED", started, error)
        print("ERROR: "+str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":sys.exit(main())
