#!/usr/bin/env python3
"""Bounded, resumable offline QC/regression jobs; never starts ROS or hardware."""
import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "docs/field_tests/20261024_25"
MANIFEST = SESSION / "manifest.json"
GEOMETRY = SESSION / "geometry.json"
HOLDOUTS = {"T09", "T11", "T13", "T15"}
REGRESSIONS = [
    "test_october_field_session.py", "test_single_car_sequential_replay.py",
    "test_single_car_fixed_lag.py", "test_two_car_offline_graph.py",
    "test_two_car_updated_comparison.py", "test_two_car_stationary_confidence.py",
    "test_two_car_range_confidence.py", "test_single_car_integrity.py",
    "test_single_car_integrity_worker_io.py", "test_integrity_evaluation.py",
    "test_two_car_independent_integrity.py",
]


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


def within(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def safe_relative(value):
    p = PurePosixPath(value)
    return isinstance(value, str) and bool(value) and not p.is_absolute() and ".." not in p.parts and "\\" not in value


def validate_configuration(manifest_path=MANIFEST, geometry_path=GEOMETRY):
    m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    g = json.loads(Path(geometry_path).read_text(encoding="utf-8"))
    if m.get("schema_version") != 1 or g.get("schema_version") != 1:
        raise ValueError("unsupported manifest/geometry schema_version")
    ids = [a["id"] for a in m["assets"]]
    if len(ids) != len(set(ids)) or "bags" not in ids:
        raise ValueError("asset IDs must be unique and contain bags")
    for asset in m["assets"]:
        if not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
            raise ValueError("invalid asset SHA256")
        if not isinstance(asset["size_bytes"], int) or asset["size_bytes"] <= 0:
            raise ValueError("asset size must be positive")
        if not safe_relative(asset["name"]) or "/" in asset["name"] or not safe_relative(asset["extract_subdir"]):
            raise ValueError("unsafe asset path")
    bags = m["formal_bags"]
    if {b["id"] for b in bags} != {"T%02d" % n for n in range(8, 16)} or len(bags) != 8:
        raise ValueError("formal bag identity set must be T08--T15")
    for bag in bags:
        if not safe_relative(bag["relative_path"]) or not re.fullmatch(r"[0-9a-f]{64}", bag["sha256"]):
            raise ValueError("unsafe bag path or invalid SHA256")
        expected = "holdout" if bag["id"] in HOLDOUTS else "development"
        if bag["split"] != expected:
            raise ValueError("whole-bag development/holdout split changed: " + bag["id"])
        if not isinstance(bag["expected_messages"], int) or bag["expected_messages"] <= 0:
            raise ValueError("invalid expected message count")
    marker = g["marker"]
    if marker["dictionary"] != "DICT_4X4_50" or abs(marker["black_border_side_m"] - .144) > 1e-9:
        raise ValueError("expected measured 144mm DICT_4X4_50 marker")
    if marker["id_mapping"]["car1"] != {"visual_id": 0, "uwb_tag_id": "node_1"} or marker["id_mapping"]["car2"] != {"visual_id": 1, "uwb_tag_id": "node_0"}:
        raise ValueError("visual/UWB identity mapping changed")
    return m, g


def build_jobs(python=sys.executable):
    jobs = [{"id": "configuration", "command": [python, str(Path(__file__).resolve()), "--check-config"], "timeout_s": 60, "depends_on": []}]
    jobs.append({"id": "field_tools_tests", "command": [python, "-m", "unittest", "discover", "-s", "tools/field_20261024_25", "-p", "test_*.py", "-v"], "timeout_s": 300, "depends_on": []})
    for filename in REGRESSIONS:
        jobs.append({"id": filename[:-3], "command": [python, "-m", "unittest", "discover", "-s", "tools", "-p", filename, "-v"], "timeout_s": 600, "depends_on": []})
    jobs.append({"id": "bag_qc", "command": [python, "tools/field_20261024_25/audit_bags.py", "--data-root", "{data_root}", "--output", "{job_output}"], "timeout_s": 1800, "depends_on": ["configuration"], "requires_bags": True, "artifacts": ["bag_qc.json", "BAG_QC_REPORT.md"]})
    return jobs


def git_info():
    def read(args):
        r = subprocess.run(["git"] + args, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return r.stdout.strip() if r.returncode == 0 else None
    return {"head": read(["rev-parse", "HEAD"]), "branch": read(["branch", "--show-current"]), "status_porcelain": read(["status", "--porcelain"])}


def provenance(data_root, jobs):
    source_paths = list((ROOT / "tools").glob("*.py")) + list((ROOT / "tools/field_20261024_25").glob("*.py"))
    # Historical synthetic fixtures used by the selected regression modules.
    source_paths += [ROOT / p for p in [
        "docs/field_tests/integrity_feasibility_v1_20261022/protocol.json",
        "docs/field_tests/two_car_updated_comparison_20261022/protocol.json",
        "docs/field_tests/two_car_updated_comparison_20261022/results/calibration.json",
        "docs/field_tests/integrity_feasibility_v1_1_20261022/estimator_config.json",
    ]]
    sources = {str(p.relative_to(ROOT)): sha256(p) for p in sorted(set(source_paths)) if p.is_file()}
    # Field diagnostics and synthetic adapters now have explicit JSON policies.
    # Their changes must also invalidate a resume of the field-tools tests.
    config_paths = [MANIFEST, GEOMETRY] + sorted((ROOT / "tools/field_20261024_25").glob("*.json"))
    configs = {str(p.relative_to(ROOT)): sha256(p) for p in config_paths if p.is_file()}
    inputs = []
    bag_errors = []
    try:
        m, _ = validate_configuration()
        for bag in m["formal_bags"]:
            path = data_root / "extracted/bags" / bag["relative_path"]
            row = {"id": bag["id"], "relative_path": bag["relative_path"], "expected_sha256": bag["sha256"]}
            if not within(path, data_root) or not path.is_file():
                row["status"] = "missing"
                bag_errors.append(bag["id"] + ": input missing")
            else:
                row["sha256"] = sha256(path)
                row["status"] = "verified" if row["sha256"] == bag["sha256"] else "hash_mismatch"
                if row["status"] != "verified":
                    bag_errors.append(bag["id"] + ": input hash mismatch")
            inputs.append(row)
    except (ValueError, KeyError, TypeError, OSError) as error:
        bag_errors.append("configuration invalid: " + str(error))
    versions = {}
    for package in ["numpy", "scipy", "matplotlib", "rosbags"]:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    git = git_info()
    identity = {"source_sha256": sources, "configuration_sha256": configs, "inputs": inputs,
                "git_head": git["head"], "python": sys.version, "executable": sys.executable,
                "package_versions": versions, "jobs": jobs}
    return {"fingerprint": digest_json(identity), "identity": identity, "git": git,
            "platform": platform.platform(), "bag_preconditions": bag_errors}


def completed_artifacts_valid(result, output):
    if result.get("status") != "PASSED" or not result.get("artifact_sha256"):
        return False
    for name, expected in result["artifact_sha256"].items():
        p = output / name
        if not safe_relative(name) or not within(p, output) or not p.is_file() or sha256(p) != expected:
            return False
    return True


def execute_job(job, data_root, output, attempt, remaining_s, popen=subprocess.Popen):
    directory = output / "jobs" / job["id"] / ("attempt_%04d" % attempt)
    directory.mkdir(parents=True, exist_ok=False)
    artifact_dir = directory / "artifacts"
    stdout = directory / "stdout.log"
    stderr = directory / "stderr.log"
    command = [x.replace("{data_root}", str(data_root)).replace("{job_output}", str(artifact_dir)) for x in job["command"]]
    timeout = min(float(job["timeout_s"]), float(remaining_s))
    result = {"id": job["id"], "attempt": attempt, "command": command, "started_utc": utc_now(), "timeout_s": timeout}
    start = time.monotonic()
    env = dict(os.environ)
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MPLBACKEND": "Agg", "PYTHONUNBUFFERED": "1"})
    process = None
    try:
        with stdout.open("wb") as out, stderr.open("wb") as err:
            process = popen(command, cwd=str(ROOT), env=env, stdout=out, stderr=err, start_new_session=(os.name == "posix"))
            result["returncode"] = process.wait(timeout=timeout)
        result["status"] = "PASSED" if result["returncode"] == 0 else "FAILED"
    except subprocess.TimeoutExpired:
        if process is not None:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()
        result.update({"status": "TIMED_OUT", "returncode": None})
    except KeyboardInterrupt:
        if process is not None:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()
        result.update({"status": "INTERRUPTED", "returncode": None})
    except OSError as error:
        result.update({"status": "FAILED", "returncode": None, "error": str(error)})
    result["finished_utc"] = utc_now()
    result["elapsed_s"] = time.monotonic() - start
    artifacts = [stdout, stderr]
    if result["status"] == "PASSED":
        for name in job.get("artifacts", []):
            p = artifact_dir / name
            if not p.is_file():
                result["status"] = "FAILED"
                result["error"] = "expected task artifact missing: " + name
            else:
                artifacts.append(p)
    result["artifact_sha256"] = {str(p.relative_to(output)): sha256(p) for p in artifacts if p.is_file()}
    return result


def append_event(output, event):
    with (output / "tasks.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def checkpoint(output, state):
    atomic_json(output / "run.json", state)
    lines = ["# Offline nightly job summary", "", "Status: **{}**".format(state["status"]),
             "", "Fingerprint: `{}`".format(state["provenance"]["fingerprint"]),
             "", "Deadline (UTC): `{}`".format(state["deadline_utc"]), "",
             "| Job | Status | Attempts | Last detail |", "| --- | --- | --- | --- |"]
    for job in state["plan"]:
        entry = state["tasks"].get(job["id"], {})
        lines.append("| {} | {} | {} | {} |".format(job["id"], entry.get("status", "PENDING"), len(entry.get("attempts", [])), entry.get("reason", "").replace("|", "/")))
    lines += ["", "These are offline health/regression checks, not localization accuracy or visual-reference acceptance.",
              "Historical synthetic test fixtures are not Oct25 calibration. No holdout error tuning is performed.",
              "Read per-attempt stdout.log/stderr.log and bag_qc artifacts before interpreting failures."]
    temporary = output / "summary.md.tmp"
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(output / "summary.md"))


@contextlib.contextmanager
def output_lock(output):
    if os.name != "posix":
        raise ValueError("nightly runner requires Linux/macOS/WSL for a process-safe output lock")
    import fcntl
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".run.lock").open("a") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("another nightly process owns this output directory") from error
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run_jobs(data_root, output, max_hours, resume=False, jobs=None, job_runner=execute_job, now=time.time):
    data_root, output = Path(data_root).expanduser().resolve(), Path(output).expanduser().resolve()
    if within(data_root, ROOT) or within(output, ROOT):
        raise ValueError("data and result directories must be outside the Git checkout")
    if within(output, data_root) or within(data_root, output):
        raise ValueError("raw data and nightly output directories must be separate")
    if not 0 < max_hours <= 6:
        raise ValueError("max-hours must be >0 and <=6")
    with output_lock(output):
        return _run_jobs_locked(data_root, output, max_hours, resume, jobs, job_runner, now)


def _run_jobs_locked(data_root, output, max_hours, resume, jobs, job_runner, now):
    jobs = build_jobs() if jobs is None else jobs
    if len(jobs) > 64 or len({j["id"] for j in jobs}) != len(jobs):
        raise ValueError("finite plan must have <=64 unique jobs")
    proof = provenance(data_root, jobs)
    state_path = output / "run.json"
    if resume:
        if not state_path.is_file():
            raise ValueError("--resume requires an existing run.json")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state["provenance"]["fingerprint"] != proof["fingerprint"]:
            raise ValueError("source/config/input/runtime fingerprint changed; keep this run and use a NEW output directory")
    else:
        if any(p.name != ".run.lock" for p in output.iterdir()):
            raise ValueError("output directory is nonempty; use --resume for the same frozen run")
        output.mkdir(parents=True, exist_ok=True)
        deadline = now() + max_hours * 3600
        state = {"schema_version": 1, "status": "RUNNING", "started_utc": utc_now(),
                 "deadline_epoch_s": deadline, "deadline_utc": dt.datetime.fromtimestamp(deadline, dt.timezone.utc).isoformat(),
                 "max_hours": max_hours, "provenance": proof, "plan": jobs, "tasks": {}}
    state["status"] = "RUNNING"
    checkpoint(output, state)
    for job in jobs:
        previous = state["tasks"].get(job["id"], {})
        attempts = previous.get("attempts", [])
        if attempts and completed_artifacts_valid(attempts[-1], output):
            previous["status"] = "PASSED"
            append_event(output, {"event": "resume_verified_skip", "id": job["id"], "utc": utc_now()})
            continue
        # A hard-killed orchestrator may leave an attempt directory without a
        # finished result. Keep it, count it toward the cap, and use a new path.
        existing = output / "jobs" / job["id"]
        highest = max([int(p.name.split("_")[-1]) for p in existing.glob("attempt_*") if p.name.split("_")[-1].isdigit()] or [0])
        while len(attempts) < highest:
            attempts.append({"id": job["id"], "attempt": len(attempts) + 1,
                             "status": "ABANDONED", "reason": "prior attempt directory had no completed checkpoint"})
        previous["attempts"] = attempts
        state["tasks"][job["id"]] = previous
        # At most two actual subprocess attempts across this run and its resumes.
        if len(attempts) >= 2:
            previous.update({"status": "FAILED", "reason": "two-attempt cap reached or completed artifacts changed"})
            continue
        remaining = state["deadline_epoch_s"] - now()
        if remaining <= 0:
            state["status"] = "BUDGET_EXHAUSTED"
            break
        dependency_errors = [key for key in job.get("depends_on", []) if state["tasks"].get(key, {}).get("status") != "PASSED"]
        reason = "dependency not passed: " + ", ".join(dependency_errors) if dependency_errors else None
        if job.get("requires_bags") and proof["bag_preconditions"]:
            reason = "; ".join(proof["bag_preconditions"])
        if reason:
            state["tasks"][job["id"]] = {"status": "BLOCKED", "reason": reason, "attempts": attempts}
            append_event(output, {"event": "blocked", "id": job["id"], "reason": reason, "utc": utc_now()})
            checkpoint(output, state)
            continue
        state["tasks"][job["id"]] = {"status": "RUNNING", "attempts": attempts}
        append_event(output, {"event": "started", "id": job["id"], "attempt": len(attempts) + 1, "utc": utc_now()})
        checkpoint(output, state)
        result = job_runner(job, data_root, output, len(attempts) + 1, remaining)
        attempts.append(result)
        state["tasks"][job["id"]] = {"status": result["status"], "attempts": attempts, "reason": result.get("error", "")}
        append_event(output, dict(result, event="finished"))
        checkpoint(output, state)
        if result["status"] == "INTERRUPTED":
            state["status"] = "INTERRUPTED"
            break
    if state["status"] == "RUNNING":
        statuses = [state["tasks"].get(j["id"], {}).get("status", "PENDING") for j in jobs]
        state["status"] = "FAILED" if any(s in {"FAILED", "TIMED_OUT", "INTERRUPTED"} for s in statuses) else "BLOCKED" if "BLOCKED" in statuses else "COMPLETE"
    state["updated_utc"] = utc_now()
    checkpoint(output, state)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, help="prepared data directory outside Git")
    parser.add_argument("--output", type=Path, help="nightly result directory outside Git and raw data")
    parser.add_argument("--max-hours", type=float, default=6, help="wall-clock budget, <=6h; a finite plan may finish sooner")
    parser.add_argument("--resume", action="store_true", help="reuse only a matching frozen run; original deadline remains")
    parser.add_argument("--plan-only", action="store_true", help="print finite job list without execution or downloads")
    parser.add_argument("--check-config", action="store_true", help="validate manifest/geometry/whole-run split only")
    args = parser.parse_args(argv)
    if args.plan_only:
        print(json.dumps({"jobs": build_jobs(), "network_downloads": False, "default_max_hours": args.max_hours}, indent=2))
        return 0
    if args.check_config:
        try:
            m, g = validate_configuration()
            print(json.dumps({"status": "pass", "formal_bags": len(m["formal_bags"]), "holdouts": sorted(HOLDOUTS), "geometry_status": g.get("status")}, indent=2))
            return 0
        except (OSError, ValueError, KeyError, TypeError) as error:
            print("Configuration check failed: " + str(error), file=sys.stderr)
            return 2
    if args.data_root is None or args.output is None:
        parser.error("--data-root and --output are required unless --plan-only/--check-config")
    try:
        state = run_jobs(args.data_root, args.output, args.max_hours, args.resume)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Nightly runner error: " + str(error), file=sys.stderr)
        return 2
    print("Nightly status: {}. Read {}".format(state["status"], args.output / "summary.md"))
    return {"COMPLETE": 0, "FAILED": 1, "BLOCKED": 2, "BUDGET_EXHAUSTED": 3, "INTERRUPTED": 130}.get(state["status"], 1)


if __name__ == "__main__":
    sys.exit(main())
