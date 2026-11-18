"""Reconstruct PR 143 B2 releases and evaluate PR 145 excursion timing for two holdout seeds."""
import argparse
import bisect
import collections
import csv
import gzip
import hashlib
import io
import json
import math
import subprocess
from pathlib import Path

SOURCE = "01e588021e7e3ddd918b1d1fc9561973373758c6"
RATE = 20
END = 64 * RATE
AL = 0.10
SEEDS = (2026111901, 2026111902)
SCENES = ("nominal", "wall")
LIMITS = (1, 2, 5)
OUTCOMES = ("timely_alarm", "recovered_before_or_at_deadline", "right_censored_before_deadline",
            "no_position_at_deadline", "exceed_available_at_deadline", "exceed_withheld_at_deadline")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_sources(repo):
    manifest = Path(__file__).with_name("source_sha256.txt").read_text().splitlines()
    sources = {}
    for line in manifest:
        expected, name = line.split()
        path = repo / name
        if path.is_file():
            data = path.read_bytes()
            require(hashlib.sha256(data).hexdigest() == expected, f"Working copy differs: {name}")
        else:
            data = subprocess.check_output(["git", "-C", str(repo), "show", f"{SOURCE}:{name}"])
            require(hashlib.sha256(data).hexdigest() == expected, f"Git blob differs: {name}")
        key = (path.parent.name, path.name)
        sources[key] = gzip.decompress(data).decode("utf-8")
    return sources


def validate_ticks(rows, car, records, truth):
    require(len(rows) == len(truth) == END and len(records) == 63, "Unexpected run length")
    release = []
    for record in records:
        release.append(max(record["cutoff"], release[-1] if release else 0) + record["b2_cost"])
    for i, row in enumerate(rows):
        now = i / RATE
        j = bisect.bisect_right(release, now) - 1
        xy = None
        if j < 0:
            status = "STARTUP"
            require(row["state_s"] == row["ready_s"] == "", f"Early release: {now}")
        else:
            r = records[j]
            require(int(row["state_s"]) == r["t"] and float(row["ready_s"]) == release[j], f"Clock: {now}")
            if release[j] > r["t"] + 2:
                status = "LATE"
            elif now > r["t"] + 2:
                status = "EXPIRED"
            else:
                xy = r["xy"][car - 1]
                dec = r["b2"][car - 1]
                status = "NO_DECISION"
                if r["pub_ready"] and dec["computable"]:
                    status = "ALARM" if dec["alarm"] else "AVAILABLE"
        require(float(row["time_s"]) == now and row["status"] == status, f"Declaration: {now}")
        if xy is None:
            require(row["x_m"] == row["y_m"] == row["error_m"] == "", f"Missing position: {now}")
        else:
            require(xy == [float(row["x_m"]), float(row["y_m"])], f"Displayed position: {now}")
            require(math.isclose(math.dist(xy, truth[i][car-1]), float(row["error_m"]),
                                 rel_tol=0, abs_tol=1e-12), f"Position error: {now}")


def excursions(rows):
    events = []
    active = None
    for i, row in enumerate(rows):
        error = float(row["error_m"]) if row["error_m"] else None
        if error is None:
            continue
        if error <= AL:
            if active is not None:
                active.update(end=i, reason="OBSERVED_WITHIN_AL")
                active = None
            continue
        if active is None:
            active = dict(start=i, initial=row["status"], alarm=None, exposed=0, end=len(rows), reason="CENSORED")
            events.append(active)
        if row["status"] == "ALARM" and active["alarm"] is None:
            active["alarm"] = i
        active["exposed"] += row["status"] == "AVAILABLE"
    return events


def classify(event, deadline, rows):
    if event["alarm"] is not None and event["alarm"] <= deadline:
        return "timely_alarm"
    if event["reason"] == "OBSERVED_WITHIN_AL" and event["end"] <= deadline:
        return "recovered_before_or_at_deadline"
    if deadline >= len(rows):
        return "right_censored_before_deadline"
    if not rows[deadline]["error_m"]:
        return "no_position_at_deadline"
    if rows[deadline]["status"] == "AVAILABLE":
        return "exceed_available_at_deadline"
    return "exceed_withheld_at_deadline"


def seconds(tick):
    return None if tick is None else tick / RATE


def wall_window(rows, events, seed, car):
    window = range(24*RATE, 38*RATE)
    first = next((i for i in window if rows[i]["error_m"] and float(rows[i]["error_m"]) > AL), None)
    alarm = None
    event = None
    if first is not None:
        alarm = next((i for i in range(first, window.stop) if rows[i]["status"] == "ALARM"), None)
        event = next(e for e in events if e["start"] <= first < e["end"])
    return dict(seed=seed, car=car, first_observed_exceed_in_fault_s=seconds(first),
                alarm_in_window_s=seconds(alarm),
                window_delay_s=seconds(alarm-first) if alarm is not None else None,
                status_at_first=rows[first]["status"] if first is not None else "",
                episode_start=seconds(event["start"]) if event is not None else None,
                episode_first_alarm=seconds(event["alarm"]) if event is not None else None)


def evaluate(repo):
    sources = read_sources(repo)
    summary, details, walls = [], [], []
    for seed in SEEDS:
        for scene in SCENES:
            run = f"{seed}_{scene}"
            records = json.loads(sources[run, "records.json.gz"])
            truth = json.loads(sources[run, "truth.json.gz"])
            ticks = list(csv.DictReader(io.StringIO(sources[run, "ticks.csv.gz"])))
            for car in (1, 2):
                rows = [r for r in ticks if r["car"] == str(car) and r["view"] == "delivery"
                        and r["method"] == "B2" and float(r["AL_m"]) == AL]
                validate_ticks(rows, car, records, truth)
                events = excursions(rows)
                if scene == "wall":
                    walls.append(wall_window(rows, events, seed, car))
                for limit in LIMITS:
                    counts = collections.Counter()
                    for number, e in enumerate(events, 1):
                        deadline = e["start"] + RATE * limit
                        outcome = classify(e, deadline, rows)
                        counts[outcome] += 1
                        details.append(dict(seed=seed, scene=scene, car=car, episode=number,
                            first_exceed_s=seconds(e["start"]), status_at_start=e["initial"], stop_s=seconds(e["end"]),
                            stop_reason=e["reason"], first_alarm_s=seconds(e["alarm"]), tta_s=limit,
                            deadline_s=seconds(deadline), outcome=outcome, available_exceed_s=seconds(e["exposed"])))
                    summary.append(dict(seed=seed, scene=scene, car=car, tta_s=limit, ticks=len(rows),
                        available_s=seconds(sum(r["status"] == "AVAILABLE" for r in rows)),
                        exceed_available_s=seconds(sum(e["exposed"] for e in events)), episodes=len(events),
                        available_at_start=sum(e["initial"] == "AVAILABLE" for e in events),
                        alarmed_anytime=sum(e["alarm"] is not None for e in events),
                        **{k: counts[k] for k in OUTCOMES}))
    return {"summary.csv":summary, "events_by_tta.csv":details, "wall_window.csv":walls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="Repository or archived directory at the repository root")
    parser.add_argument("--out", required=True, type=Path, help="Directory for the three output tables")
    args = parser.parse_args()
    results = evaluate(args.repo.resolve())
    args.out.mkdir(parents=True, exist_ok=True)
    for name, rows in results.items():
        with (args.out/name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    print("Verified 10,240 vehicle-clock B2 samples. Wrote", ", ".join(results))


if __name__ == "__main__":
    main()
