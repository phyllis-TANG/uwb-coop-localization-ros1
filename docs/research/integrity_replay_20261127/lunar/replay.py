"""Apply the three estimators to causal observations. Load synthetic truth only for scoring."""
import csv
import gzip
import json
from time import perf_counter_ns, process_time_ns

import numpy as np

from nine_bias import NineBiasFilter
from monitor import Config, Monitor


METHODS = ("ss_only", "nine_bias_innovation", "iterative")
OBS_FIELDS = {"id", "times_s", "anchors", "heights", "ranges", "increments",
              "prior", "sigma_range", "sigma_motion", "sigma_prior"}


def open_json(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def run(obs, method):
    if set(obs) != OBS_FIELDS:
        raise ValueError(f"Observation interface changed: {set(obs) ^ OBS_FIELDS}")
    times = np.asarray(obs["times_s"], dtype=float)
    dt = np.diff(times)
    np.testing.assert_allclose(dt, dt[0], atol=1e-12, rtol=1e-12)
    if method == "nine_bias_innovation":
        monitor = NineBiasFilter(obs)
    else:
        conf = dict(range_sigma=obs["sigma_range"], odom_sigma=obs["sigma_motion"]/np.sqrt(dt[0]),
                    initial_sigma=obs["sigma_prior"])
        if method == "ss_only":
            conf["max_augmented"] = 0
        monitor = Monitor(obs["anchors"], obs["heights"][0], obs["prior"], Config(**conf))
    joint = []
    for i,t in enumerate(times):
        odo = np.asarray(obs["increments"][i-1] if i else np.zeros((2,2)), dtype=float)
        ranges = np.asarray(obs["ranges"][i], dtype=float)
        missing = int((~np.isfinite(ranges)).sum())
        if np.isinf(ranges).any():
            raise ValueError("Unexpected infinite range")
        heights = obs["heights"][i]
        before = perf_counter_ns()
        cpu_before = process_time_ns()
        if method == "nine_bias_innovation" and missing:
            # Preserve the legacy nine-range gate: with incomplete data predict only.
            # This is its original prediction, without state update or published HPL.
            monitor.x[:4] += odo.ravel()
            if monitor.prev is not None:
                monitor.cov += np.diag([monitor.motion_var] * 4 + [.01**2*(t-monitor.prev)] * 9)
            monitor.prev = t
            out = dict(t=t, xy=monitor.x[:4].reshape(2,2).copy().tolist(),hpl=[None,None],
                       fd_pass=False,status="incomplete_nine_ranges",augmented=[],selected=[])
        else:
            out = monitor.step(float(t),ranges,odo,heights=heights)
        cpu_s = (process_time_ns() - cpu_before) * 1e-9
        wall_s = (perf_counter_ns() - before) * 1e-9
        if method == "ss_only":
            out["hpl"] = [None,None]
        joint.append((out,missing,wall_s,cpu_s))
    return joint



def score_record(job):
    suite, observed_path, reference_path = job
    obs = open_json(observed_path)
    estimates = {method: run(obs, method) for method in METHODS}
    ref = open_json(reference_path)
    if ref["id"] != obs["id"] or ref["times_s"] != obs["times_s"]:
        raise ValueError(f"Reference and observations differ for {observed_path.name}")
    xyz = np.asarray(ref["xyz"], dtype=float)
    if xyz.shape != (len(obs["times_s"]), 2, 3) or not np.isfinite(xyz).all():
        raise ValueError(f"Invalid reference trajectory for {obs['id']}")
    rows = []
    for method, sequence in estimates.items():
        for tick, (estimate, missing, wall_s, cpu_s) in enumerate(sequence):
            errors = np.linalg.norm(np.asarray(estimate["xy"]) - xyz[tick, :, :2], axis=1)
            for rover in range(2):
                level = estimate["hpl"][rover]
                if level is not None and (not np.isfinite(level) or level < 0):
                    raise ValueError(f"Invalid HPL at epoch {tick}")
                rows.append(dict(
                    suite=suite, run=obs["id"], method=method, rover=rover + 1,
                    epoch=tick, t_s=obs["times_s"][tick], missing_links=missing,
                    accepted=bool(estimate["fd_pass"]), pe_m=float(errors[rover]),
                    hpl_m=level, cpu_s=cpu_s, wall_s=wall_s,
                ))
    return rows


def summarise(rows):
    summaries = []
    suites = {
        "main": [r for r in rows if r["suite"] == "main"],
        "screen_all_epochs": [r for r in rows if r["suite"] == "screen"],
        "screen_blocked_epochs": [r for r in rows if r["suite"] == "screen" and r["missing_links"]],
    }
    for suite, records in suites.items():
        for method in METHODS:
            for rover in (1, 2):
                epochs = [r for r in records if r["method"] == method and r["rover"] == rover]
                issued = [r for r in epochs if r["hpl_m"] is not None]
                breaches = sum(r["pe_m"] > r["hpl_m"] for r in issued)
                summaries.append(dict(
                    suite=suite, method=method, rover=rover, requested=len(epochs),
                    detector_passes=sum(r["accepted"] for r in epochs), issued=len(issued),
                    covered=len(issued)-breaches if issued else None,
                    exceeded=breaches if issued else None,
                    median_issued_pe_m=float(np.median([r["pe_m"] for r in issued])) if issued else None,
                    median_hpl_m=float(np.median([r["hpl_m"] for r in issued])) if issued else None,
                ))
    return summaries
