#!/usr/bin/env python3
"""Independent output readback; does not import engine, simulator, or evaluator."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from normalize import new_run, finish_run
from run_nightly import sha256, atomic_json
import time


def verify(directory):
    run = json.loads((directory/"run.json").read_text())
    if run["status"] != "DONE":
        raise ValueError("only complete runs can be accepted")
    cfg = json.loads((directory/"config_snapshot/frozen_config.json").read_text())
    for item in run["outputs"]:
        if sha256(directory/item["relative_path"]) != item["sha256"]:
            raise ValueError("output hash mismatch: "+item["relative_path"])
    for item in run["inputs"]:
        if sha256(directory/item["relative_path"]) != item["sha256"]:
            raise ValueError("input hash mismatch")
    counts = {"trials": 0, "estimate_rows": 0, "checked_metric_rows": 0, "selected_peer_checks": 0,
              "firewall_bound_checks": 0, "solver_failures": 0}
    worst_healthy, worst_weak = 0., 0.
    for trial_id in run["completed_experiments"]:
        trial = directory/trial_id
        rows = list(csv.DictReader(gzip.open(trial/"estimate.csv.gz", "rt")))
        truth = np.array(json.loads(gzip.decompress((trial/"truth_evaluation_only.json.gz").read_bytes())))
        odom = json.loads(gzip.decompress((trial/"odom.json.gz").read_bytes()))
        observations = json.loads(gzip.decompress((trial/"observations.json.gz").read_bytes()))
        by_id = {}
        for r in observations:
            by_id.setdefault((r["vehicle_id"], r["record_index"]), r)
        times = np.array(odom["time_ns"], dtype=np.int64)
        ds = json.loads(gzip.decompress((trial/"diagnostics.json.gz").read_bytes()))
        audit = json.loads((trial/"audit.json").read_text())
        scores = json.loads((trial/"metrics.json").read_text())
        estimates = {m: np.zeros((len(times), 2, 2)) for m in cfg["methods"]}
        for r in rows:
            tick = int(round(float(r["canonical_time_s"])*1e9/cfg["dt_ns"]))
            i = ("car1", "car2").index(r["vehicle_id"])
            estimates[r["method_id"]][tick, i] = [float(r["x_m"]), float(r["y_m"])]
        if len(rows) != len(times)*len(cfg["methods"])*2:
            raise ValueError("estimate row count mismatch")
        for m in cfg["methods"]:
            if audit["methods"][m]["linear_solves"] != len(times)*4*cfg["gn_iterations"]:
                raise ValueError("compute budget mismatch")
            used = set()
            for now, d in zip(times, ds[m]):
                counts["solver_failures"] += int(not d["solver_success"])
                for trace in d["admission_trace"]:
                    if trace["reason"] != "selected":
                        continue
                    r = by_id[trace["vehicle_id"], trace["record_index"]]
                    if not r["sample_ns"] <= r["receive_ns"] <= now or now-r["sample_ns"] > cfg["max_age_ns"]:
                        raise ValueError("noncausal or stale selected peer")
                    b = (r["sample_ns"]+cfg["correlation_bin_ns"]//2)//cfg["correlation_bin_ns"]
                    if b in used:
                        raise ValueError("correlated peer reuse")
                    used.add(b)
                    counts["selected_peer_checks"] += 1
        shift = np.linalg.norm(estimates["firewall"]-estimates["independent"], axis=2)
        for k, d in enumerate(ds["firewall"]):
            for i, healthy in enumerate(d["healthy"]):
                cap = cfg["healthy_shift_cap_m"] if healthy else cfg["weak_shift_cap_m"]
                if shift[k, i] > cap+1e-10:
                    raise ValueError("independent readback violates firewall bound")
                if healthy:
                    worst_healthy = max(worst_healthy, float(shift[k, i]))
                else:
                    worst_weak = max(worst_weak, float(shift[k, i]))
                counts["firewall_bound_checks"] += 1
        errors = {m: np.linalg.norm(x-truth[:, :, :2], axis=2) for m, x in estimates.items()}
        seconds = times/1e9
        for score in scores:
            i = ("car1", "car2").index(score["vehicle_id"])
            phase = score["phase"]
            mask = np.ones(len(times), dtype=bool) if phase == "all" else (
                (seconds >= cfg["fault_start_s"]) & (seconds < cfg["fault_end_s"]) if phase == "fault" else seconds >= cfg["fault_end_s"])
            e = errors[score["method_id"]][mask, i]
            vals = {"rmse_m": float(np.sqrt(np.mean(e**2))), "p95_m": float(np.quantile(e, .95)),
                    "p99_m": float(np.quantile(e, .99)), "max_m": float(np.max(e)),
                    "error_failure_fraction": float(np.mean(e > cfg["failure_error_m"]))}
            for name, value in vals.items():
                if abs(value-score[name]) > 1e-11:
                    raise ValueError("metric readback mismatch: "+name)
            counts["checked_metric_rows"] += 1
        counts["trials"] += 1
        counts["estimate_rows"] += len(rows)
    return {"schema_version": 1, "status": "DONE", "input_run_sha256": sha256(directory/"run.json"),
            "checked": counts, "max_healthy_shift_m": worst_healthy, "max_weak_shift_m": worst_weak,
            "limitations": ["readback verifies recorded causality; online prefix test is separate",
                            "does not independently validate synthetic physical realism"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    started, run = time.monotonic(), None
    try:
        run = new_run(args.output, "reliability_independent_readback", [HERE/"frozen_config.json"], sys.argv)
        run["source_sha256"][str(Path(__file__).resolve().relative_to(HERE.parents[2]))] = sha256(Path(__file__))
        run["inputs"] = [{"asset_id": "synthetic_run", "relative_path": "run.json", "sha256": sha256(args.input/"run.json")}]
        result = verify(args.input)
        atomic_json(args.output/"verification.json", result)
        finish_run(args.output, run, "DONE", started)
        print(json.dumps(result, ensure_ascii=False))
    except (Exception, KeyboardInterrupt) as exc:
        if run:
            finish_run(args.output, run, "FAILED", started, exc)
        raise


if __name__ == "__main__":
    main()
