"""Check whether a bounded inter-vehicle measurement constrains any kept joint box."""
import argparse
import csv
import gzip
import json
from collections import deque
from fractions import Fraction
from pathlib import Path


def verify_case(root, obs_file):
    data = json.loads(obs_file.read_text())
    key = data["id"] + "_anchor_only"
    certificate = json.loads((root / "results" / "certificates" / (key + "_Car1.json")).read_text())
    tags = gzip.decompress((root / "results" / "trees" / (key + ".gz")).read_bytes())
    boxes = deque([tuple(tuple(map(Fraction, axis)) for axis in certificate["root"])])
    pair_range = Fraction(data["observations"][8])
    tolerance = Fraction(3, 5)
    lower_allowed = max(Fraction(0), pair_range - tolerance) ** 2
    upper_allowed = (pair_range + tolerance) ** 2
    dz_squared = (Fraction(data["heights"][0]) - Fraction(data["heights"][1])) ** 2
    worst_low = None
    worst_high = None
    kept = 0
    for tag in tags:
        box = boxes.popleft()
        if tag == ord("O"):
            continue
        if tag == ord("S"):
            axis = max(range(4), key=lambda i: box[i][1] - box[i][0])
            a, b = box[axis]
            mid = (a + b) / 2
            for interval in [(a, mid), (mid, b)]:
                boxes.append(box[:axis] + (interval,) + box[axis+1:])
            continue
        assert tag in b"UIP"
        kept += 1
        near, far = dz_squared, dz_squared
        for v, w in zip(box[:2], box[2:]):
            lo, hi = v[0] - w[1], v[1] - w[0]
            near += max(Fraction(0), lo, -hi) ** 2
            far += max(abs(lo), abs(hi)) ** 2
        worst_low = near if worst_low is None else min(worst_low, near)
        worst_high = far if worst_high is None else max(worst_high, far)
    assert not boxes and kept == certificate["kept_boxes"]
    proven = lower_allowed <= worst_low and worst_high <= upper_allowed
    # The verdict uses exact squared-distance comparisons above; these are display columns only.
    return [data["id"], kept, float(worst_low)**.5, float(worst_high)**.5,
            float(pair_range-tolerance), float(pair_range+tolerance), proven]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = [verify_case(args.root, f) for f in sorted((args.root/"results"/"observations").glob("*.json"))]
    assert len(rows) == 8
    with args.output.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case", "retained_joint_boxes", "min_distance_outer_m", "max_distance_outer_m",
                         "bias_band_low_m", "bias_band_high_m", "identical_feasible_sets_proven"])
        writer.writerows(rows)
    for row in rows:
        print(row[0], row[-1])
