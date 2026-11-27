"""Analytic UWB mirror ambiguity and nominal chi-square gate checks."""

import math


def profiled_score(measured, predicted, sigma, bias_limit):
    """Minimise the standardised range residuals over a bias on the last link."""
    bias = max(-bias_limit, min(bias_limit, measured[-1] - predicted[-1]))
    residuals = [a - b for a, b in zip(measured, predicted)]
    residuals[-1] -= bias
    return sum((r / sigma) ** 2 for r in residuals)


def mirror_example():
    # Synthetic, noise-free construction. Distance is invariant under y -> -y.
    anchor_x = (-4.0, -1.0, 3.0, 5.0)
    x, y = 1.0, 2.0
    sigma, bias, bias_limit, gate = 0.04, 0.30, 0.60, 9.488
    ranges = [math.hypot(x - a, y) for a in anchor_x]
    measured = list(ranges)
    measured[-1] += bias
    mirror_ranges = [math.hypot(x - a, -y) for a in anchor_x]

    # Rows one and two span x,y. A third independent column acts only on link four.
    gradients = [((x - a) / r, y / r) for a, r in zip(anchor_x, ranges)]
    u, v = gradients[:2]
    determinant = u[0] * v[1] - u[1] * v[0]
    if abs(determinant) < 1e-12:
        raise ValueError("The designated linearisation point is rank deficient")

    # The reflected position differs only in y: the displacement is -2*y.
    mirror_tangent = [r - 2.0 * y * gy for r, (_, gy) in zip(ranges, gradients)]
    exact_cost = profiled_score(measured, mirror_ranges, sigma, bias_limit)
    local_cost = profiled_score(measured, mirror_tangent, sigma, bias_limit)
    separation = 2.0 * abs(y)
    if not (exact_cost <= gate < local_cost and math.isclose(local_cost, 12764.739951578, abs_tol=1e-7, rel_tol=0.0)):
        raise ValueError("Unexpected mirror scores")
    print(f"Nonlinear mirror score: {exact_cost:.6f}")
    print(f"Affine mirror score: {local_cost:.6f} (gate {gate})")
    print(f"Mirror separation: {separation:.2f} m; covering-radius lower bound: {separation / 2:.2f} m")


def chi2_tail(degrees, budget):
    """Upper chi-square tail via the integer/half-integer upper-gamma recurrence."""
    x = budget / 2
    if degrees % 2:
        shape = 0.5
        result = math.erfc(math.sqrt(x))
    else:
        shape = 1.0
        result = math.exp(-x)
    while shape < degrees / 2:
        result += math.exp(shape * math.log(x) - x - math.lgamma(shape + 1))
        shape += 1.0
    return result


if __name__ == "__main__":
    mirror_example()
    for degrees, budget, expected in [
        (8, 24, 0.002291791207791423),
        (9, 26, 0.002042989656293934),
        (8, 26, 0.0010502997311105304),
    ]:
        probability = chi2_tail(degrees, budget)
        if not math.isclose(probability, expected, rel_tol=2e-14):
            raise ValueError(f"Unexpected tail probability for df={degrees}, q={budget}")
        print(f"Pr(chi2_{degrees} > {budget}) = {probability:.11f}")
