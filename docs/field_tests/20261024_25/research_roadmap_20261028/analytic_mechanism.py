"""Small analytic surrogate; no sensor files, FGO solver, or rover interface.

Absolute positions are represented as errors u,v relative to true positions
0,d (fixed ordering). Local estimates have errors z1,z2. A correct relative
measurement contributes gamma/2 * (v-u)^2. Precisions are illustrative.
"""

import argparse
import json
import math
from pathlib import Path


def _check(a, b, gamma, z1, z2):
    if not all(math.isfinite(v) for v in (a, b, gamma, z1, z2)):
        raise ValueError("finite parameters required")
    if a <= 0 or b <= 0 or gamma < 0:
        raise ValueError("positive local precisions and nonnegative peer weight required")


def objective(u, v, a, b, gamma, z1, z2):
    return 0.5 * (a * (u-z1)**2 + b * (v-z2)**2 + gamma * (v-u)**2)


def gradient(u, v, a, b, gamma, z1, z2):
    return (a * (u-z1) + gamma * (u-v),
            b * (v-z2) + gamma * (v-u))


def unconstrained(a, b, gamma, z1, z2):
    _check(a, b, gamma, z1, z2)
    determinant = a*b + gamma*(a+b)
    u = (a*(b+gamma)*z1 + gamma*b*z2) / determinant
    v = (gamma*a*z1 + b*(a+gamma)*z2) / determinant
    return u, v


def equal_precision_box(weight, gamma, z1, z2, budget):
    """Exact optimum ONLY for equal local precisions and equal scalar budgets.

    Bounds are |u-z1|<=budget, |v-z2|<=budget. This closed form is not a
    nonlinear FGO implementation or a rule for selecting a real budget.
    """
    _check(weight, weight, gamma, z1, z2)
    if not math.isfinite(budget) or budget < 0:
        raise ValueError("finite nonnegative budget required")
    transfer = gamma*(z1-z2) / (weight+2*gamma)
    transfer = max(-budget, min(budget, transfer))
    return z1-transfer, z2+transfer


def clip_about_reference(pair, reference, budget):
    return tuple(r + max(-budget, min(budget, x-r)) for x, r in zip(pair, reference))


def _record(pair, reference):
    u, v = pair
    return {
        "car1_error_m": u,
        "car2_error_m": v,
        "car1_abs_error_m": abs(u),
        "car2_abs_error_m": abs(v),
        "relative_residual_m": v-u,
        "car1_displacement_from_independent_m": u-reference[0],
        "car2_displacement_from_independent_m": v-reference[1],
    }


def build_report():
    # Public explanatory values, not selected on held-out data and not a
    # recommended operating budget. No random trials or sensor data are used.
    budget = 0.04
    cases = [
        ("normal", 1., 1., 25., 0., 0.),
        ("car1_bias_peer_off", 1., 1., 0., .30, 0.),
        ("car1_bias_peer_weight_1", 1., 1., 1., .30, 0.),
        ("car1_bias_peer_weight_25", 1., 1., 25., .30, 0.),
        ("car1_bias_peer_weight_1000", 1., 1., 1000., .30, 0.),
        ("car1_bias_higher_local_precision", 4., 1., 25., .30, 0.),
        ("car2_bias_peer_weight_25", 1., 1., 25., 0., .30),
        ("car1_negative_bias", 1., 1., 25., -.30, 0.),
        ("both_same_bias", 1., 1., 25., .30, .30),
    ]
    records = []
    for name, a, b, gamma, z1, z2 in cases:
        ref = (z1, z2)
        joint = unconstrained(a, b, gamma, z1, z2)
        row = {
            "case": name,
            "parameters": {"a": a, "b": b, "gamma": gamma, "z1_m": z1, "z2_m": z2},
            "independent": _record(ref, ref),
            "unconstrained_joint": _record(joint, ref),
        }
        if a == b:
            bounded = equal_precision_box(a, gamma, z1, z2, budget)
            clipped = clip_about_reference(joint, ref, budget)
            row["equal_precision_box"] = _record(bounded, ref)
            row["post_clip"] = _record(clipped, ref)
            row["box_equals_post_clip_within_1e_12"] = all(abs(x-y) <= 1e-12 for x, y in zip(bounded, clipped))
        else:
            row["box_status"] = "NOT_EVALUATED_UNEQUAL_PRECISION"
        records.append(row)
    return {
        "schema": "cooperative-influence-analytic-v1",
        "status": "ILLUSTRATION_NOT_A_PROPOSED_OR_VALIDATED_FGO_METHOD",
        "source_data": "none; deterministic analytic surrogate",
        "units": "positions and errors in m; illustrative inverse-variance weights",
        "budget_m": budget,
        "budget_status": "EXPLANATORY_ONLY_NOT_FROZEN_RESEARCH_BUDGET",
        "case_count": len(records),
        "cases": records,
        "limitations": [
            "One-dimensional signed relative displacement with fixed ordering, not arbitrary 2-D UWB geometry.",
            "Local absolute estimates are a surrogate, not raw wall-anchor observations.",
            "No temporal state, marginalization, covariance guarantee, IMU, or real-time claim.",
            "The symmetric box optimum equals post-clipping here; this does not demonstrate an advantage over clipping.",
            "A displacement bound is relative to the independent reference, not absolute truth or integrity risk.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Exclusive creation protects previous results. A rerun needs a fresh path.
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(build_report(), handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print("Wrote nine deterministic analytic cases:", args.output)


if __name__ == "__main__":
    main()
