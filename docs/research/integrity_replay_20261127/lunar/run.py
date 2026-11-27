"""Generate and score all 12 primary lunar replays and the three screen controls."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import os
from pathlib import Path

# Tiny dense systems are more reproducible with a single BLAS thread per worker.
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS"):
    os.environ[key] = "1"

from generate import TERRAIN_RELATIVE_PATH, build as build_primary, table
from replay import score_record, summarise
from screen import build as build_screen


def verify(summary):
    """Check the reference run's (requested, passed, issued, breached) counts per rover."""
    expected = {
        "main": (1092, 954, 1035, 1076, (40, 0)),
        "screen_all_epochs": (273, 273, 205, 273, (20, 0)),
        "screen_blocked_epochs": (66, 66, 0, 66, (None, None)),
    }
    for row in summary:
        n, ss, nine, selective, nine_breaches = expected[row["suite"]]
        if row["method"] == "ss_only":
            values = (n, ss, 0, None)
        elif row["method"] == "nine_bias_innovation":
            values = (n, nine, nine, nine_breaches[row["rover"]-1])
        else:
            values = (n, selective, selective, 0)
        observed = tuple(row[k] for k in ("requested", "detector_passes", "issued", "exceeded"))
        if observed != values:
            raise RuntimeError(f"{row['suite']}/{row['method']}/rover {row['rover']}: {observed} != {values}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path,
                        help="Local project checkout containing docs/research/lunar_end_to_end/continuous")
    parser.add_argument("--out", type=Path, required=True, help="New or empty output directory")
    parser.add_argument("--jobs", type=int, default=1, help="Separate replay workers (default: 1)")
    parser.add_argument("--check", action="store_true", help="Verify source-epoch counts against the reference")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    output = args.out.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error("choose a new or empty output directory to keep existing results")
    source = args.repo_root.resolve() / TERRAIN_RELATIVE_PATH
    if not all((source / name).is_file() for name in ("terrain.npz", "CLOUD_SUPPORT.npz")):
        parser.error(f"required project terrain inputs missing under {source}")
    primary = output / "primary_inputs"
    screen = output / "screen_inputs"
    build_primary(source, primary)
    build_screen(source, primary, screen)
    jobs = [(suite, path, root / "reference" / path.name)
            for suite, root in (("main", primary), ("screen", screen))
            for path in sorted((root / "observations").glob("*.json.gz"))]
    if len(jobs) != 15:
        raise ValueError(f"expected 15 synthetic records, found {len(jobs)}")
    print("Generated 12 primary replays and 3 screen controls. Scoring source epochs.", flush=True)
    if args.jobs == 1:
        records = [score_record(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            records = list(pool.map(score_record, jobs))
    rows = [row for record in records for row in record]
    summary = summarise(rows)
    table(output / "source_coverage.csv", summary)
    with gzip.open(output / "source_epochs.csv.gz", "wt", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if args.check:
        verify(summary)
        print("Verified all 18 method/rover/experiment count rows.")
    print(output / "source_coverage.csv")


if __name__ == "__main__":
    main()
