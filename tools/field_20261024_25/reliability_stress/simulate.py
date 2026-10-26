"""Reproducible noisy fixtures. Only this module and evaluate.py see truth."""
import copy
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_adapter import antenna, wall_distance
from protocol import CARS, TAGS, WALLS


def trajectory(t, variant):
    v = float(variant)
    return np.array([[1.35+.38*math.sin((.11+.01*v)*t)+.008*t,
                      1.45+.40*math.sin(.075*t+.2*v), .2+.25*math.sin(.10*t)],
                     [3.35+.40*math.cos((.095+.01*v)*t+.4*v),
                      3.10+.48*math.sin(.085*t+.5*v), -.3+.22*math.cos(.09*t)]])


def generate(config, template, split, scenario, source_car, seed):
    if split not in ("development", "validation") or scenario not in config["scenarios"]:
        raise ValueError("unknown frozen experiment")
    params = config[split]
    rng = np.random.default_rng(np.random.SeedSequence([seed, params["trajectory_variant"]]))
    geometry = copy.deepcopy(template)
    n = int(round(config["duration_s"]*1e9/config["dt_ns"]))+1
    times = np.arange(n, dtype=np.int64)*config["dt_ns"]
    truth = np.array([trajectory(t/1e9, params["trajectory_variant"]) for t in times])
    noise = params["noise_scale"]
    odom = truth.copy()
    odom[:, :, :2] += np.cumsum(rng.normal(0., .009*noise, (n, 2, 2)), axis=0)
    odom[:, :, :2] += np.arange(n)[:, None, None]*np.array([[[.0012, -.0006], [-.0008, .0010]]])
    odom[:, :, 2] += np.cumsum(rng.normal(0., .0015*noise, (n, 2)), axis=0)
    initial = {c: np.r_[truth[0, i, :2]+rng.normal(0., .12, 2), odom[0, i, 2]] for i, c in enumerate(CARS)}
    events = []
    for tick, now in enumerate(times[1:], start=1):
        t = int(now)/1e9
        active = config["fault_start_s"] <= t < config["fault_end_s"]
        common_noise = rng.normal(0., config["peer_sigma_m"]*.85*noise)
        for i, car in enumerate(CARS):
            # Different samples, same known clock. The data transport layer has
            # no access to the generator's true pose interpolation.
            lag = 20000000 if car == "car1" else 30000000
            if scenario == "async_delay" and car == source_car:
                lag = 85000000
            sample = int(now)-lag
            poses = trajectory(sample/1e9, params["trajectory_variant"])
            apparent = poses.copy()
            if scenario == "coherent_fault" and active:
                apparent[:, :2] += [.65, -.40]
            for j, target in enumerate(sorted(WALLS)):
                value = wall_distance(apparent[i], car, target, geometry)+rng.normal(0., config["wall_sigma_m"]*noise)
                if scenario in ("wall_reduced", "bias_weak_wall", "slow_ramp") and active and car == source_car and j != 0:
                    continue
                # Diagonally opposite corners have nearly opposed bearings for
                # these near-diagonal trajectories: weak local transverse info.
                if scenario == "geometry_degenerate" and active and car == source_car and target not in ("node_2", "node_10"):
                    continue
                events.append(_row(len(events), car, target, sample, sample+10000000, value))
            value = float(np.linalg.norm(antenna(apparent[0], "car1", geometry)-antenna(apparent[1], "car2", geometry)))
            value += common_noise+rng.normal(0., config["peer_sigma_m"]*math.sqrt(1-.85**2)*noise)
            if active:
                if scenario in ("peer_bias", "bias_weak_wall") and car == source_car:
                    value += params["peer_bias_m"]
                if scenario == "common_peer_bias":
                    value += params["peer_bias_m"]
                if scenario == "spikes" and car == source_car and tick % 7 == 0:
                    value += params["spike_m"]
                if scenario == "slow_ramp" and car == source_car:
                    value += params["ramp_max_m"]*(t-config["fault_start_s"])/(config["fault_end_s"]-config["fault_start_s"])
                if scenario == "small_bias" and car == source_car:
                    value += .12
            delay = 10000000
            if scenario == "async_delay" and active and car == source_car:
                delay = (600000000, 220000000, 80000000)[tick % 3]
            if scenario == "oneway_missing" and active and car == source_car:
                continue
            row = _row(len(events), car, TAGS[CARS[1-i]], sample, sample+delay, value)
            events.append(row)
            if scenario == "async_delay" and active and tick % 9 == 0:
                events.append(dict(row, receive_ns=row["receive_ns"]+5000000))
    events.sort(key=lambda r: (r["receive_ns"], r["record_index"]))
    # Actual arrivals beyond final cutoff remain in the input but aren't consumed.
    public = {"times_ns": times, "odom": odom, "events": events, "initial": initial, "geometry": geometry}
    return public, truth


def _row(index, car, target, sample, receive, value):
    return {"experiment_id": "synthetic", "vehicle_id": car, "tag_id": TAGS[car], "target_id": target,
            "record_index": index, "link_index": 0, "sample_ns": sample, "receive_ns": receive,
            "clock_mapping_id": "synthetic_exact_v1", "range_m": float(value), "source": "raw",
            "primary_observation": True, "valid": True}
