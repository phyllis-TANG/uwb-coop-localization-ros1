#!/usr/bin/env python3
"""Read PR45 normalized tables and replay three fixed arrival-causal baselines.

Field mode accepts development experiments only and has no accuracy-evaluation
interface. Unknown room initialization/extrinsics/clocks produce BLOCKED outputs.
The source-frame odometry baseline can still run without those room conditions.
"""
import argparse
from collections import Counter
import copy
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import model

PARENT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
SESSION = ROOT/"docs/field_tests/20261024_25"
sys.path.insert(0, str(PARENT))
from development import verify_normalized
from prepare import validate_data_root
from run_nightly import atomic_json, sha256, git_info

DEVELOPMENT = {"T08", "T10", "T12", "T14"}
ESTIMATE_COLUMNS = ["experiment_id", "method_id", "vehicle_id", "canonical_time_s", "frame_id",
    "x_m", "y_m", "z_m", "yaw_rad", "valid", "diagnostic_id", "source_version", "config_version", "reference_version",
    "publish_receive_epoch_ns", "state_epoch_ns", "source_header_epoch_ns", "source_receive_epoch_ns",
    "source_record_index", "pose_reference_point", "fallback_status", "receipt_age_ns", "pose_covariance"]


def event_key(event):
    r = event["row"]
    return (int(r["receive_epoch_ns"]), int(r["record_index"]), int(r.get("link_index") or 0))


def read_events(normalized, experiment, config, manifest):
    if experiment not in DEVELOPMENT:raise ValueError("whole-bag holdout gate: development input only")
    row = next(r for r in manifest["formal_bags"] if r["id"] == experiment)
    events = []
    counts = Counter()
    ready = model.readiness(config)
    range_needed = any(not ready[m][c] for m in ("independent", "joint") for c in model.CARS)
    for kind, name in [("odom", "odom.csv")]+([("range", "ranges.csv")] if range_needed else []):
        with (normalized/name).open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            required = {"experiment_id", "vehicle_id", "record_index", "receive_epoch_ns", "header_epoch_ns", "source_file_sha256"}
            if not required.issubset(reader.fieldnames or []):raise ValueError("missing normalized columns: "+name)
            for item in reader:
                if item["experiment_id"] != experiment:continue
                if item["source_file_sha256"] != row["sha256"]:raise ValueError("input bag identity mismatch")
                if item["vehicle_id"] not in model.CARS:raise ValueError("unknown vehicle")
                for field in ("record_index", "receive_epoch_ns", "header_epoch_ns"):
                    item[field] = int(item[field])
                if kind == "range":item["link_index"] = int(item["link_index"])
                events.append({"kind": kind, "row": item})
                counts[kind] += 1
                if len(events) > config["max_events"]:raise ValueError("event budget exceeded")
    events.sort(key=event_key)
    return events, dict(counts), {"range_tables_ingested": range_needed,
        "range_skip_reason": None if range_needed else "all room range-based methods BLOCKED before ingestion"}


def replay_events(events, config, experiment, origin_ns, end_ns, config_hash="unsaved", deadline=None):
    """Yield one publication at a time; no future rows reach any estimator."""
    model.validate_config(config)
    if config["scope"] == "field" and experiment not in DEVELOPMENT:
        raise ValueError("whole-bag holdout gate: development replay only")
    engines = {m: model.Baseline(m, config) for m in model.METHODS}
    events = sorted(events, key=event_key)
    if len(events) > config["max_events"]:raise ValueError("event budget exceeded")
    if end_ns < origin_ns:raise ValueError("negative replay span")
    ticks = list(range(origin_ns, end_ns+1, config["publish_period_ns"]))
    if not ticks or ticks[-1] != end_ns:ticks.append(end_ns)
    pointer = 0
    for tick_index, tick in enumerate(ticks):
        if deadline is not None and time.monotonic() >= deadline:raise TimeoutError("run wall-time budget exhausted")
        decisions = []
        while pointer < len(events) and int(events[pointer]["row"]["receive_epoch_ns"]) <= tick:
            if pointer % 256 == 0 and deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("run wall-time budget exhausted during event batch")
            event = events[pointer]
            pointer += 1
            for method, engine in engines.items():
                detail = engine.process(event)
                detail["method_id"] = method
                detail["admitted_at_publication_ns"] = tick
                decisions.append(detail)
        rows, diagnostics = [], {"diagnostic_id": str(tick_index), "publish_receive_epoch_ns": tick,
                                  "input_events_consumed": pointer, "methods": {}}
        for method, engine in engines.items():
            states = engine.snapshot(tick)
            diagnostics["methods"][method] = {"vehicles": states, "cumulative_event_status": dict(engine.counts)}
            for car, state in states.items():
                pose = state["pose"]
                rows.append(dict(experiment_id=experiment, method_id=method, vehicle_id=car,
                    canonical_time_s=(tick-origin_ns)/1e9, frame_id=state["frame_id"],
                    x_m=pose[0] if pose else None, y_m=pose[1] if pose else None, z_m=None,
                    yaw_rad=pose[2] if pose else None, valid=int(state["valid"]), diagnostic_id=str(tick_index),
                    source_version="synthetic_normalized_fixture_v1" if config["scope"] == "synthetic" else "pr45_normalized_v1", config_version=config_hash, reference_version="none_not_used",
                    publish_receive_epoch_ns=tick, state_epoch_ns=state.get("state_epoch_ns"),
                    source_header_epoch_ns=state.get("source_header_epoch_ns"), source_receive_epoch_ns=state.get("source_receive_epoch_ns"),
                    source_record_index=state.get("source_record_index"), pose_reference_point="base_footprint",
                    fallback_status=state["fallback_status"], receipt_age_ns=state.get("receipt_age_ns"),
                    pose_covariance=state["covariance"]))
        yield rows, diagnostics, decisions


def create_run(output, config_path, argv):
    output = validate_data_root(output)
    output.mkdir(parents=True, exist_ok=False)
    git = git_info()
    sources = list(Path(__file__).parent.glob("*.py"))
    sources += [PARENT/p for p in ("normalize.py", "development.py", "prepare.py", "run_nightly.py")]
    packages = subprocess.run([sys.executable, "-m", "pip", "freeze"], check=True, capture_output=True, text=True).stdout
    (output/"python_packages.txt").write_text(packages)
    run = {"schema_version": 1, "run_id": output.name, "role": "causal_baselines", "status": "IN_PROGRESS",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "code_commit": git["head"],
        "branch": git["branch"], "worktree_dirty": bool(git["status_porcelain"]),
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sorted(set(sources))},
        "config_sha256": {config_path.name: sha256(config_path), "manifest.json": sha256(SESSION/"manifest.json"), "geometry.json": sha256(SESSION/"geometry.json")},
        "command_argv": argv, "inputs": [], "outputs": [], "blocked_reasons": [],
        "environment": {"python": sys.version, "packages_file": "python_packages.txt"},
        "limitations": ["fixed engineering covariance; not independently calibrated", "no field localization error evaluation", "no IMU independence assumption"],
        "publications_completed": 0}
    atomic_json(output/"run.json", run)
    return run


def finish(output, run, status, started, error=None):
    run.update(status=status, elapsed_s=time.monotonic()-started,
               finished_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    if error is not None:run["error"] = str(error)
    run["outputs"] = [{"relative_path": str(p.relative_to(output)), "sha256": sha256(p)}
                      for p in sorted(output.rglob("*")) if p.is_file() and p.name != "run.json"]
    atomic_json(output/"run.json", run)


def write_replay(output, events, config, experiment, origin, end, run, deadline):
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, allow_nan=False).encode()).hexdigest()
    atomic_json(output/"config.json", config)
    ready = model.readiness(config)
    atomic_json(output/"readiness.json", {"methods": ready, "independent_reference_required_for_code": False,
        "field_accuracy_evaluation": "BLOCKED: independent spatial/time reference not accepted",
        "experiment_notes": config.get("experiment_notes", {})})
    summary = {"experiment_id": experiment, "methods": {}, "input_events": len(events), "estimates": 0,
               "accuracy_evaluation_performed": False, "publication_state_policy": "hold last odometry-anchored posterior; per-vehicle state time recorded"}
    last_diagnostic = None
    state_counts = {m: {c: {"rows":0, "valid_rows":0, "fallback_counts":Counter()} for c in model.CARS} for m in model.METHODS}
    with (output/"estimate.csv").open("x", newline="") as estimates, (output/"tick_diagnostics.jsonl").open("x") as diagnostics, (output/"observations.jsonl").open("x") as observations:
        writer = csv.DictWriter(estimates, fieldnames=ESTIMATE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for rows, diag, decisions in replay_events(events, config, experiment, origin, end, config_hash, deadline):
            for row in rows:
                count = state_counts[row["method_id"]][row["vehicle_id"]]
                count["rows"] += 1
                count["valid_rows"] += row["valid"]
                count["fallback_counts"][row["fallback_status"]] += 1
                row = dict(row)
                row["pose_covariance"] = json.dumps(row["pose_covariance"], allow_nan=False) if row["pose_covariance"] is not None else None
                writer.writerow(row)
            diagnostics.write(json.dumps(diag, allow_nan=False)+"\n")
            for decision in decisions:observations.write(json.dumps(decision, allow_nan=False)+"\n")
            run["publications_completed"] += 1
            summary["estimates"] += len(rows)
            last_diagnostic = diag
            if run["publications_completed"] % 100 == 0:
                estimates.flush();diagnostics.flush();observations.flush()
                atomic_json(output/"run.json", run)
    for method in model.METHODS:
        blocked = ready[method]
        summary["methods"][method] = {"status": "BLOCKED" if all(blocked[c] for c in model.CARS) else "PARTIAL" if any(blocked[c] for c in model.CARS) else "DONE",
            "blocked_reasons": blocked, "states":state_counts[method],
            "events": last_diagnostic["methods"][method]["cumulative_event_status"] if last_diagnostic else {}}
    atomic_json(output/"diagnostics.json", summary)
    run["blocked_reasons"] = sorted({reason for method in ready.values() for reasons in method.values() for reason in reasons})
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--experiment", required=True, choices=sorted(DEVELOPMENT))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=600)
    args = parser.parse_args(argv)
    started = time.monotonic();run = None
    try:
        if not 0 < args.max_seconds <= 21600:raise ValueError("maximum run time is six hours")
        run = create_run(args.output, args.config, [sys.executable, __file__]+(list(argv) if argv is not None else sys.argv[1:]))
        config = json.loads(args.config.read_text())
        if config["scope"] != "field":raise ValueError("real-data replay requires explicit field config; synthetic config is forbidden")
        model.validate_config(config)
        notes = config.get("experiment_notes", {})
        config["experiment_notes"] = notes.get(args.experiment, [])
        normalized = verify_normalized(args.normalized)
        manifest = json.loads((SESSION/"manifest.json").read_text())
        item = next(r for r in manifest["formal_bags"] if r["id"] == args.experiment)
        if item["split"] != "development":raise ValueError("whole-bag holdout gate")
        run["inputs"] = [{"asset_id": "normalized", "relative_path": "run.json", "sha256": sha256(args.normalized/"run.json")},
            *[dict(r) for r in normalized["outputs"] if r["relative_path"] in ("odom.csv", "ranges.csv")],
            {"asset_id": "bags", "relative_path": item["relative_path"], "sha256": item["sha256"]}]
        events, counts, ingestion = read_events(args.normalized, args.experiment, config, manifest)
        run["ingestion"] = dict(ingestion, selected_event_counts=counts)
        summary = write_replay(args.output, events, config, args.experiment, item["first_bag_receive_epoch_ns"], item["last_bag_receive_epoch_ns"], run, started+args.max_seconds)
        status = "BLOCKED" if run["blocked_reasons"] else "DONE"
        finish(args.output, run, status, started)
        print(json.dumps({"status": status, "methods": summary["methods"], "estimates": summary["estimates"]}))
        return 2 if status == "BLOCKED" else 0
    except (Exception, KeyboardInterrupt) as error:
        if run is not None:finish(args.output, run, "FAILED", started, error)
        print("ERROR: "+str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":sys.exit(main())
