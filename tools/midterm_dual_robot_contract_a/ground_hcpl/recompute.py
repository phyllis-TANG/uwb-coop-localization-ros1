"""Rebuild the linearization point and audit each prefix using independent batch square-root least squares."""
import argparse
import json
from pathlib import Path
from statistics import NormalDist

import numpy as np


CARS = ("car1", "car2")
DIM = 13
LINKS = 9
RANGE_SD = 0.04
PRIOR_SD = np.array([0.2] * 4 + [0.3] * LINKS)
WALK_SD = np.array([0.03] * 4 + [0.01] * LINKS)
BIAS_BOUND = 0.02
NOMINAL_ALPHA = 0.01
ATOL = 1e-12


def check(value, reference, name):
    np.testing.assert_allclose(value, reference, atol=ATOL, rtol=0, err_msg=name)
    return float(np.max(np.abs(np.asarray(value) - reference)))


def antenna_step(previous, current, initial, model):
    """Antenna increments in the local map, then local map to survey room, both planar."""
    px, py, pa = previous
    cx, cy, ca = current
    arm = complex(*model["base_to_antenna_body_xy_m"])
    base_delta = complex(cx - px, cy - py)
    arm_delta = (np.exp(1j * ca) - np.exp(1j * pa)) * arm
    room_rotation = np.exp(1j * (np.deg2rad(model["initial_heading_deg"]) - initial[2]))
    room_delta = room_rotation * (base_delta + arm_delta)
    return [room_delta.real, room_delta.imag]


def range_equations(point, packet):
    """Surveyed endpoints define a signed nine-link, 3-D slant range model."""
    positions = np.column_stack((point[:4].reshape(2, 2), packet["heights"]))
    anchors = np.asarray(packet["anchors"])
    differences = np.vstack((positions[0] - anchors, positions[1] - anchors,
                             positions[0] - positions[1]))
    distances = np.linalg.norm(differences, axis=1)
    directions = differences[:, :2] / distances[:, None]
    h = np.zeros((LINKS, DIM))
    h[:4, :2] = directions[:4]
    h[4:8, 2:4] = directions[4:8]
    h[8, :2], h[8, 2:4] = directions[8], -directions[8]
    h[:, 4:] = np.eye(LINKS)
    predicted = distances + point[4:]
    return h, predicted


def car_result(x, covariance, sensitivity, index, archived):
    axes = slice(2 * index, 2 * index + 2)
    marginal = covariance[axes, axes]
    sigma = np.sqrt(np.diag(marginal))
    history_bias = BIAS_BOUND * np.abs(sensitivity[axes]).sum(axis=1)
    current_bias = BIAS_BOUND * np.abs(sensitivity[axes, -LINKS:]).sum(axis=1)
    check(x[axes], archived["published_antenna_xy"], "published XY")
    check(sigma, archived["sigma"], "marginal sigma")
    check(current_bias, archived["current_bias_bound"], "current bias bound")
    check(history_bias, archived["history_bias_bound"], "history bias bound")
    errors = {}
    for label, alpha, bound in [
        ("eq13_to_16", NOMINAL_ALPHA, current_bias),
        ("axis_preallocated", NOMINAL_ALPHA / 2, current_bias),
        ("history_preallocated", NOMINAL_ALPHA / 2, history_bias),
    ]:
        quantile = NormalDist().inv_cdf(1 - alpha / 2)
        per_axis = bound + quantile * sigma
        hcpl = float(np.linalg.norm(per_axis))
        variant = archived["variants"][label]
        check(alpha, variant["axis_alpha"], "axis alpha")
        check(quantile, variant["k"], "axis quantile")
        check(per_axis, variant["CPL"], "CPL")
        check(hcpl, variant["HCPL"], "HCPL")
        errors[label] = hcpl - variant["HCPL"]
    return dict(car=index + 1, xy=x[axes].tolist(), covariance=marginal.tolist(),
                bias=history_bias.tolist(), current_bias=current_bias.tolist(),
                HCPL_difference_m=errors)


def recompute(data):
    packets, history = data["packets"], data["history"]
    if not packets or len(packets) != len(history):
        raise ValueError("each packet needs one archived state")
    models = data["survey_init"]
    config = data.get("config", {})
    prior_time = config["prior_state_s"] if "prior_state_s" in config else data["prior_state_s"]
    expected_times = np.arange(len(packets)) + prior_time
    check([p["t"] for p in packets], expected_times, "packets start at survey prior and have 1 s cadence")
    check([s["t"] for s in history], expected_times, "archive state times")
    check(BIAS_BOUND, data["remaining_range_bias_bound"], "model bias bound")
    check(NOMINAL_ALPHA, data["axis_nominal_alpha"], "model risk")
    check(np.diag(WALK_SD ** 2), data["Q"], "model process covariance")
    check(RANGE_SD ** 2 * np.eye(LINKS), data["R"], "model range covariance")

    n = len(packets)
    stride = DIM + LINKS
    design = np.zeros((stride * n, DIM * n))
    values = np.zeros(stride * n)
    measurement_rows = []
    prior = np.r_[np.concatenate([models[c]["start_antenna_xyz_m"][:2] for c in CARS]),
                  np.zeros(LINKS)]
    prior_covariance = np.diag(PRIOR_SD ** 2)
    results = []
    for i, (packet, state) in enumerate(zip(packets, history)):
        col = slice(i * DIM, (i + 1) * DIM)
        row = slice(i * stride, i * stride + DIM)
        ranges = slice(row.stop, (i + 1) * stride)
        if i == 0:
            displacement = np.zeros(4)
            sd = PRIOR_SD
            motion_value = prior
        else:
            displacement = np.concatenate([
                antenna_step(packets[i - 1]["odom"][j], packet["odom"][j],
                             packets[0]["odom"][j], models[c]) for j, c in enumerate(CARS)
            ])
            sd = WALK_SD
            motion_value = np.r_[displacement, np.zeros(LINKS)]
            design[row, col.start - DIM:col.start] = -np.diag(1 / sd)
            prior = state_estimate + motion_value
            prior_covariance = covariance + np.diag(sd ** 2)
        design[row, col] = np.diag(1 / sd)
        values[row] = motion_value / sd
        # Compute the point from the preceding independently solved prefix.
        point = prior
        check(point, state["prior"], "linearization point reconstructed from previous SVD prefix")
        check(displacement, state["u"], "antenna displacement")
        check(prior_covariance, state["prior_cov"], "prediction covariance")
        h, predicted = range_equations(point, packet)
        observed = np.asarray(packet["ranges"])
        innovation = observed - predicted
        innovation_cov = h @ prior_covariance @ h.T + RANGE_SD ** 2 * np.eye(LINKS)
        check(h, state["H"], "range Jacobian")
        check(predicted, state["predicted"], "slant range prediction")
        check(innovation, state["innovation"], "slant range innovation")
        check(innovation_cov, state["S"], "innovation covariance")
        design[ranges, col] = h / RANGE_SD
        values[ranges] = (observed - predicted + h @ point) / RANGE_SD
        measurement_rows.extend(range(ranges.start, ranges.stop))

        matrix = design[:ranges.stop, :col.stop]
        left, singular, right_t = np.linalg.svd(matrix, full_matrices=False)
        if singular[-1] <= max(matrix.shape) * np.finfo(float).eps * singular[0]:
            raise ValueError("rank deficient batch system with survey and process priors")
        # Only the final 13 rows of the pseudoinverse enter the terminal marginal.
        inverse_rows = (right_t.T[-DIM:] / singular) @ left.T
        state_estimate = inverse_rows @ values[:ranges.stop]
        covariance = inverse_rows @ inverse_rows.T
        sensitivity = inverse_rows[:, measurement_rows] / RANGE_SD
        state_difference = check(state_estimate, state["posterior"], "full posterior state")
        covariance_difference = check(covariance, state["posterior_cov"], "full posterior covariance")
        check(sensitivity[:, -LINKS:], state["gain"], "current measurement influence")
        results.append(dict(t=packet["t"], max_abs_state_difference=state_difference,
                            max_abs_covariance_difference=covariance_difference))
    transfer_difference = check(sensitivity, data["transfer"], "all-packet measurement influence")
    nis = float(innovation @ np.linalg.solve(innovation_cov, innovation))
    check(nis, data["innovation_test"]["statistic"], "terminal NIS")
    cars = [car_result(state_estimate, covariance, sensitivity, i, c)
            for i, c in enumerate(data["cars"])]
    if len(cars) != len(CARS):
        raise ValueError("expected exactly two archived vehicles")
    # Keep original Car1 top-level keys for consumers of the first development artifact.
    legacy = {key: cars[0][key] for key in ("xy", "bias", "covariance", "HCPL_difference_m")}
    return dict(**legacy, cars=cars, prefixes=results, NIS=nis,
                max_abs_transfer_difference=transfer_difference)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", nargs="?", type=Path)
    args = parser.parse_args()
    result = json.dumps(recompute(json.loads(args.archive.read_text())), indent=2, allow_nan=False)
    if args.output is None:
        print(result)
    else:
        args.output.write_text(result + "\n")


if __name__ == "__main__":
    main()
