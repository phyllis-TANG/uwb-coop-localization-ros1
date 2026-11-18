"""Candidate support bounds for the diagonal anchor-ball outer relaxation."""
from fractions import Fraction
from math import isqrt
from time import monotonic

from prepare import decimal_exact


def propose(model, threshold):
    domain = [list(interval) for interval in model["domain"]]
    proofs = []
    for axis in range(4):
        for side in (0, 1):
            start = monotonic()
            sign = 2 * side - 1
            endpoint = Fraction(domain[axis][side])
            winner = None
            for anchor, coordinates in enumerate(model["anchors"]):
                index = 4 * (axis // 2) + anchor
                variance = Fraction(model["R"][index][index])
                squared = Fraction(threshold) * variance * 10**24
                epsilon = Fraction(isqrt(squared.numerator // squared.denominator) + 1, 10**12)
                radius = Fraction(model["observations"][index][1]) + epsilon
                candidate = Fraction(coordinates[axis % 2]) + sign * radius
                if radius >= 0 and sign * candidate < sign * endpoint:
                    endpoint, winner = candidate, index
            if monotonic() - start > 0.5:
                winner = None
            proofs.append(winner)
            if winner is not None:
                domain[axis][side] = decimal_exact(endpoint)
    if any(Fraction(lo) > Fraction(hi) for lo, hi in domain):
        return model["domain"], [None] * 8
    return domain, proofs
