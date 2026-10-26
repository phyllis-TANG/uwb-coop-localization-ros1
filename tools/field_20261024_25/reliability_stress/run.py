#!/usr/bin/env python3
"""Frozen noisy two-car stress study, with exclusive Git-external outputs."""
import argparse
import gzip
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from normalize import ROOT, SESSION, new_run, finish_run, write_table
from run_nightly import atomic_json, sha256
from engine import Estimator
from evaluate import metrics, summarize
from protocol import CARS
from simulate import generate

CONFIG = HERE/"frozen_config.json"
TEMPLATE = HERE.parent/"synthetic_comparison_config.json"


def gz_json(path, obj):
    data = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    path.write_bytes(gzip.compress(data, mtime=0))


def jsonable(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    return obj


def register_inputs(output):
    return [{"asset_id": p.parent.name, "relative_path": str(p.relative_to(output)), "sha256": sha256(p),
             "kind": "generated_evaluation_truth" if "truth" in p.name else "generated_synthetic_input"}
            for p in sorted(output.glob("*/*")) if p.name in ("observations.json.gz", "odom.json.gz", "truth_evaluation_only.json.gz", "initial_geometry.json")]


def trial(config, template, split, scenario, source, seed, output):
    public, truth = generate(config, template, split, scenario, source, seed)
    trial_id = f"{scenario}_{source}_s{seed}"
    directory = output/trial_id
    directory.mkdir()
    gz_json(directory/"observations.json.gz", public["events"])
    gz_json(directory/"odom.json.gz", {"time_ns": public["times_ns"].tolist(), "poses": public["odom"].tolist()})
    gz_json(directory/"truth_evaluation_only.json.gz", truth.tolist())
    atomic_json(directory/"initial_geometry.json", {"initial": jsonable(public["initial"]), "geometry": public["geometry"]})
    models = {m: Estimator(m, config, public["geometry"], public["initial"]) for m in config["methods"]}
    estimates = {m: [] for m in models}
    diagnostics = {m: [] for m in models}
    config_hash = sha256(CONFIG)
    rows, index = [], 0
    for k, stamp in enumerate(public["times_ns"]):
        now = int(stamp)
        arrived = []
        while index < len(public["events"]) and public["events"][index]["receive_ns"] <= now:
            arrived.append(public["events"][index])
            index += 1
        for method, model in models.items():
            x, d = model.step(now, public["odom"][k], arrived)
            estimates[method].append(x)
            diagnostics[method].append(d)
            for i, car in enumerate(CARS):
                rows.append({"experiment_id": trial_id, "method_id": method, "vehicle_id": car,
                             "canonical_time_s": now/1e9, "frame_id": "synthetic_room_base",
                             "x_m": float(x[i, 0]), "y_m": float(x[i, 1]), "z_m": None,
                             "yaw_rad": float(public["odom"][k, i, 2]), "valid": d["solver_success"],
                             "diagnostic_id": f"{method}:{k}", "source_version": "generated_noisy_v1",
                             "config_version": config_hash, "reference_version": "synthetic_truth_only"})
    estimates = {m: np.array(x) for m, x in estimates.items()}
    score = metrics(config, trial_id, scenario, source, seed, public["times_ns"]/1e9, truth, estimates, diagnostics)
    write_table(directory/"estimate.csv", rows, list(rows[0]))
    p = directory/"estimate.csv"
    (directory/"estimate.csv.gz").write_bytes(gzip.compress(p.read_bytes(), mtime=0))
    p.unlink()  # This run owns this newly generated intermediate exclusively.
    gz_json(directory/"diagnostics.json.gz", diagnostics)
    atomic_json(directory/"metrics.json", score)
    audit = {"trial_id": trial_id, "methods": {m: {"linear_solves": model.linear_solves,
              "elapsed_s": sum(d["elapsed_s"] for d in diagnostics[m]), "admission": dict(model.admission.counts),
              "max_shadow_shift_m": max(max(d["shift_from_independent_shadow_m"]) for d in diagnostics[m]),
              "gate_reopen_s": gate_reopen(config, public["times_ns"], diagnostics[m])} for m, model in models.items()}}
    atomic_json(directory/"audit.json", audit)
    return score, audit


def gate_reopen(config, times, ds):
    end = int(config["fault_end_s"]*1e9)
    answer = {}
    for car in CARS:
        saw_closed = any(d["gate"][car]["closed"] for t, d in zip(times, ds) if t < end)
        delay = None if not saw_closed else next((float((t-end)/1e9) for t, d in zip(times, ds)
                           if t >= end and not d["gate"][car]["closed"]), None)
        answer[car] = {"was_quarantined_before_removal": saw_closed, "reopen_delay_s": delay,
                       "status": "not_applicable" if not saw_closed else "censored" if delay is None else "reopened"}
    return answer


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "validation"), required=True)
    parser.add_argument("--smoke", action="store_true", help="development only: first seed, two scenes, two sources")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze-commit", help="required for validation; must equal clean actual HEAD")
    args = parser.parse_args(argv)
    if args.smoke and args.split != "development":
        parser.error("validation may not be selectively truncated")
    if args.split == "validation":
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        if args.freeze_commit != head or dirty:
            parser.error("validation requires the frozen exact commit and a clean worktree")
    started, run = time.monotonic(), None
    try:
        run = new_run(args.output, "reliability_stress_synthetic", [CONFIG, TEMPLATE, SESSION/"manifest.json", SESSION/"geometry.json"],
                      [sys.executable, str(Path(__file__).resolve())]+(list(argv) if argv is not None else sys.argv[1:]))
        run["source_sha256"].update({str(p.relative_to(ROOT)): sha256(p) for p in sorted(HERE.glob("*.py"))})
        for relative in run["source_sha256"]:
            destination = args.output/"source_snapshot"/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/relative, destination)
        for source in (CONFIG, TEMPLATE, SESSION/"manifest.json", SESSION/"geometry.json"):
            destination = args.output/"config_snapshot"/source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        run["environment"]["thread_limits"] = {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}
        run["source_snapshot"] = "source_snapshot/<repository_relative_path>"
        cfg, template = json.loads(CONFIG.read_text()), json.loads(TEMPLATE.read_text())
        scenarios = ["normal", "peer_bias"] if args.smoke else cfg["scenarios"]
        seeds = cfg[args.split+"_seeds"][:1] if args.smoke else cfg[args.split+"_seeds"]
        run.update(split=args.split, random_seeds=seeds, freeze_commit=args.freeze_commit,
                   limitations=["synthetic only; field accuracy remains BLOCKED", "known synthetic clock/room/height/lever arms",
                                "full 4x4 local Gaussian covariance; no calibrated yaw/clock uncertainty model",
                                "no academic novelty established", "bootstrap intervals unadjusted for multiple comparisons"])
        all_rows, audits = [], []
        for seed in seeds:
            for scenario in scenarios:
                for source in cfg["source_vehicles"]:
                    score, audit = trial(cfg, template, args.split, scenario, source, seed, args.output)
                    all_rows.extend(score)
                    audits.append(audit)
                    run["completed_experiments"].append(audit["trial_id"])
                    # Checkpoint on owned output; no restarts or hidden resume.
                    atomic_json(args.output/"run.json", run)
            print(json.dumps({"seed_completed": seed, "trials_completed": len(audits), "elapsed_s": time.monotonic()-started}), flush=True)
        atomic_json(args.output/"summary.json", summarize(all_rows, cfg))
        atomic_json(args.output/"metrics.json", all_rows)
        atomic_json(args.output/"audit.json", audits)
        run["inputs"] = register_inputs(args.output)
        finish_run(args.output, run, "DONE", started)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        if run is not None:
            run["inputs"] = register_inputs(args.output)
            finish_run(args.output, run, "FAILED", started, exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
