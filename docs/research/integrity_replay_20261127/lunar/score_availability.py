"""Replay 20 Hz service availability and recovery from run.py's source_epochs.csv.gz."""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import gzip
import math
from pathlib import Path

PERIOD = 0.05
DURATION = 90
EXPIRY = 2.0
METHODS = ("nine_bias_innovation", "iterative")
MAIN_RUNS = {f"L{layout}_{case}_S{seed}" for layout in (1, 2)
             for case in ("N", "F") for seed in (1, 2, 3)}
SCREEN_RUNS = {f"L1_B_S{seed}" for seed in (1, 2, 3)}


@dataclass(frozen=True)
class Update:
    source: float
    wall: float
    radius: float | None


def load_updates(path):
    traces = defaultdict(list)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["method"] == "ss_only":
                continue  # A detector-only pass carries no numerical protection level.
            key = row["suite"], row["run"], row["method"], int(row["rover"])
            t = float(row["t_s"])
            cost = float(row["wall_s"])
            radius = float(row["hpl_m"]) if row["hpl_m"] else None
            if row["accepted"] not in ("True", "False"):
                raise ValueError(f"Unexpected acceptance flag at {key}, time {t}")
            if (row["accepted"] == "True") != (radius is not None):
                raise ValueError(f"Expected a radius exactly when the monitor accepts at {key}, time {t}")
            if not math.isfinite(cost) or cost < 0 or (
                    radius is not None and (not math.isfinite(radius) or radius < 0)):
                raise ValueError(f"Invalid runtime or radius at {key}, time {t}")
            traces[key].append(Update(t, cost, radius))

    expected = {(suite, run, method, rover)
                for suite, runs in (("main", MAIN_RUNS), ("screen", SCREEN_RUNS))
                for run in runs for method in METHODS for rover in (1, 2)}
    if traces.keys() != expected:
        raise ValueError("Expected both numerical monitors and both rovers for all 15 runs")
    for key, updates in traces.items():
        updates.sort(key=lambda u: u.source)
        if [u.source for u in updates] != list(range(DURATION + 1)):
            raise ValueError(f"Expected each 1 Hz epoch from 0 to 90 exactly once for {key}")
    return traces


def display_trace(updates, delay, speed):
    """Each tuple is (source, disposition, aged radius) on a complete display tick."""
    receipts = []
    finish = -math.inf
    for update in updates:
        finish = max(finish, update.source + delay) + update.wall
        receipts.append(finish + delay)

    ticks = []
    for i in range(round(DURATION / PERIOD)):
        now = i * PERIOD
        index = bisect_right(receipts, now) - 1
        if index < 0:
            ticks.append((None, "waiting", None))
            continue
        u = updates[index]
        age = now - u.source
        if age > EXPIRY + 1e-12:
            ticks.append((u.source, "expired", None))
        elif u.radius is None:
            ticks.append((u.source, "rejected", None))
        else:
            ticks.append((u.source, "issued", u.radius + speed * age))
    return ticks


def disposition_counts(ticks, limit):
    counts = Counter()
    for _, status, radius in ticks:
        if radius is not None:
            status = "available" if radius <= limit else "above_limit"
        counts[status] += 1
    return counts


def recovery(ticks, onset, removal, limit):
    """Classify service interruption and time its restoration only when eligible."""
    start = round(onset / PERIOD)
    stop = round(removal / PERIOD)
    ok = [radius is not None and radius <= limit for _, _, radius in ticks]
    after = next((i for i in range(stop, len(ticks))
                  if ok[i] and ticks[i][0] >= removal), None)
    if not any(ok[:start]):
        status = "no_pre_fault_service"
    elif not ok[start - 1]:
        status = "already_unavailable_at_onset"
    elif all(ok[start:stop]):
        status = "no_loss_in_fault_window"
    elif ok[stop - 1]:
        status = "service_returned_before_removal"
    elif after is None:
        status = "not_restored_during_observed_postwindow"
    else:
        status = "restored_after_removal"
    return dict(onset_s=onset, removal_s=removal, classification=status,
                first_service_from_new_post_source_s=None if after is None else round(after * PERIOD, 2),
                recovery_s=round((after - stop) * PERIOD, 2) if status == "restored_after_removal" else None)


def write_table(path, records):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def score(epochs, out, delay, speed, service_limit, recovery_limit):
    grouped = defaultdict(Counter)
    recoveries = []
    for (suite, run, method, rover), updates in sorted(load_updates(epochs).items()):
        ticks = display_trace(updates, delay, speed)
        grouped[suite, method, rover].update(disposition_counts(ticks, service_limit))
        case = run.split("_")[1]
        if case in ("F", "B"):
            onset, removal = (30, 60) if case == "F" else (33, 55)
            recoveries.append(dict(suite=suite, run=run, method=method, rover=rover,
                                   delay_each_way_s=delay, speed_bound_mps=speed, limit_m=recovery_limit,
                                   **recovery(ticks, onset, removal, recovery_limit)))

    summaries = []
    for (suite, method, rover), counts in sorted(grouped.items()):
        total = sum(counts.values())
        summaries.append(dict(suite=suite, method=method, rover=rover,
                              delay_each_way_s=delay, speed_bound_mps=speed, limit_m=service_limit,
                              total_ticks=total, available_ticks=counts["available"],
                              waiting_ticks=counts["waiting"], expired_ticks=counts["expired"],
                              rejected_ticks=counts["rejected"], above_limit_ticks=counts["above_limit"],
                              available_s=round(counts["available"] * PERIOD, 2),
                              availability_pct=100 * counts["available"] / total))
    out.mkdir(parents=True, exist_ok=True)
    write_table(out / "clock_availability.csv", summaries)
    write_table(out / "clock_recovery.csv", recoveries)


def nonnegative(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("expected a finite nonnegative value")
    return number


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=Path, required=True, help="source_epochs.csv.gz produced by run.py")
    parser.add_argument("--out", type=Path, required=True, help="Directory for clock CSV outputs")
    parser.add_argument("--delay-s", type=nonnegative, default=0.02, help="Assumed transport delay in each direction")
    parser.add_argument("--speed-bound", type=nonnegative, default=0.25, help="Assumed horizontal speed bound in m/s")
    parser.add_argument("--service-limit-m", type=nonnegative, default=1.0)
    parser.add_argument("--recovery-limit-m", type=nonnegative, default=1.5)
    args = parser.parse_args()
    score(args.epochs, args.out, args.delay_s, args.speed_bound, args.service_limit_m, args.recovery_limit_m)
