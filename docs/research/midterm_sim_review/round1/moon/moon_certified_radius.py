"""Read accepted #146 fine-grid certificates and bound per-car horizontal radii.

Inputs: a checkout of PR #146 at 00145cb01a809b325a928b3735ef1d9d62edf23a,
or its docs/research/lunar_end_to_end/radius_resolution directory.
Before use, validate the trees with that checkout's run.py --verify. This
post-processing script checks archive identity but does not verify leaf labels.

For the published center: maximum distance to an INSIDE corner is a lower
bound; maximum over all retained corners is an upper bound. For any center:
two INSIDE corners at distance d imply a lower bound of d/2. The two corners
may belong to different 4D boxes: both are feasible in the car's projection.
All extrema and threshold comparisons use exact squared rational distances.
Metres in the output are rounded only for display.
"""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
import sys
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path

DATA = Path("docs/research/lunar_end_to_end/radius_resolution")
# Digests of the four independently verified fine_matched.json.gz archives.
LOCK = {
    "main_start_normal": "0be83bfcbcd17c731e7d147f639364b3e8d04323bb395c497517f108e4d16c42",
    "main_mid_normal": "334287ed3a0b735e92eb2a3f28884b8e4c6129cd313f0eb778bbf566e2fa301c",
    "second_start_normal": "8b132e604f52841c09cd1bf942d3c87cfb0abf106b23b590e65a313e58e8d8e9",
    "second_mid_normal": "e0a1dc80a269dc4d60333d17180e205b2284afe934d4deb70e129fb06b148089",
}


def turn(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def hull(points):
    """Andrew's monotone chain; removing collinear interior vertices is safe."""
    ordered = sorted(points)
    if len(ordered) < 2:
        raise ValueError("Need at least two distinct INSIDE corners")

    def half(sequence):
        out = []
        for point in sequence:
            while len(out) >= 2 and turn(out[-2], out[-1], point) <= 0:
                out.pop()
            out.append(point)
        return out

    return half(ordered)[:-1] + half(reversed(ordered))[:-1]


def squared_distance(a, b):
    return (a[0]-b[0])**2 + (a[1]-b[1])**2


def metres(squared):
    return format(math.sqrt(float(squared)), ".9f")


def car_bounds(case, certificate, car, record):
    center = F(record["published_x"]), F(record["published_y"])
    offset = 0 if car == "p" else 2
    witnesses = {}

    @lru_cache(maxsize=None)
    def axis_bound(axis, low, high):
        return max(abs(F(low)-center[axis]), abs(F(high)-center[axis]))**2

    @lru_cache(maxsize=None)
    def corner_bound(x0, x1, y0, y1):
        return axis_bound(0, x0, x1) + axis_bound(1, y0, y1)

    inner2 = outer2 = F(0)
    for node in certificate["nodes"]:
        kind = node["kind"]
        if kind not in ("INSIDE", "UNDECIDED"):
            continue
        x, y = node["box"][offset:offset+2]
        bound2 = corner_bound(*x, *y)
        outer2 = max(outer2, bound2)
        if kind == "INSIDE":
            inner2 = max(inner2, bound2)
            for ix, iy in itertools.product(range(2), repeat=2):
                witnesses.setdefault((x[ix], y[iy]), (node["id"], f"{ix}{iy}"))

    points = {(F(x), F(y)): witness for (x, y), witness in witnesses.items()}
    vertices = hull(points)
    d2, a, b = max((squared_distance(a, b), a, b)
                   for a, b in itertools.combinations(vertices, 2))
    any2 = d2 / 4
    if abs(math.sqrt(float(outer2)) - float(record["fine_PL_m"])) > 1e-12:
        raise ValueError(f"Archived outer radius mismatch at {case}/{car}")
    target = F(1, 5)**2
    status20 = ("all_model_positions_fit" if outer2 <= target
                else "some_model_position_exceeds" if inner2 > target
                else "unresolved")
    return {
        "case": case, "car": car,
        "published_inner_m": metres(inner2), "published_outer_m": metres(outer2),
        "any_center_lower_m": metres(any2),
        "published_inner_gt_010": inner2 > F(1, 10)**2,
        "any_center_lower_gt_010": any2 > F(1, 10)**2,
        "published_020_status": status20,
        "inside_leaf_a": node_id(points[a][0]), "xy_corner_a": points[a][1],
        "inside_leaf_b": node_id(points[b][0]), "xy_corner_b": points[b][1],
        "pair_distance_sq_m2_exact": str(d2),
    }


def node_id(path):
    # Text prefix also preserves leading zeroes in spreadsheet viewers.
    return "path:" + path


def analyse(directory):
    table = directory / "paired.csv"
    table_hash = "c6797e9c0e92af1f74e39800f8a7111525915f3fd8d4cad2fe9a7a15eb56cb0f"
    if hashlib.sha256(table.read_bytes()).hexdigest() != table_hash:
        raise ValueError("Published-center table differs from verified PR #146")
    with table.open(newline="") as source:
        paired = {(r["case"], r["car"]): r for r in csv.DictReader(source)}
    if set(paired) != set(itertools.product(LOCK, "ps")):
        raise ValueError("Expected the eight registered case/car pairs")
    for case, digest in LOCK.items():
        archive = directory / "results" / case / "fine_matched.json.gz"
        raw = archive.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"Archive differs from verified PR #146: {case}")
        data = json.loads(gzip.decompress(raw))
        cert = data["certificate"]
        if (cert["queue"] or cert["counts"]["PENDING"] or
                data["original"]["case_id"] != case):
            raise ValueError(f"Expected complete, correctly bound certificate: {case}")
        for car in "ps":
            yield car_bounds(case, cert, car, paired[case, car])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo", type=Path, help="PR #146 checkout")
    group.add_argument("--data", type=Path, help="radius_resolution data directory")
    parser.add_argument("--output", type=Path, help="output CSV (default: stdout)")
    args = parser.parse_args()
    rows = list(analyse(args.data if args.data is not None else args.repo / DATA))
    out = args.output.open("w", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            out.close()


if __name__ == "__main__":
    main()
