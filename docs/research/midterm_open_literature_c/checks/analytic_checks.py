#!/usr/bin/env python3
"""Three preregistered deterministic algebra fixtures; no optimizer or RNG."""
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
DOC = HERE.parent
ROOT = DOC.parents[2]


def det(a):
    if len(a) == 1:
        return a[0][0]
    return sum(((-1) ** j) * a[0][j] * det(
        [[a[i][k] for k in range(len(a)) if k != j]
         for i in range(1, len(a))]) for j in range(len(a)))


def quadratic(a, v):
    return sum(v[i] * a[i][j] * v[j]
               for i in range(len(v)) for j in range(len(v)))


def stringify(x):
    if isinstance(x, F):
        return str(x)
    if isinstance(x, dict):
        return {k: stringify(v) for k, v in x.items()}
    if isinstance(x, list):
        return [stringify(v) for v in x]
    return x


def main():
    # E1: exact squared ranges and opposing halfspaces, without computing sqrt.
    anchors = [[F(0), F(0)], [F(2), F(0)], [F(0), F(2)]]
    point = [F(1), F(1)]
    distances2 = [sum((point[i] - a[i]) ** 2 for i in range(2))
                  for a in anchors]
    difference_rows = [[F(4), F(0)], [F(0), F(4)]]
    radius = F(1, 4)
    e1 = {"squared_ranges": distances2,
          "difference_matrix_determinant": det(difference_rows),
          "feasible_point": point,
          "twice_positive_radius": 2 * radius,
          "original_set_nonempty": all(v == 2 for v in distances2),
          "positive_radius_ball_impossible": 2 * radius > 0,
          "finding": "positive-radius inflation does not imply original-set emptiness"}

    # E2: objective values at x=2 and x^2=5, all symbolic/rational.
    f_at_two = ((F(2) - 1) ** 2 + (F(2) - 3) ** 2) / 2
    g_at_two = ((F(4) - 1) ** 2 + (F(4) - 9) ** 2) / 2
    g_at_root5 = ((F(5) - 1) ** 2 + (F(5) - 9) ** 2) / 2
    e2 = {"raw_unique_minimizer": "2 on x>=0",
          "squared_range_unique_minimizer": "sqrt(5) on x>=0",
          "f_at_2": f_at_two, "g_at_2": g_at_two,
          "g_at_sqrt5": g_at_root5,
          "f_at_sqrt5": "10-4*sqrt(5)",
          "strict_raw_cost_gap_proof": "9>4*sqrt(5), because both positive and 81>80",
          "targets_differ": g_at_two > g_at_root5 and 81 > 80,
          "finding": "certificate for squared-range objective is not a raw-range certificate"}

    # E3: exact finite covariance matrices, one fixed process interval/response.
    amin, amax, ahat, k = F(1, 3), F(7, 9), F(3, 5), F(2)
    left_low = k * (1 + ahat) / (1 - ahat)
    right_low = (1 + amax) / (1 - amax)
    left_high = k * (1 - ahat) / (1 + ahat)
    right_high = (1 - amin) / (1 + amin)
    k0 = (k * (1 - ahat ** 2) - 1 + amin ** 2) / (
        k * (1 - ahat ** 2) - 1 - ahat ** 2 + 2 * amin * ahat)
    actual = [[amin ** abs(i - j) for j in range(3)] for i in range(3)]
    stationary = [[k * ahat ** abs(i - j) for j in range(3)] for i in range(3)]
    nonstationary = [[stationary[i][j] + (k0 - k) * ahat ** (i + j)
                      for j in range(3)] for i in range(3)]
    ds = [[stationary[i][j] - actual[i][j] for j in range(3)] for i in range(3)]
    dn = [[nonstationary[i][j] - actual[i][j] for j in range(3)] for i in range(3)]
    minors = {}
    for size in (1, 2, 3):
        for ids in combinations(range(3), size):
            minors[str(ids)] = det([[ds[i][j] for j in ids] for i in ids])
    v = [F(-9, 5), F(1), F(-1, 10)]
    e3 = {"alpha_interval": [amin, amax], "alpha_hat": ahat,
          "stationary_k": k, "nonstationary_k0_eq32": k0,
          "endpoint_spectral_equalities": [left_low == right_low, left_high == right_high],
          "actual_covariance": actual, "nonstationary_difference": dn,
          "first_pair_difference_determinant": det([row[:2] for row in dn[:2]]),
          "fixed_response": v,
          "response_variance_difference": quadratic(dn, v),
          "stationary_difference_principal_minors": minors,
          "stationary_finite_matrix_psd": all(x >= 0 for x in minors.values()),
          "nonstationary_general_bound_rejected": quadratic(dn, v) < 0,
          "finding": "v1 lowered initial variance is not a universal 3-epoch covariance bound"}

    result = {"protocol_commit": subprocess.check_output(
        ["git", "-C", str(ROOT), "log", "-1", "--format=%H", "--",
         str((DOC / 'CHECK_PROTOCOL.md').relative_to(ROOT))], text=True).strip(),
        "protocol_sha256": hashlib.sha256((DOC / "CHECK_PROTOCOL.md").read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "example_count": 3, "optimizer_calls": 0, "random_draws": 0,
        "results": {"E1": e1, "E2": e2, "E3": e3},
        "meaning": "exact algebra checks and counterexamples; not coverage validation"}
    output = DOC / "checks" / "RESULTS.json"
    with output.open("x", encoding="utf-8") as stream:
        json.dump(stringify(result), stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(stringify(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
